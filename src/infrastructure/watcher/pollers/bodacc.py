"""BODACC poller for the watcher daemon.

Polls for new legal announcements (creations, radiations, etc.)
"""

from datetime import date, timedelta

from ...dashboard.models import Alert, AlertSource, AlertType
from ...datasources.adapters.bodacc import BodaccAdapter
from .base import BasePoller


class BodaccPoller(BasePoller):
    """Poller for BODACC announcements.

    Checks for new company creations, radiations, and other legal events.
    """

    source = "bodacc"
    default_interval = 6 * 3600  # 6 hours

    # Map BODACC types to AlertType
    TYPE_MAP = {
        "creation": AlertType.CREATION,
        "imm": AlertType.CREATION,
        "radiation": AlertType.RADIATION,
        "rad": AlertType.RADIATION,
        "modification": AlertType.MODIFICATION,
        "mod": AlertType.MODIFICATION,
        "vente": AlertType.VENTE,
        "vte": AlertType.VENTE,
    }

    def __init__(self):
        super().__init__()
        self.adapter = BodaccAdapter()

    async def poll(self, keywords: list[str]) -> list[Alert]:
        """Poll BODACC for new announcements matching keywords.

        Args:
            keywords: Keywords to filter announcements

        Returns:
            List of alerts for new announcements
        """
        alerts = []

        # Search for recent announcements (last 7 days)
        date_from = (date.today() - timedelta(days=7)).isoformat()

        # If we have keywords, search for each one
        if keywords:
            for keyword in keywords:
                results = await self.adapter.search(
                    {
                        "nom": keyword,
                        "date_from": date_from,
                        "limit": 50,
                    }
                )
                alerts.extend(self._results_to_alerts(results))
        else:
            # No keywords, just get recent announcements
            results = await self.adapter.search(
                {
                    "date_from": date_from,
                    "limit": 100,
                }
            )
            alerts.extend(self._results_to_alerts(results))

        # Deduplicate by unique key (siren + date + type)
        seen = set()
        unique_alerts = []
        for alert in alerts:
            key = (alert.title, alert.url)
            if key not in seen:
                seen.add(key)
                unique_alerts.append(alert)

        self.logger.info(f"BODACC poll: found {len(unique_alerts)} alerts")
        return unique_alerts

    def _results_to_alerts(self, results: list[dict]) -> list[Alert]:
        """Convert BODACC results to Alert objects."""
        alerts = []

        for result in results:
            # Determine alert type
            bodacc_type = result.get("type", "")
            alert_type = self.TYPE_MAP.get(bodacc_type, AlertType.CREATION)

            # Build title
            nom = result.get("nom", "Entreprise inconnue")
            type_label = result.get("type_label", bodacc_type)
            ville = result.get("ville", "")

            title = f"{type_label}: {nom} ({ville})" if ville else f"{type_label}: {nom}"

            # Build content
            content_parts = []
            if result.get("departement"):
                content_parts.append(f"Département: {result['departement']}")
            if result.get("tribunal"):
                content_parts.append(f"Tribunal: {result['tribunal']}")
            if result.get("contenu"):
                content_parts.append(result["contenu"][:500])

            content = "\n".join(content_parts) if content_parts else None

            alert = Alert(
                source=AlertSource.BODACC,
                type=alert_type,
                title=title,
                content=content,
                url=result.get("url"),
                data={
                    "siren": result.get("siren"),
                    "date_publication": result.get("date_publication"),
                    "numero_annonce": result.get("numero_annonce"),
                    "departement": result.get("numero_departement"),
                    "ville": result.get("ville"),
                },
            )
            alerts.append(alert)

        return alerts

    async def poll_by_type(self, event_type: str, keywords: list[str] = None) -> list[Alert]:
        """Poll for specific event type.

        Args:
            event_type: Type of event (creation, radiation, modification)
            keywords: Optional keywords to filter

        Returns:
            List of alerts
        """
        date_from = (date.today() - timedelta(days=7)).isoformat()

        query = {
            "type": event_type,
            "date_from": date_from,
            "limit": 100,
        }

        results = await self.adapter.search(query)

        # Filter by keywords if provided
        if keywords:
            results = self.filter_by_keywords(
                results,
                keywords,
                ["nom", "contenu", "ville", "departement"],
            )

        return self._results_to_alerts(results)

    async def poll_by_department(self, departement: str, keywords: list[str] = None) -> list[Alert]:
        """Poll for announcements in a specific department.

        Args:
            departement: Department code (e.g., "59" for Nord)
            keywords: Optional keywords to filter

        Returns:
            List of alerts
        """
        date_from = (date.today() - timedelta(days=7)).isoformat()

        results = await self.adapter.search(
            {
                "departement": departement,
                "date_from": date_from,
                "limit": 100,
            }
        )

        if keywords:
            results = self.filter_by_keywords(
                results,
                keywords,
                ["nom", "contenu"],
            )

        return self._results_to_alerts(results)
