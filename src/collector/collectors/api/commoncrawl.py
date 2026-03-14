"""Common Crawl collector - Enterprise web intelligence via archived snapshots.

Orchestrates CommonCrawlAdapter + CrawlIntelAnalyzer to produce
CollectedSignal objects from time series analysis of enterprise websites.
"""

from datetime import date, timedelta
from typing import Any

from loguru import logger

from src.infrastructure.datasources.adapters.commoncrawl import (
    CdxRecord,
    CommonCrawlAdapter,
    WebPageContent,
)
from src.infrastructure.datasources.analyzers.crawl_intel import (
    CrawlIntelAnalyzer,
    WebSnapshot,
)

from ..base import BaseCollector, CollectedSignal, CollectorConfig


class CommonCrawlCollector(BaseCollector):
    """Collect enterprise signals from Common Crawl archives.

    For each enterprise:
    1. Query CDX index for monthly snapshots of the website
    2. Extract text content from WARC records
    3. Analyze each snapshot with LLM (qwen3.5:27b)
    4. Detect patterns in the time series
    5. Produce CollectedSignal for each detected pattern

    Prioritization:
    - Enterprises with recent BODACC signals -> high priority
    - Enterprises in TAJINE-analyzed departments -> medium
    - Recently created enterprises (<2 years) -> medium
    - Others -> low priority, opportunistic
    """

    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3.5:27b",
        max_enterprises: int = 100,
        months_back: int = 12,
    ) -> None:
        super().__init__(
            CollectorConfig(
                name="commoncrawl",
                source_type="api",
                rate_limit=1.0,  # 1 req/s for CDX API
                max_retries=2,
                timeout=60,
                batch_size=max_enterprises,
            )
        )
        self._adapter = CommonCrawlAdapter()
        self._analyzer = CrawlIntelAnalyzer(
            ollama_url=ollama_url,
            model=model,
        )
        self._months_back = months_back

    async def close(self) -> None:
        """Cleanup resources."""
        await super().close()
        await self._adapter.close()
        await self._analyzer.close()

    async def collect(
        self,
        code_dept: str | None = None,
        since: date | None = None,
    ) -> list[CollectedSignal]:
        """Collect signals from Common Crawl for enterprises.

        Args:
            code_dept: Department code to filter enterprises.
            since: Not used directly (we use months_back instead).

        Returns:
            List of CollectedSignal from pattern detection.
        """
        signals: list[CollectedSignal] = []

        # Get target enterprises
        enterprises = await self._get_target_enterprises(code_dept)
        if not enterprises:
            logger.warning("[commoncrawl] No enterprises with websites found")
            return []

        logger.info(f"[commoncrawl] Analyzing {len(enterprises)} enterprises for dept={code_dept}")

        for enterprise in enterprises:
            try:
                enterprise_signals = await self._analyze_enterprise(enterprise)
                signals.extend(enterprise_signals)
            except Exception as e:
                logger.error(f"[commoncrawl] Error analyzing {enterprise.get('siret')}: {e}")

        return signals

    async def collect_single(
        self,
        siret: str,
        nom: str,
        site_web: str,
        naf: str = "",
        code_dept: str | None = None,
    ) -> list[CollectedSignal]:
        """Analyze a single enterprise. Useful for testing and on-demand analysis.

        Args:
            siret: Enterprise SIRET.
            nom: Enterprise name.
            site_web: Website URL.
            naf: NAF code.
            code_dept: Department code.

        Returns:
            List of signals detected for this enterprise.
        """
        enterprise = {
            "siret": siret,
            "nom": nom,
            "site_web": site_web,
            "naf": naf,
            "code_dept": code_dept,
        }
        return await self._analyze_enterprise(enterprise)

    async def _analyze_enterprise(self, enterprise: dict[str, Any]) -> list[CollectedSignal]:
        """Full analysis pipeline for one enterprise."""
        siret = enterprise.get("siret", "unknown")
        nom = enterprise.get("nom", "unknown")
        site_web = enterprise.get("site_web", "")
        naf = enterprise.get("naf", "")
        code_dept = enterprise.get("code_dept")

        if not site_web:
            return []

        # Step 1: Get timeline from Common Crawl
        timeline = await self._adapter.get_timeline(site_web, months=self._months_back)

        if not timeline:
            logger.debug(f"[commoncrawl] No snapshots found for {nom} ({site_web})")
            return []

        logger.info(
            f"[commoncrawl] {nom}: {len(timeline)} snapshots from "
            f"{timeline[0].crawl_date} to {timeline[-1].crawl_date}"
        )

        # Step 2: Analyze each snapshot with LLM
        snapshots: list[WebSnapshot] = []
        prev_hash: str = ""

        for content in timeline:
            # Skip unchanged content
            if content.content_hash == prev_hash and content.text == "[unchanged]":
                if snapshots:
                    # Copy previous snapshot with new date
                    prev = snapshots[-1]
                    snap = WebSnapshot(
                        siret=siret,
                        url=content.url,
                        crawl_date=content.crawl_date,
                        crawl_id=content.crawl_id,
                        activity_status=prev.activity_status,
                        employee_mentions=prev.employee_mentions,
                        products_services=prev.products_services,
                        job_openings=prev.job_openings,
                        sentiment_score=prev.sentiment_score,
                        notable_elements=prev.notable_elements,
                        content_hash=content.content_hash,
                        content_length=prev.content_length,
                        confidence=prev.confidence,
                    )
                    snapshots.append(snap)
                continue

            # LLM analysis
            snap = await self._analyzer.analyze_content(
                text=content.text,
                siret=siret,
                nom=nom,
                naf=naf,
                crawl_date=content.crawl_date,
                crawl_id=content.crawl_id,
                url=content.url,
                content_hash=content.content_hash,
            )
            snapshots.append(snap)
            prev_hash = content.content_hash

        if len(snapshots) < 2:
            return []

        # Step 3: Compare consecutive snapshots
        for i in range(1, len(snapshots)):
            change = await self._analyzer.compare_snapshots(snapshots[i - 1], snapshots[i], nom)
            if change and change.changes:
                snapshots[i].notable_elements.extend(change.changes)

        # Step 4: Detect patterns
        patterns = self._analyzer.detect_patterns(snapshots)

        # Step 5: Convert patterns to CollectedSignal
        signals: list[CollectedSignal] = []
        for pattern in patterns:
            signals.append(
                CollectedSignal(
                    source="commoncrawl",
                    source_url=site_web,
                    event_date=pattern.get("detected_at"),
                    code_dept=code_dept,
                    metric_name=pattern.get("metric_name", "unknown"),
                    metric_value=pattern.get("severity", pattern.get("confidence", 0.5)),
                    signal_type=pattern.get("signal_type", "neutre"),
                    confidence=pattern.get("confidence", 0.5),
                    raw_data={
                        "siret": siret,
                        "nom": nom,
                        "pattern": pattern.get("description"),
                        "details": pattern.get("details"),
                        "snapshots_count": len(snapshots),
                        "timeline_start": snapshots[0].crawl_date.isoformat(),
                        "timeline_end": snapshots[-1].crawl_date.isoformat(),
                    },
                    extracted_text=pattern.get("details", ""),
                )
            )

        if signals:
            logger.info(
                f"[commoncrawl] {nom}: {len(signals)} patterns detected "
                f"from {len(snapshots)} snapshots"
            )

        # Persist to database (best effort)
        await self._persist_results(snapshots, signals, nom, code_dept)

        return signals

    async def _persist_results(
        self,
        snapshots: list,
        signals: list[CollectedSignal],
        nom: str,
        code_dept: str | None,
    ) -> None:
        """Persist snapshots and signals to database (best effort)."""
        try:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            from src.infrastructure.persistence.database import get_session
            from src.infrastructure.persistence.models.web_snapshot_model import (
                CrawlIntelSignalDB,
                WebSnapshotDB,
            )

            async with get_session() as session:
                # Upsert snapshots (skip duplicates)
                for snap in snapshots:
                    stmt = (
                        pg_insert(WebSnapshotDB)
                        .values(
                            siret=snap.siret,
                            url=snap.url,
                            crawl_date=snap.crawl_date,
                            crawl_id=snap.crawl_id,
                            content_hash=snap.content_hash,
                            content_length=snap.content_length,
                            activity_status=snap.activity_status,
                            employee_mentions=snap.employee_mentions,
                            products_services=snap.products_services,
                            job_openings=snap.job_openings,
                            sentiment_score=snap.sentiment_score,
                            notable_elements=snap.notable_elements,
                            confidence=snap.confidence,
                        )
                        .on_conflict_do_nothing(
                            index_elements=["siret", "crawl_id", "content_hash"]
                        )
                    )
                    await session.execute(stmt)

                # Save signals
                for sig in signals:
                    db_sig = CrawlIntelSignalDB(
                        siret=sig.raw_data.get("siret", ""),
                        nom=nom,
                        code_dept=code_dept,
                        signal_type=sig.signal_type,
                        metric_name=sig.metric_name,
                        confidence=sig.confidence,
                        description=sig.raw_data.get("pattern", ""),
                        details=sig.extracted_text,
                        source_url=sig.source_url,
                        snapshots_count=sig.raw_data.get("snapshots_count"),
                        raw_data=sig.raw_data,
                    )
                    session.add(db_sig)

            logger.debug(
                f"[commoncrawl] Persisted {len(snapshots)} snapshots + "
                f"{len(signals)} signals for {nom}"
            )
        except Exception as e:
            logger.warning(f"[commoncrawl] Persistence failed (non-blocking): {e}")

    async def _get_target_enterprises(self, code_dept: str | None) -> list[dict[str, Any]]:
        """Get prioritized list of enterprises to analyze.

        Priority order:
        1. Enterprises with recent BODACC signals (liquidations, creations)
        2. Enterprises from SIRENE with known websites
        """
        enterprises: list[dict[str, Any]] = []
        seen_sirets: set[str] = set()

        # Priority 1: enterprises with recent BODACC activity
        try:
            bodacc_enterprises = await self._get_bodacc_targets(code_dept)
            for e in bodacc_enterprises:
                siret = e.get("siret", "")
                if siret and siret not in seen_sirets:
                    seen_sirets.add(siret)
                    enterprises.append(e)
        except Exception as ex:
            logger.debug(f"[commoncrawl] BODACC priority lookup failed: {ex}")

        # Priority 2: SIRENE enterprises with websites
        remaining = self.config.batch_size - len(enterprises)
        if remaining > 0:
            try:
                from src.infrastructure.datasources.adapters.sirene import SireneAdapter

                sirene = SireneAdapter()
                params: dict[str, Any] = {"per_page": 25}
                if code_dept:
                    params["departement"] = code_dept

                result = await sirene.search(params)
                await sirene.close()

                for r in result.get("results", []):
                    siret = r.get("siret", "")
                    if siret in seen_sirets:
                        continue
                    site_web = self._extract_website(r)
                    if site_web:
                        seen_sirets.add(siret)
                        enterprises.append(
                            {
                                "siret": siret,
                                "nom": r.get("nom") or r.get("nom_commercial", ""),
                                "site_web": site_web,
                                "naf": r.get("naf_code", ""),
                                "code_dept": r.get("adresse", {}).get("departement") or code_dept,
                            }
                        )
                    if len(enterprises) >= self.config.batch_size:
                        break
            except Exception as e:
                logger.error(f"[commoncrawl] SIRENE lookup failed: {e}")

        logger.info(f"[commoncrawl] Target enterprises: {len(enterprises)} (dept={code_dept})")
        return enterprises[: self.config.batch_size]

    async def _get_bodacc_targets(self, code_dept: str | None) -> list[dict[str, Any]]:
        """Get enterprises with recent BODACC signals that have websites."""
        from sqlalchemy import text

        from src.infrastructure.persistence.database import get_session

        enterprises = []
        async with get_session() as session:
            # Query recent BODACC signals for enterprises with known websites
            query = text("""
                SELECT DISTINCT ON (s.raw_data->>'siret')
                    s.raw_data->>'siret' as siret,
                    s.raw_data->>'nom' as nom,
                    s.raw_data->>'naf' as naf,
                    s.code_dept
                FROM signals s
                WHERE s.source = 'bodacc'
                  AND s.event_date >= CURRENT_DATE - INTERVAL '90 days'
                  AND s.raw_data->>'siret' IS NOT NULL
                  AND (:dept IS NULL OR s.code_dept = :dept)
                ORDER BY s.raw_data->>'siret', s.event_date DESC
                LIMIT 10
            """)
            result = await session.execute(query, {"dept": code_dept})
            rows = result.fetchall()

        # For each BODACC enterprise, try to find a website via SIRENE
        if rows:
            from src.infrastructure.datasources.adapters.sirene import SireneAdapter

            sirene = SireneAdapter()
            for row in rows:
                siret = row[0]
                if not siret or len(siret) < 9:
                    continue
                try:
                    result = await sirene.search({"q": siret, "per_page": 1})
                    for r in result.get("results", []):
                        site_web = self._extract_website(r)
                        if site_web:
                            enterprises.append(
                                {
                                    "siret": siret,
                                    "nom": row[1] or r.get("nom", ""),
                                    "site_web": site_web,
                                    "naf": row[2] or r.get("naf_code", ""),
                                    "code_dept": row[3] or code_dept,
                                    "priority": "bodacc",
                                }
                            )
                except Exception:
                    continue
            await sirene.close()

        return enterprises

    def _extract_website(self, enterprise: dict[str, Any]) -> str | None:
        """Extract website URL from enterprise data."""
        raw = enterprise.get("raw", {})

        # Try common fields
        for field in ("site_internet", "url", "website"):
            if url := raw.get(field):
                return url

        # Try matching_etablissements
        for etab in raw.get("matching_etablissements", []):
            if url := etab.get("site_internet"):
                return url

        # Try complements
        complements = raw.get("complements", {})
        if urls := complements.get("identifiant_association"):
            pass  # Not a website

        # Fallback: construct from name (best effort)
        nom = enterprise.get("nom", "")
        if nom and len(nom) > 3:
            # Only for well-known domains, don't guess
            clean = nom.lower().replace(" ", "").replace("'", "")
            if len(clean) <= 20:
                return f"{clean}.fr"

        return None
