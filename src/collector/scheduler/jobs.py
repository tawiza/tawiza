"""
Scheduler for periodic signal collection using APScheduler.

Runs as part of the FastAPI backend lifecycle:
- API collectors (France Travail, SIRENE): daily at 6h + 18h
- Web crawlers (presse locale pipeline): every 4h
- Cross-source detection: daily at 7h (after API collection)
- Network watchdog: every 15 min (auto-triggers collection on network recovery)
"""

import os
from datetime import date, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from ..collectors.api.caf import CAFCollector
from ..collectors.api.commoncrawl import CommonCrawlCollector
from ..collectors.api.dgfip import DGFiPCollector
from ..collectors.api.dvf import DVFCollector
from ..collectors.api.education_nationale import EducationNationaleCollector
from ..collectors.api.france_travail import FranceTravailCollector
from ..collectors.api.google_trends import GoogleTrendsCollector
from ..collectors.api.sirene import SireneCollector
from ..collectors.api.sitadel import SitadelCollector
from ..collectors.api.urssaf import URSSAFCollector
from ..storage.repository import SignalRepository


def _load_credentials() -> dict[str, str]:
    """Load API credentials from .env file or environment."""
    creds = {}
    env_file = str(Path(__file__).resolve().parents[2] / ".env")

    # Try reading .env directly (dotenv has issues in some contexts)
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key in (
                    "FRANCE_TRAVAIL_CLIENT_ID",
                    "FRANCE_TRAVAIL_CLIENT_SECRET",
                ):
                    creds[key] = value

    # Environment overrides .env
    for key in ("FRANCE_TRAVAIL_CLIENT_ID", "FRANCE_TRAVAIL_CLIENT_SECRET"):
        env_val = os.getenv(key)
        if env_val:
            creds[key] = env_val

    return creds


# Departments to monitor (top 15 French metropolitan areas + IDF)
MONITORED_DEPARTMENTS = [
    "75",  # Paris
    "92",  # Hauts-de-Seine
    "93",  # Seine-Saint-Denis
    "94",  # Val-de-Marne
    "78",  # Yvelines
    "91",  # Essonne
    "95",  # Val-d'Oise
    "13",  # Bouches-du-Rhône (Marseille)
    "69",  # Rhône (Lyon)
    "31",  # Haute-Garonne (Toulouse)
    "33",  # Gironde (Bordeaux)
    "59",  # Nord (Lille)
    "44",  # Loire-Atlantique (Nantes)
    "67",  # Bas-Rhin (Strasbourg)
    "34",  # Hérault (Montpellier)
    "35",  # Ille-et-Vilaine (Rennes)
    "06",  # Alpes-Maritimes (Nice)
    "38",  # Isère (Grenoble)
]


class CollectorScheduler:
    """Manages scheduled collection jobs."""

    def __init__(self, database_url: str | None = None) -> None:
        self._db_url = database_url or os.getenv(
            "COLLECTOR_DATABASE_URL",
            "postgresql+asyncpg://localhost:5433/tawiza",
        )
        self._scheduler = AsyncIOScheduler()
        self._repo = SignalRepository(self._db_url)
        self._departments = MONITORED_DEPARTMENTS
        self._network_was_down = False  # will be set True by watchdog if network is actually down
        self._last_successful_collection: date | None = None

        # Load credentials
        creds = _load_credentials()

        # Collectors
        self._collectors = {
            "france_travail": FranceTravailCollector(
                client_id=creds.get("FRANCE_TRAVAIL_CLIENT_ID"),
                client_secret=creds.get("FRANCE_TRAVAIL_CLIENT_SECRET"),
            ),
            "sirene": SireneCollector(),
            "sitadel": SitadelCollector(),
            "caf": CAFCollector(),
            "dgfip": DGFiPCollector(),
            "dvf": DVFCollector(),
            "urssaf": URSSAFCollector(),
            "education_nationale": EducationNationaleCollector(),
            "google_trends": None,  # lazy-loaded (pytrends dependency)
            "presse_locale": None,  # lazy-loaded (heavier dependencies)
            "commoncrawl": None,  # lazy-loaded (heavy: LLM + WARC)
        }

    def _get_google_trends_collector(self):
        """Lazy-load Google Trends collector (pytrends dependency)."""
        if self._collectors["google_trends"] is None:
            self._collectors["google_trends"] = GoogleTrendsCollector()
        return self._collectors["google_trends"]

    def _get_presse_collector(self):
        """Lazy-load presse locale collector."""
        if self._collectors["presse_locale"] is None:
            from ..collectors.crawlers.presse_locale import PresseLocaleCollector

            self._collectors["presse_locale"] = PresseLocaleCollector()
        return self._collectors["presse_locale"]

    def _get_commoncrawl_collector(self) -> CommonCrawlCollector:
        """Lazy-load Common Crawl collector (heavy: LLM + WARC downloads)."""
        if self._collectors["commoncrawl"] is None:
            self._collectors["commoncrawl"] = CommonCrawlCollector(
                max_enterprises=5,  # 5 per dept per run (~40min max)
                months_back=12,
            )
        return self._collectors["commoncrawl"]

    async def _run_collector(self, name: str, code_dept: str | None = None) -> int:
        """Run a single collector and store results. Returns signal count."""
        if name == "presse_locale":
            collector = self._get_presse_collector()
        elif name == "commoncrawl":
            collector = self._get_commoncrawl_collector()
        elif name == "google_trends":
            collector = self._get_google_trends_collector()
        else:
            collector = self._collectors.get(name)

        if not collector:
            logger.error(f"[scheduler] Unknown collector: {name}")
            return 0

        try:
            since = date.today() - timedelta(days=7)
            signals = await collector.run(code_dept=code_dept, since=since)

            if signals:
                batch = [s.to_dict() for s in signals]
                count = await self._repo.insert_signals_batch(batch)
                logger.info(f"[scheduler] {name}: stored {count} signals (dept={code_dept})")
                return count
            return 0
        except Exception as e:
            logger.error(f"[scheduler] {name} failed (dept={code_dept}): {e}")
            return 0

    async def _run_api_collectors(self) -> None:
        """Run all API collectors for all departments."""
        total = 0
        api_collectors = [
            "france_travail",
            "sirene",
            "sitadel",
            "caf",
            "dgfip",
            "dvf",
            "urssaf",
            "education_nationale",
            "google_trends",
        ]
        for dept in self._departments:
            for name in api_collectors:
                count = await self._run_collector(name, code_dept=dept)
                total += count

        if total > 0:
            self._last_successful_collection = date.today()
            logger.info(f"[scheduler] API collection complete: {total} total signals")
        else:
            logger.warning("[scheduler] API collection: 0 signals (network issue?)")

    async def _run_crawling_pipeline(self) -> None:
        """Run the full crawling pipeline (Trafilatura + NLP)."""
        try:
            from ..crawling.pipeline import CrawlingPipeline

            pipeline = CrawlingPipeline(use_spacy=True, max_workers=3)
            signals = await pipeline.run()

            if signals:
                batch = [s.to_dict() for s in signals]
                count = await self._repo.insert_signals_batch(batch)
                logger.info(f"[scheduler] Crawling pipeline: stored {count} signals")
            else:
                logger.info("[scheduler] Crawling pipeline: 0 signals")

            await pipeline.close()
        except Exception as e:
            logger.error(f"[scheduler] Crawling pipeline failed: {e}")

    async def _run_crawlintel(self) -> None:
        """Run Common Crawl web intelligence for prioritized departments.

        Heavy job (~8min per enterprise): runs weekly on a subset of departments.
        Rotates through departments to cover all over time.
        """
        # Rotate: pick 3 departments per run (covers all 18 in ~6 weeks)

        week_num = date.today().isocalendar()[1]
        start_idx = (week_num * 3) % len(self._departments)
        target_depts = []
        for i in range(3):
            target_depts.append(self._departments[(start_idx + i) % len(self._departments)])

        total = 0
        collector = self._get_commoncrawl_collector()

        for dept in target_depts:
            try:
                signals = await collector.run(code_dept=dept)
                if signals:
                    batch = [s.to_dict() for s in signals]
                    count = await self._repo.insert_signals_batch(batch)
                    total += count
                    logger.info(f"[scheduler] CrawlIntel dept={dept}: {count} signals stored")
            except Exception as e:
                logger.error(f"[scheduler] CrawlIntel dept={dept} failed: {e}")

        await collector.close()
        # Re-null so next run creates fresh instance
        self._collectors["commoncrawl"] = None

        if total > 0:
            logger.info(f"[scheduler] CrawlIntel complete: {total} signals from {target_depts}")
        else:
            logger.info(f"[scheduler] CrawlIntel: 0 signals for {target_depts}")

    async def _run_cross_source_detection(self) -> None:
        """Run cross-source anomaly detection."""
        try:
            from ..crawling.crossref import run_cross_source_detection

            micro_signals = await run_cross_source_detection(
                self._repo, window_days=7, baseline_days=30
            )

            if micro_signals:
                logger.info(
                    f"[scheduler] Cross-source: {len(micro_signals)} micro-signals detected"
                )
                for ms in micro_signals:
                    logger.info(
                        f"  🔔 {ms.signal_type} dept={ms.code_dept} "
                        f"score={ms.score} sources={ms.sources}"
                    )
                    # Store as anomaly
                    try:
                        await self._repo.insert_anomaly(**ms.to_anomaly_dict())
                    except Exception as e:
                        logger.debug(f"[scheduler] Anomaly insert error: {e}")
            else:
                logger.info("[scheduler] Cross-source: no micro-signals detected")
        except Exception as e:
            logger.error(f"[scheduler] Cross-source detection failed: {e}")

    async def _network_watchdog(self) -> None:
        """Check network connectivity and trigger collection on recovery."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.head("https://api.insee.fr/")
                network_up = resp.status_code < 500
        except Exception:
            network_up = False

        if network_up and self._network_was_down:
            logger.info("[scheduler] 🌐 Network recovered! Triggering collection...")
            self._network_was_down = False
            # Run collection immediately on network recovery
            await self._run_api_collectors()
            await self._run_crawling_pipeline()
        elif not network_up:
            if not self._network_was_down:
                logger.warning("[scheduler] ⚠️ Network down")
            self._network_was_down = True

    def setup_jobs(self) -> None:
        """Configure all scheduled jobs."""
        # API collectors: daily at 6h and 18h
        self._scheduler.add_job(
            self._run_api_collectors,
            CronTrigger(hour="6,18", minute=0),
            id="api_collectors",
            name="API Collectors (SIRENE, France Travail)",
            replace_existing=True,
        )

        # Crawling pipeline: every 4 hours
        self._scheduler.add_job(
            self._run_crawling_pipeline,
            CronTrigger(hour="*/4", minute=30),
            id="crawling_pipeline",
            name="Crawling Pipeline (Presse locale + NLP)",
            replace_existing=True,
        )

        # Cross-source detection: daily at 7h (after API collection)
        self._scheduler.add_job(
            self._run_cross_source_detection,
            CronTrigger(hour=7, minute=0),
            id="cross_source_detection",
            name="Cross-Source Micro-Signal Detection",
            replace_existing=True,
        )

        # CrawlIntel (Common Crawl): weekly on Sundays at 2h
        # Heavy job (~8min/enterprise × 5 enterprises × 3 depts = ~2h max)
        self._scheduler.add_job(
            self._run_crawlintel,
            CronTrigger(day_of_week="sun", hour=2, minute=0),
            id="crawlintel",
            name="CrawlIntel (Common Crawl Web Intelligence)",
            replace_existing=True,
        )

        # Network watchdog: every 15 minutes
        self._scheduler.add_job(
            self._network_watchdog,
            IntervalTrigger(minutes=15),
            id="network_watchdog",
            name="Network Watchdog",
            replace_existing=True,
        )

        logger.info(
            f"[scheduler] Jobs configured: "
            f"{len(self._departments)} departments monitored, "
            f"5 scheduled jobs"
        )

    async def start(self) -> None:
        """Start the scheduler."""
        await self._repo.init_db()
        self.setup_jobs()
        self._scheduler.start()
        logger.info("[scheduler] ✅ Started (watchdog will check network in 1 min)")

    async def stop(self) -> None:
        """Stop the scheduler and cleanup."""
        self._scheduler.shutdown()
        for collector in self._collectors.values():
            if collector and hasattr(collector, "close"):
                await collector.close()
        await self._repo.close()
        logger.info("[scheduler] Stopped")

    async def run_now(self, collector_name: str, code_dept: str | None = None) -> int:
        """Run a collector immediately. Returns signal count."""
        if collector_name == "crawling_pipeline":
            await self._run_crawling_pipeline()
            return 0
        if collector_name == "cross_source":
            await self._run_cross_source_detection()
            return 0
        if collector_name == "crawlintel":
            await self._run_crawlintel()
            return 0

        return await self._run_collector(collector_name, code_dept=code_dept)

    def get_status(self) -> dict:
        """Get scheduler status for API."""
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None,
                }
            )

        return {
            "running": self._scheduler.running,
            "network_up": not self._network_was_down,
            "departments": self._departments,
            "last_collection": str(self._last_successful_collection)
            if self._last_successful_collection
            else None,
            "jobs": jobs,
        }
