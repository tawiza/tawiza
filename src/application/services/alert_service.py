"""Alert Service - Notifications sur changements significatifs.

Détecte et notifie les changements importants dans les données territoriales.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from loguru import logger


class AlertType(Enum):
    """Types d'alertes."""
    ENTERPRISE_CREATION = "enterprise_creation"
    ENTERPRISE_CLOSURE = "enterprise_closure"
    MARKET_OPPORTUNITY = "market_opportunity"
    LEGAL_ANNOUNCEMENT = "legal_announcement"
    ECONOMIC_INDICATOR = "economic_indicator"
    SUBSIDY_AVAILABLE = "subsidy_available"
    JOB_MARKET_CHANGE = "job_market_change"
    REAL_ESTATE_CHANGE = "real_estate_change"


class AlertSeverity(Enum):
    """Sévérité de l'alerte."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Statut de l'alerte."""
    NEW = "new"
    READ = "read"
    ARCHIVED = "archived"


@dataclass
class Alert:
    """Une alerte territoriale."""
    id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    territory: str | None  # Code département
    sector: str | None  # Code NAF
    data: dict[str, Any]
    created_at: datetime
    status: AlertStatus = AlertStatus.NEW
    source_id: str | None = None  # Source du crawler


@dataclass
class AlertRule:
    """Règle de déclenchement d'alerte."""
    id: str
    name: str
    alert_type: AlertType
    condition: Callable[[dict], bool]
    severity: AlertSeverity
    territories: list[str] | None = None  # None = tous
    sectors: list[str] | None = None  # None = tous
    enabled: bool = True


class AlertService:
    """Service de gestion des alertes territoriales."""

    _instance: "AlertService | None" = None

    def __init__(self):
        self._alerts: list[Alert] = []
        self._rules: list[AlertRule] = []
        self._handlers: list[Callable[[Alert], None]] = []
        self._setup_default_rules()

    @classmethod
    def get_instance(cls) -> "AlertService":
        """Singleton."""
        if cls._instance is None:
            cls._instance = AlertService()
        return cls._instance

    def _setup_default_rules(self) -> None:
        """Configure les règles par défaut."""
        # Règle: Nouvelle entreprise dans secteur tech
        self.add_rule(AlertRule(
            id="tech_creation",
            name="Création entreprise tech",
            alert_type=AlertType.ENTERPRISE_CREATION,
            condition=lambda d: d.get("naf_code", "").startswith("62"),
            severity=AlertSeverity.INFO,
            sectors=["62.01Z", "62.02A", "62.02B", "62.03Z"],
        ))

        # Règle: Fermeture entreprise majeure
        self.add_rule(AlertRule(
            id="major_closure",
            name="Fermeture entreprise majeure",
            alert_type=AlertType.ENTERPRISE_CLOSURE,
            condition=lambda d: d.get("employees", 0) > 50,
            severity=AlertSeverity.WARNING,
        ))

        # Règle: Marché public important
        self.add_rule(AlertRule(
            id="major_market",
            name="Marché public > 100k€",
            alert_type=AlertType.MARKET_OPPORTUNITY,
            condition=lambda d: d.get("amount", 0) > 100000,
            severity=AlertSeverity.INFO,
        ))

        # Règle: Subvention disponible
        self.add_rule(AlertRule(
            id="new_subsidy",
            name="Nouvelle subvention disponible",
            alert_type=AlertType.SUBSIDY_AVAILABLE,
            condition=lambda d: d.get("status") == "open",
            severity=AlertSeverity.INFO,
        ))

        # Règle: Variation emploi significative
        self.add_rule(AlertRule(
            id="job_variation",
            name="Variation emploi > 10%",
            alert_type=AlertType.JOB_MARKET_CHANGE,
            condition=lambda d: abs(d.get("variation_pct", 0)) > 10,
            severity=AlertSeverity.WARNING,
        ))

        logger.info(f"AlertService: {len(self._rules)} règles par défaut configurées")

    def add_rule(self, rule: AlertRule) -> None:
        """Ajouter une règle d'alerte."""
        self._rules.append(rule)

    def on_alert(self, handler: Callable[[Alert], None]) -> None:
        """Enregistrer un handler de notification."""
        self._handlers.append(handler)

    def process_data(
        self,
        data: dict[str, Any],
        source_id: str,
        data_type: AlertType,
        territory: str | None = None,
    ) -> list[Alert]:
        """Traiter des données et déclencher les alertes si nécessaire."""
        triggered_alerts = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            if rule.alert_type != data_type:
                continue

            # Filtrer par territoire
            if rule.territories and territory and territory not in rule.territories:
                continue

            # Filtrer par secteur
            if rule.sectors and data.get("naf_code") not in rule.sectors:
                continue

            # Évaluer la condition
            try:
                if rule.condition(data):
                    alert = self._create_alert(data, source_id, rule, territory)
                    triggered_alerts.append(alert)
                    self._alerts.append(alert)
                    self._notify(alert)
            except Exception as e:
                logger.warning(f"Erreur évaluation règle {rule.id}: {e}")

        return triggered_alerts

    def _create_alert(
        self,
        data: dict[str, Any],
        source_id: str,
        rule: AlertRule,
        territory: str | None,
    ) -> Alert:
        """Créer une alerte."""
        return Alert(
            id=str(uuid4()),
            type=rule.alert_type,
            severity=rule.severity,
            title=self._generate_title(data, rule),
            description=self._generate_description(data, rule),
            territory=territory or data.get("department"),
            sector=data.get("naf_code"),
            data=data,
            created_at=datetime.now(),
            source_id=source_id,
        )

    def _generate_title(self, data: dict[str, Any], rule: AlertRule) -> str:
        """Générer le titre de l'alerte."""
        templates = {
            AlertType.ENTERPRISE_CREATION: f"Nouvelle entreprise: {data.get('name', 'N/A')}",
            AlertType.ENTERPRISE_CLOSURE: f"Fermeture: {data.get('name', 'N/A')}",
            AlertType.MARKET_OPPORTUNITY: f"Marché: {data.get('title', 'N/A')[:50]}",
            AlertType.LEGAL_ANNOUNCEMENT: f"Annonce légale: {data.get('type', 'N/A')}",
            AlertType.SUBSIDY_AVAILABLE: f"Subvention: {data.get('name', 'N/A')[:50]}",
            AlertType.JOB_MARKET_CHANGE: f"Emploi {data.get('territory', '')}: {data.get('variation_pct', 0):+.1f}%",
            AlertType.REAL_ESTATE_CHANGE: f"Immobilier {data.get('territory', '')}: {data.get('variation_pct', 0):+.1f}%",
        }
        return templates.get(rule.alert_type, rule.name)

    def _generate_description(self, data: dict[str, Any], rule: AlertRule) -> str:
        """Générer la description de l'alerte."""
        parts = [f"Règle: {rule.name}"]

        if data.get("department"):
            parts.append(f"Département: {data['department']}")
        if data.get("city"):
            parts.append(f"Ville: {data['city']}")
        if data.get("naf_code"):
            parts.append(f"Secteur: {data['naf_code']}")
        if data.get("amount"):
            parts.append(f"Montant: {data['amount']:,.0f}€")

        return " | ".join(parts)

    def _notify(self, alert: Alert) -> None:
        """Notifier les handlers."""
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Erreur notification alerte: {e}")

        logger.info(
            f"🔔 Alerte [{alert.severity.value}] {alert.type.value}: {alert.title}"
        )

    # === API publique ===

    def get_alerts(
        self,
        status: AlertStatus | None = None,
        alert_type: AlertType | None = None,
        territory: str | None = None,
        limit: int = 100,
    ) -> list[Alert]:
        """Récupérer les alertes avec filtres."""
        alerts = self._alerts

        if status:
            alerts = [a for a in alerts if a.status == status]
        if alert_type:
            alerts = [a for a in alerts if a.type == alert_type]
        if territory:
            alerts = [a for a in alerts if a.territory == territory]

        return sorted(alerts, key=lambda a: a.created_at, reverse=True)[:limit]

    def mark_read(self, alert_id: str) -> bool:
        """Marquer une alerte comme lue."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.READ
                return True
        return False

    def archive(self, alert_id: str) -> bool:
        """Archiver une alerte."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.status = AlertStatus.ARCHIVED
                return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Statistiques des alertes."""
        return {
            "total": len(self._alerts),
            "new": len([a for a in self._alerts if a.status == AlertStatus.NEW]),
            "by_type": {
                t.value: len([a for a in self._alerts if a.type == t])
                for t in AlertType
            },
            "by_severity": {
                s.value: len([a for a in self._alerts if a.severity == s])
                for s in AlertSeverity
            },
            "rules_count": len(self._rules),
        }


def get_alert_service() -> AlertService:
    """Get singleton."""
    return AlertService.get_instance()
