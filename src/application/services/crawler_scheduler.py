"""Crawler Scheduler Service.

Intègre AdaptiveCrawler avec APScheduler pour le crawling automatique des sources.
"""

from datetime import datetime
from typing import Any

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from src.infrastructure.crawler.adaptive_crawler import AdaptiveCrawler
from src.infrastructure.crawler.events import CrawlerCallback, CrawlerEvent

# Import alert service
try:
    from src.application.services.alert_service import AlertType, get_alert_service
    ALERTS_ENABLED = True
except ImportError:
    ALERTS_ENABLED = False


# Sources officielles françaises à crawler
FRENCH_DATA_SOURCES = [
    # === HAUTE PRIORITÉ - Données entreprises ===
    {
        "source_id": "sirene_api",
        "url": "https://api.insee.fr/entreprises/sirene/V3.11/siret",
        "source_type": "api",
        "requires_js": False,
        "priority": "high",
        "rate_limit": 30,
    },
    {
        "source_id": "bodacc_api",
        "url": "https://bodacc-datadila.opendatasoft.com/api/records/1.0/search",
        "source_type": "api",
        "requires_js": False,
        "priority": "high",
    },
    {
        "source_id": "boamp_api",
        "url": "https://boamp-datadila.opendatasoft.com/api/records/1.0/search",
        "source_type": "api",
        "requires_js": False,
        "priority": "high",
    },
    # === MOYENNE PRIORITÉ - Données économiques ===
    {
        "source_id": "dvf_api",
        "url": "https://api.cquest.org/dvf",
        "source_type": "api",
        "requires_js": False,
        "priority": "medium",
    },
    {
        "source_id": "france_travail_api",
        "url": "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
        "source_type": "api",
        "requires_js": False,
        "priority": "medium",
    },
    {
        "source_id": "subventions_api",
        "url": "https://aides-territoires.beta.gouv.fr/api/aids/",
        "source_type": "api",
        "requires_js": False,
        "priority": "medium",
    },
    {
        "source_id": "insee_local_api",
        "url": "https://api.insee.fr/donnees-locales/V0.1",
        "source_type": "api",
        "requires_js": False,
        "priority": "medium",
    },
    {
        "source_id": "ofgl_api",
        "url": "https://data.ofgl.fr/api/records/1.0/search",
        "source_type": "api",
        "requires_js": False,
        "priority": "medium",
    },
    # === RSS FEEDS ===
    {
        "source_id": "legifrance_rss",
        "url": "https://www.legifrance.gouv.fr/eli/jo/rss",
        "source_type": "rss",
        "requires_js": False,
        "priority": "medium",
    },
    {
        "source_id": "economie_gouv_rss",
        "url": "https://www.economie.gouv.fr/rss/actualites",
        "source_type": "rss",
        "requires_js": False,
        "priority": "medium",
    },
    # === BASSE PRIORITÉ - Référentiels ===
    {
        "source_id": "geo_api",
        "url": "https://geo.api.gouv.fr/communes",
        "source_type": "api",
        "requires_js": False,
        "priority": "low",
    },
    {
        "source_id": "ban_api",
        "url": "https://api-adresse.data.gouv.fr/search?q=test",
        "source_type": "api",
        "requires_js": False,
        "priority": "low",
    },
    {
        "source_id": "data_gouv",
        "url": "https://www.data.gouv.fr/api/1/datasets",
        "source_type": "api",
        "requires_js": False,
        "priority": "low",
    },
    # === SITES JS (Playwright) ===
    {
        "source_id": "annuaire_entreprises",
        "url": "https://annuaire-entreprises.data.gouv.fr",
        "source_type": "web",
        "requires_js": True,
        "priority": "low",
    },
]


class CrawlerScheduler:
    """Scheduler pour le crawling automatique.

    Fonctionnalités:
    - Crawling périodique des sources françaises
    - Intégration avec TAJINE via events
    - Adaptation automatique des priorités (MAB)
    """

    _instance: "CrawlerScheduler | None" = None

    def __init__(self):
        self._scheduler: AsyncIOScheduler | None = None
        self._crawler: AdaptiveCrawler | None = None
        self._is_running = False
        self._crawl_results: list[dict[str, Any]] = []

    @classmethod
    def get_instance(cls) -> "CrawlerScheduler":
        """Singleton."""
        if cls._instance is None:
            cls._instance = CrawlerScheduler()
        return cls._instance

    async def start(self) -> None:
        """Démarrer le crawler scheduler."""
        if self._is_running:
            return

        # Initialiser le crawler avec les sources françaises
        self._crawler = AdaptiveCrawler(
            sources=FRENCH_DATA_SOURCES,
            exploration_param=2.0,
            max_concurrent=5,
            enable_playwright=True,
        )

        # Enregistrer le handler d'events
        self._crawler.on_event(self._handle_crawler_event)

        # Initialiser APScheduler
        self._scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Paris"))

        # Job de crawling toutes les heures (sources haute priorité)
        self._scheduler.add_job(
            self._crawl_high_priority,
            trigger=IntervalTrigger(hours=1),
            id="crawl_high_priority",
            replace_existing=True,
        )

        # Job de crawling quotidien (toutes les sources)
        self._scheduler.add_job(
            self._crawl_all,
            trigger=CronTrigger(hour=2, minute=0),  # 02:00
            id="crawl_daily_all",
            replace_existing=True,
        )

        # Job de nettoyage hebdomadaire
        self._scheduler.add_job(
            self._cleanup_old_data,
            trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="cleanup_weekly",
            replace_existing=True,
        )

        self._scheduler.start()
        self._is_running = True

        logger.info(
            f"CrawlerScheduler started with {len(FRENCH_DATA_SOURCES)} sources"
        )

    async def stop(self) -> None:
        """Arrêter le crawler scheduler."""
        if self._scheduler and self._is_running:
            self._scheduler.shutdown(wait=False)

        if self._crawler:
            await self._crawler.close()

        self._is_running = False
        logger.info("CrawlerScheduler stopped")

    def _handle_crawler_event(self, callback: CrawlerCallback) -> None:
        """Handler pour les events du crawler."""
        if callback.event == CrawlerEvent.SOURCE_CHANGED:
            logger.info(
                f"Source {callback.source_id} changed - new data available"
            )
            # Stocker pour TAJINE
            self._crawl_results.append({
                "source_id": callback.source_id,
                "url": callback.url,
                "data": callback.data,
                "quality_score": callback.quality_score,
                "timestamp": datetime.now().isoformat(),
            })

            # Déclencher les alertes
            if ALERTS_ENABLED and callback.data:
                self._process_alerts(callback.source_id, callback.data)

        elif callback.event == CrawlerEvent.SOURCE_ERROR:
            logger.warning(
                f"Source {callback.source_id} error: {callback.error}"
            )

    def _process_alerts(self, source_id: str, data: Any) -> None:
        """Traiter les données pour les alertes."""
        if not ALERTS_ENABLED:
            return

        alert_service = get_alert_service()

        # Mapper source_id vers AlertType
        source_type_map = {
            "bodacc_api": AlertType.LEGAL_ANNOUNCEMENT,
            "boamp_api": AlertType.MARKET_OPPORTUNITY,
            "sirene_api": AlertType.ENTERPRISE_CREATION,
            "subventions_api": AlertType.SUBSIDY_AVAILABLE,
            "france_travail_api": AlertType.JOB_MARKET_CHANGE,
            "dvf_api": AlertType.REAL_ESTATE_CHANGE,
        }

        alert_type = source_type_map.get(source_id)
        if not alert_type:
            return

        # Traiter les données (peut être une liste ou un dict)
        items = data if isinstance(data, list) else [data]

        for item in items[:10]:  # Limiter à 10 items par batch
            if isinstance(item, dict):
                try:
                    alert_service.process_data(
                        data=item,
                        source_id=source_id,
                        data_type=alert_type,
                        territory=item.get("department") or item.get("codeDepartement"),
                    )
                except Exception as e:
                    logger.debug(f"Alert processing error: {e}")

    async def _crawl_high_priority(self) -> None:
        """Crawler les sources haute priorité."""
        if not self._crawler:
            return

        logger.info("Starting high priority crawl")

        high_priority_ids = [
            s["source_id"]
            for s in FRENCH_DATA_SOURCES
            if s.get("priority") == "high"
        ]

        for source_id in high_priority_ids:
            try:
                await self._crawler.crawl_source(source_id)
            except Exception as e:
                logger.error(f"Error crawling {source_id}: {e}")

        logger.info(f"High priority crawl completed: {len(high_priority_ids)} sources")

    async def _crawl_all(self) -> None:
        """Crawler toutes les sources."""
        if not self._crawler:
            return

        logger.info("Starting full crawl")

        results = await self._crawler.crawl_batch(batch_size=len(FRENCH_DATA_SOURCES))

        logger.info(f"Full crawl completed: {len(results)} results")

    async def _cleanup_old_data(self) -> None:
        """Nettoyer les anciennes données."""
        # Garder seulement les 1000 derniers résultats
        if len(self._crawl_results) > 1000:
            self._crawl_results = self._crawl_results[-1000:]

        logger.info("Cleanup completed")

    # --- API publique ---

    async def crawl_now(self, source_id: str | None = None) -> list[dict[str, Any]]:
        """Lancer un crawl immédiat."""
        if not self._crawler:
            await self.start()

        if source_id:
            result = await self._crawler.crawl_source(source_id)
            return [result] if result else []
        else:
            return await self._crawler.crawl_batch()

    def get_recent_results(self, limit: int = 100) -> list[dict[str, Any]]:
        """Récupérer les résultats récents."""
        return self._crawl_results[-limit:]

    def get_source_stats(self) -> dict[str, Any]:
        """Statistiques sur les sources."""
        if not self._crawler:
            return {}

        return {
            "total_sources": len(FRENCH_DATA_SOURCES),
            "results_cached": len(self._crawl_results),
            "is_running": self._is_running,
        }

    def update_relevance(self, source_id: str, was_useful: bool) -> None:
        """Feedback depuis TAJINE sur l'utilité d'une source."""
        if self._crawler:
            self._crawler.update_relevance(source_id, was_useful)


def get_crawler_scheduler() -> CrawlerScheduler:
    """Get singleton."""
    return CrawlerScheduler.get_instance()
