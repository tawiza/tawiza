"""BOAMP poller for the watcher daemon.

Polls for new public procurement announcements.
"""

from datetime import date, timedelta

from ...dashboard.models import Alert, AlertSource, AlertType
from ...datasources.adapters.boamp import BoampAdapter
from .base import BasePoller


class BoampPoller(BasePoller):
    """Poller for BOAMP public procurement announcements.

    Checks for new calls for tenders, award notices, etc.
    """

    source = "boamp"
    default_interval = 6 * 3600  # 6 hours

    # Map BOAMP types to AlertType
    TYPE_MAP = {
        "appel_offre": AlertType.MARCHE,
        "marche": AlertType.MARCHE,
        "attribution": AlertType.ATTRIBUTION,
    }

    def __init__(self):
        super().__init__()
        self.adapter = BoampAdapter()

    async def poll(self, keywords: list[str]) -> list[Alert]:
        """Poll BOAMP for new announcements matching keywords.

        Args:
            keywords: Keywords to filter announcements

        Returns:
            List of alerts for new announcements
        """
        alerts = []
        date_from = (date.today() - timedelta(days=7)).isoformat()

        if keywords:
            for keyword in keywords:
                results = await self.adapter.search({
                    "keywords": keyword,
                    "date_from": date_from,
                    "limit": 50,
                })
                alerts.extend(self._results_to_alerts(results))
        else:
            # Get recent calls for tenders
            results = await self.adapter.search({
                "type": "appel_offre",
                "date_from": date_from,
                "limit": 100,
            })
            alerts.extend(self._results_to_alerts(results))

        # Deduplicate
        seen = set()
        unique_alerts = []
        for alert in alerts:
            key = (alert.title, alert.url)
            if key not in seen:
                seen.add(key)
                unique_alerts.append(alert)

        self.logger.info(f"BOAMP poll: found {len(unique_alerts)} alerts")
        return unique_alerts

    def _results_to_alerts(self, results: list[dict]) -> list[Alert]:
        """Convert BOAMP results to Alert objects."""
        alerts = []

        for result in results:
            # Determine alert type
            boamp_type = result.get("type", "")
            alert_type = self.TYPE_MAP.get(boamp_type, AlertType.MARCHE)

            # Build title
            objet = result.get("objet", "Marché public")[:100]
            acheteur = result.get("nom_acheteur", "")

            title = f"{objet} - {acheteur}" if acheteur else objet

            # Build content
            content_parts = []
            if result.get("type_label"):
                content_parts.append(f"Type: {result['type_label']}")
            if result.get("famille"):
                content_parts.append(f"Famille: {result['famille']}")
            if result.get("procedure"):
                content_parts.append(f"Procédure: {result['procedure']}")
            if result.get("date_limite_reponse"):
                content_parts.append(f"Date limite: {result['date_limite_reponse']}")
            if result.get("cpv_label"):
                content_parts.append(f"CPV: {result['cpv_label']}")

            content = "\n".join(content_parts) if content_parts else None

            alert = Alert(
                source=AlertSource.BOAMP,
                type=alert_type,
                title=title[:200],  # Limit title length
                content=content,
                url=result.get("url"),
                data={
                    "id": result.get("id"),
                    "reference": result.get("reference"),
                    "acheteur": result.get("nom_acheteur"),
                    "date_publication": result.get("date_publication"),
                    "date_limite": result.get("date_limite_reponse"),
                    "departement": result.get("departement"),
                    "cpv_code": result.get("cpv_code"),
                    "type_marche": result.get("type_marche"),
                },
            )
            alerts.append(alert)

        return alerts

    async def poll_opportunities(self, keywords: list[str] = None, departements: list[str] = None) -> list[Alert]:
        """Poll specifically for business opportunities.

        Args:
            keywords: Keywords to filter
            departements: Department codes to filter

        Returns:
            List of alerts for opportunities
        """
        results = await self.adapter.search_opportunities(
            keywords=keywords[0] if keywords else None,
            departements=departements,
            limit=100,
        )

        # Filter by additional keywords if provided
        if keywords and len(keywords) > 1:
            results = self.filter_by_keywords(
                results,
                keywords,
                ["objet", "cpv_label", "nom_acheteur"],
            )

        return self._results_to_alerts(results)
