"""CrawlIntel Analyzer - LLM-powered web content analysis and pattern detection."""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx
from loguru import logger


@dataclass
class WebSnapshot:
    """Structured snapshot of an enterprise website at a point in time."""

    siret: str
    url: str
    crawl_date: date
    crawl_id: str

    # LLM-extracted signals
    activity_status: str = "unknown"  # active, declining, closed, unknown
    employee_mentions: int | None = None
    products_services: list[str] = field(default_factory=list)
    job_openings: int = 0
    sentiment_score: float = 0.0  # -1.0 to 1.0
    notable_elements: list[str] = field(default_factory=list)

    # Meta
    content_hash: str = ""
    content_length: int = 0
    confidence: float = 0.0
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for storage."""
        return {
            "siret": self.siret,
            "url": self.url,
            "crawl_date": self.crawl_date.isoformat(),
            "crawl_id": self.crawl_id,
            "activity_status": self.activity_status,
            "employee_mentions": self.employee_mentions,
            "products_services": self.products_services,
            "job_openings": self.job_openings,
            "sentiment_score": self.sentiment_score,
            "notable_elements": self.notable_elements,
            "content_hash": self.content_hash,
            "content_length": self.content_length,
            "confidence": self.confidence,
        }


@dataclass
class ChangeSignal:
    """A detected change between two consecutive snapshots."""

    changes: list[str]
    trend: str  # growth, stable, decline, pivot, closure
    severity: float  # 0.0 to 1.0
    signal_type: str  # positif, negatif, neutre


# Pattern definitions for time series analysis
PATTERNS = {
    "site_disappeared": {
        "description": "Site returns 404 for 2+ consecutive months",
        "signal_type": "negatif",
        "confidence": 0.8,
        "metric_name": "site_disparu",
    },
    "hiring_surge": {
        "description": "Job openings jump from 0 to 5+",
        "signal_type": "positif",
        "confidence": 0.9,
        "metric_name": "pic_recrutement",
    },
    "activity_decline": {
        "description": "Sentiment decreases for 3 consecutive months",
        "signal_type": "negatif",
        "confidence": 0.7,
        "metric_name": "declin_activite",
    },
    "pivot_detected": {
        "description": "Products/services change by >50%",
        "signal_type": "neutre",
        "confidence": 0.8,
        "metric_name": "pivot_entreprise",
    },
    "growth_signal": {
        "description": "Employee mentions increase >20%",
        "signal_type": "positif",
        "confidence": 0.85,
        "metric_name": "croissance_entreprise",
    },
    "stale_site": {
        "description": "Content hash unchanged for 6+ months",
        "signal_type": "negatif",
        "confidence": 0.4,
        "metric_name": "site_inactif",
    },
}


class CrawlIntelAnalyzer:
    """Analyzes web content using LLM and detects patterns in time series.

    Uses qwen3.5:27b via Ollama to extract structured information from
    web page content. Compares consecutive snapshots to detect changes.
    Applies pattern rules on time series to generate signals.
    """

    EXTRACT_SYSTEM = (
        "Tu es un analyste economique expert. Tu analyses le contenu "
        "d'un site web d'entreprise pour en extraire des indicateurs de sante "
        "economique. Reponds UNIQUEMENT en JSON valide, sans markdown, "
        "sans explication, sans balise think."
    )

    EXTRACT_TEMPLATE = """Analyse le contenu suivant du site web de l'entreprise {nom} (SIRET: {siret}, secteur NAF: {naf}).
Date du snapshot: {crawl_date}

CONTENU DU SITE:
---
{text}
---

Extrais les informations suivantes en JSON:
{{
  "activity_status": "active|declining|closed|unknown",
  "employee_mentions": null ou nombre entier,
  "products_services": ["liste", "des", "produits"],
  "job_openings": nombre d'offres emploi detectees,
  "sentiment_score": -1.0 a 1.0 (tonalite generale),
  "notable_elements": ["elements remarquables"],
  "confidence": 0.0 a 1.0 (confiance dans ton analyse)
}}"""

    DIFF_TEMPLATE = """Voici deux snapshots du site de {nom}, espaces dans le temps.

SNAPSHOT {date_1}: {json_1}
SNAPSHOT {date_2}: {json_2}

Quels changements significatifs detectes-tu ? Reponds en JSON:
{{
  "changes": ["description de chaque changement"],
  "trend": "growth|stable|decline|pivot|closure",
  "severity": 0.0 a 1.0,
  "signal_type": "positif|negatif|neutre"
}}"""

    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3.5:27b",
    ) -> None:
        self._ollama_url = ollama_url
        self._model = model
        self._client = httpx.AsyncClient(timeout=300.0)

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()

    async def analyze_content(
        self,
        text: str,
        siret: str,
        nom: str,
        naf: str,
        crawl_date: date,
        crawl_id: str,
        url: str,
        content_hash: str,
    ) -> WebSnapshot:
        """Analyze web page content using LLM.

        Args:
            text: Extracted text from web page.
            siret: Enterprise SIRET.
            nom: Enterprise name.
            naf: NAF/APE code.
            crawl_date: Date of the crawl.
            crawl_id: Common Crawl ID.
            url: Original URL.
            content_hash: Hash of the content.

        Returns:
            WebSnapshot with LLM-extracted signals.
        """
        # Truncate to 4000 chars for efficiency
        truncated = text[:4000]

        prompt = self.EXTRACT_TEMPLATE.format(
            nom=nom,
            siret=siret,
            naf=naf or "inconnu",
            crawl_date=crawl_date.isoformat(),
            text=truncated,
        )

        try:
            result = await self._call_llm(prompt)
            parsed = self._parse_json(result)

            return WebSnapshot(
                siret=siret,
                url=url,
                crawl_date=crawl_date,
                crawl_id=crawl_id,
                activity_status=parsed.get("activity_status", "unknown"),
                employee_mentions=parsed.get("employee_mentions"),
                products_services=parsed.get("products_services", []),
                job_openings=parsed.get("job_openings", 0),
                sentiment_score=float(parsed.get("sentiment_score", 0.0)),
                notable_elements=parsed.get("notable_elements", []),
                content_hash=content_hash,
                content_length=len(text),
                confidence=float(parsed.get("confidence", 0.5)),
                raw_text=truncated,
            )

        except Exception as e:
            logger.error(f"[crawl_intel] LLM analysis failed for {siret}: {e}")
            # Return a low-confidence snapshot with basic info
            return WebSnapshot(
                siret=siret,
                url=url,
                crawl_date=crawl_date,
                crawl_id=crawl_id,
                content_hash=content_hash,
                content_length=len(text),
                confidence=0.1,
                raw_text=truncated,
            )

    async def compare_snapshots(
        self,
        snap_old: WebSnapshot,
        snap_new: WebSnapshot,
        nom: str,
    ) -> ChangeSignal | None:
        """Compare two consecutive snapshots using LLM.

        Args:
            snap_old: Earlier snapshot.
            snap_new: Later snapshot.
            nom: Enterprise name.

        Returns:
            ChangeSignal if significant changes detected, None otherwise.
        """
        # Skip if content is identical
        if snap_old.content_hash == snap_new.content_hash:
            return None

        json_old = json.dumps(
            {
                "activity_status": snap_old.activity_status,
                "employee_mentions": snap_old.employee_mentions,
                "products_services": snap_old.products_services,
                "job_openings": snap_old.job_openings,
                "sentiment_score": snap_old.sentiment_score,
            },
            ensure_ascii=False,
        )

        json_new = json.dumps(
            {
                "activity_status": snap_new.activity_status,
                "employee_mentions": snap_new.employee_mentions,
                "products_services": snap_new.products_services,
                "job_openings": snap_new.job_openings,
                "sentiment_score": snap_new.sentiment_score,
            },
            ensure_ascii=False,
        )

        prompt = self.DIFF_TEMPLATE.format(
            nom=nom,
            date_1=snap_old.crawl_date.isoformat(),
            json_1=json_old,
            date_2=snap_new.crawl_date.isoformat(),
            json_2=json_new,
        )

        try:
            result = await self._call_llm(prompt)
            parsed = self._parse_json(result)

            changes = parsed.get("changes", [])
            if not changes:
                return None

            return ChangeSignal(
                changes=changes,
                trend=parsed.get("trend", "stable"),
                severity=float(parsed.get("severity", 0.0)),
                signal_type=parsed.get("signal_type", "neutre"),
            )
        except Exception as e:
            logger.error(f"[crawl_intel] Diff analysis failed: {e}")
            return None

    def detect_patterns(self, snapshots: list[WebSnapshot]) -> list[dict[str, Any]]:
        """Detect patterns in a time series of snapshots.

        Args:
            snapshots: Chronologically ordered list of WebSnapshots.

        Returns:
            List of detected patterns with metadata.
        """
        if len(snapshots) < 2:
            return []

        detected: list[dict[str, Any]] = []
        siret = snapshots[0].siret

        # --- Pattern: stale_site ---
        # Content hash unchanged for 6+ months
        if len(snapshots) >= 6:
            last_hashes = [s.content_hash for s in snapshots[-6:]]
            if len(set(last_hashes)) == 1 and last_hashes[0]:
                detected.append(
                    {
                        **PATTERNS["stale_site"],
                        "siret": siret,
                        "detected_at": snapshots[-1].crawl_date,
                        "details": f"Contenu identique sur {len(last_hashes)} mois",
                    }
                )

        # --- Pattern: activity_decline ---
        # Sentiment decreases for 3 consecutive months
        if len(snapshots) >= 3:
            recent = snapshots[-3:]
            sentiments = [s.sentiment_score for s in recent]
            if all(sentiments[i] > sentiments[i + 1] for i in range(len(sentiments) - 1)):
                if sentiments[0] - sentiments[-1] > 0.3:
                    detected.append(
                        {
                            **PATTERNS["activity_decline"],
                            "siret": siret,
                            "detected_at": snapshots[-1].crawl_date,
                            "details": f"Sentiment: {sentiments[0]:.2f} -> {sentiments[-1]:.2f}",
                        }
                    )

        # --- Pattern: hiring_surge ---
        # Job openings jump from 0 to 5+
        if len(snapshots) >= 2:
            prev = snapshots[-2]
            curr = snapshots[-1]
            if prev.job_openings == 0 and curr.job_openings >= 5:
                detected.append(
                    {
                        **PATTERNS["hiring_surge"],
                        "siret": siret,
                        "detected_at": curr.crawl_date,
                        "details": f"Offres: {prev.job_openings} -> {curr.job_openings}",
                    }
                )

        # --- Pattern: growth_signal ---
        # Employee mentions increase >20%
        if len(snapshots) >= 2:
            prev = snapshots[-2]
            curr = snapshots[-1]
            if prev.employee_mentions and curr.employee_mentions and prev.employee_mentions > 0:
                growth = (curr.employee_mentions - prev.employee_mentions) / prev.employee_mentions
                if growth > 0.2:
                    detected.append(
                        {
                            **PATTERNS["growth_signal"],
                            "siret": siret,
                            "detected_at": curr.crawl_date,
                            "details": f"Employes: {prev.employee_mentions} -> {curr.employee_mentions} (+{growth:.0%})",
                        }
                    )

        # --- Pattern: pivot_detected ---
        # Products/services change by >50%
        if len(snapshots) >= 2:
            prev_prods = set(snapshots[-2].products_services)
            curr_prods = set(snapshots[-1].products_services)
            if prev_prods and curr_prods:
                overlap = len(prev_prods & curr_prods)
                total = len(prev_prods | curr_prods)
                if total > 0 and (overlap / total) < 0.5:
                    detected.append(
                        {
                            **PATTERNS["pivot_detected"],
                            "siret": siret,
                            "detected_at": snapshots[-1].crawl_date,
                            "details": f"Produits: {len(prev_prods)} -> {len(curr_prods)}, overlap {overlap}/{total}",
                        }
                    )

        return detected

    # --- Private methods ---

    async def _call_llm(self, prompt: str) -> str:
        """Call Ollama LLM and return response text."""
        response = await self._client.post(
            f"{self._ollama_url}/api/generate",
            json={
                "model": self._model,
                "system": self.EXTRACT_SYSTEM,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 4096,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")

    def _parse_json(self, text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling common issues."""
        # Remove markdown code blocks if present
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:])
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        # Handle thinking tags from qwen3.5
        if "<think>" in text:
            # Extract content after </think>
            parts = text.split("</think>")
            if len(parts) > 1:
                text = parts[-1].strip()

        # Try to find JSON object in text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"[crawl_intel] JSON parse error: {e}")
            logger.debug(f"[crawl_intel] Raw LLM output: {text[:200]}")
            return {}
