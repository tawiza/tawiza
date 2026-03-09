"""GDELT poller for the watcher daemon.

Polls for news articles matching keywords.
"""

from ...dashboard.models import Alert, AlertSource, AlertType
from ...datasources.adapters.gdelt import GdeltAdapter
from .base import BasePoller


class GdeltPoller(BasePoller):
    """Poller for GDELT news articles.

    Checks for news articles matching keywords in French media.
    """

    source = "gdelt"
    default_interval = 2 * 3600  # 2 hours (news updates frequently)

    def __init__(self):
        super().__init__()
        self.adapter = GdeltAdapter()

    async def poll(self, keywords: list[str]) -> list[Alert]:
        """Poll GDELT for news articles matching keywords.

        Args:
            keywords: Keywords to filter articles

        Returns:
            List of alerts for new articles
        """
        alerts = []

        if keywords:
            # Search for each keyword
            for keyword in keywords:
                results = await self.adapter.search({
                    "keywords": keyword,
                    "country": "FR",
                    "language": "French",
                    "days": 3,  # More recent for news
                    "limit": 30,
                })
                alerts.extend(self._results_to_alerts(results, keyword))
        else:
            # Default: French tech/business news
            results = await self.adapter.search({
                "keywords": "startup entreprise innovation",
                "country": "FR",
                "language": "French",
                "days": 3,
                "limit": 50,
            })
            alerts.extend(self._results_to_alerts(results))

        # Deduplicate by URL
        seen = set()
        unique_alerts = []
        for alert in alerts:
            if alert.url not in seen:
                seen.add(alert.url)
                unique_alerts.append(alert)

        self.logger.info(f"GDELT poll: found {len(unique_alerts)} alerts")
        return unique_alerts

    def _results_to_alerts(self, results: list[dict], matched_keyword: str = None) -> list[Alert]:
        """Convert GDELT results to Alert objects."""
        alerts = []

        for result in results:
            title = result.get("title", "Article sans titre")
            domain = result.get("domain", "")

            # Build content
            content_parts = []
            if domain:
                content_parts.append(f"Source: {domain}")
            if result.get("language"):
                content_parts.append(f"Langue: {result['language']}")
            if result.get("tone"):
                tone = result["tone"]
                tone_label = "positif" if tone > 0 else "négatif" if tone < 0 else "neutre"
                content_parts.append(f"Ton: {tone_label} ({tone:.1f})")
            if matched_keyword:
                content_parts.append(f"Mot-clé: {matched_keyword}")

            content = "\n".join(content_parts) if content_parts else None

            alert = Alert(
                source=AlertSource.GDELT,
                type=AlertType.NEWS,
                title=title[:200],  # Limit title length
                content=content,
                url=result.get("url"),
                data={
                    "domain": domain,
                    "language": result.get("language"),
                    "country": result.get("country"),
                    "seendate": result.get("seendate"),
                    "tone": result.get("tone"),
                    "socialimage": result.get("socialimage"),
                    "matched_keyword": matched_keyword,
                },
            )
            alerts.append(alert)

        return alerts

    async def poll_company_news(self, company_name: str, days: int = 7) -> list[Alert]:
        """Poll for news about a specific company.

        Args:
            company_name: Company name to search
            days: Days to look back

        Returns:
            List of alerts for company news
        """
        results = await self.adapter.search_company_mentions(
            company_name=company_name,
            days=days,
            limit=30,
        )
        return self._results_to_alerts(results, matched_keyword=company_name)

    async def poll_sector_news(self, sector: str, days: int = 3) -> list[Alert]:
        """Poll for news about a specific sector.

        Args:
            sector: Sector/industry to search (e.g., "intelligence artificielle")
            days: Days to look back

        Returns:
            List of alerts for sector news
        """
        results = await self.adapter.search({
            "keywords": sector,
            "country": "FR",
            "language": "French",
            "days": days,
            "limit": 50,
        })
        return self._results_to_alerts(results, matched_keyword=sector)
