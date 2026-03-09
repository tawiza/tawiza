"""
Predictive Signals - Détection de signaux avancés pour anticipation économique.

Signaux détectés :
- STRESS_ENTREPRISES : ratio modifications/créations élevé
- HEMORRAGIE : plus de fermetures que de créations
- TENSION_EMPLOI : peu d'offres vs demandeurs
- SECTEUR_CRISE : un secteur spécifique en difficulté
- ACCELERATION_NEGATIVE : tendance qui s'aggrave
- ALERTE_PROCEDURES : hausse des procédures collectives
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger


class SignalSeverity(Enum):
    """Niveau de sévérité d'un signal."""
    INFO = "info"           # Observation, pas d'action requise
    WARNING = "warning"     # À surveiller
    ALERT = "alert"         # Action recommandée
    CRITICAL = "critical"   # Action urgente


class SignalType(Enum):
    """Types de signaux prédictifs."""
    STRESS_ENTREPRISES = "stress_entreprises"
    HEMORRAGIE = "hemorragie"
    TENSION_EMPLOI = "tension_emploi"
    SECTEUR_CRISE = "secteur_crise"
    ACCELERATION_NEGATIVE = "acceleration_negative"
    ALERTE_PROCEDURES = "alerte_procedures"
    BULLE_IMMOBILIERE = "bulle_immobiliere"
    CHOMAGE_CRITIQUE = "chomage_critique"
    # Signaux positifs
    DYNAMISME_EXCEPTIONNEL = "dynamisme_exceptionnel"
    SECTEUR_EMERGENT = "secteur_emergent"
    REPRISE_CONFIRMEE = "reprise_confirmee"


@dataclass
class PredictiveSignal:
    """Un signal prédictif détecté."""
    signal_type: SignalType
    severity: SignalSeverity
    territory_code: str
    territory_name: str
    detected_at: datetime
    
    # Détails
    title: str
    description: str
    value: float  # Valeur du métrique déclencheur
    threshold: float  # Seuil dépassé
    
    # Contexte
    sector: str | None = None  # Code NAF si applicable
    trend: str | None = None  # "rising", "falling", "stable"
    recommendation: str | None = None
    
    # Metadata
    confidence: float = 0.8
    data_sources: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.signal_type.value,
            "severity": self.severity.value,
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "detected_at": self.detected_at.isoformat(),
            "title": self.title,
            "description": self.description,
            "value": round(self.value, 2),
            "threshold": round(self.threshold, 2),
            "sector": self.sector,
            "trend": self.trend,
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 2),
            "data_sources": self.data_sources,
        }


class PredictiveSignalDetector:
    """
    Détecteur de signaux prédictifs pour l'analyse territoriale.
    
    Analyse les métriques et tendances pour détecter des signaux
    d'alerte précoce ou d'opportunité.
    """
    
    # Seuils de détection
    THRESHOLDS = {
        "stress_ratio": 3.0,           # modifications / créations
        "hemorragie_ratio": 1.5,       # fermetures / créations
        "tension_emploi": 0.3,         # offres / demandeurs
        "procedures_variation": 0.5,   # +50% vs période précédente
        "chomage_critique": 12.0,      # Taux de chômage %
        "prix_immo_variation": 0.15,   # +15% vs M-3
        "vitality_drop": 10.0,         # Chute de vitalité en 30j
        "dynamisme_exceptionnel": 70.0, # Vitalité exceptionnelle
    }
    
    def __init__(self):
        self._history_store = None
    
    @property
    def history_store(self):
        """Lazy loading du store d'historique."""
        if self._history_store is None:
            from src.infrastructure.persistence.territorial_history import get_history_store
            self._history_store = get_history_store()
        return self._history_store
    
    async def detect_signals(
        self,
        territory_code: str,
        territory_name: str,
        current_metrics: dict[str, Any],
        sector_analysis: dict[str, Any] | None = None,
    ) -> list[PredictiveSignal]:
        """
        Détecte tous les signaux pour un territoire.
        
        Args:
            territory_code: Code du département
            territory_name: Nom du territoire
            current_metrics: Métriques actuelles (du collector)
            sector_analysis: Analyse sectorielle optionnelle
        
        Returns:
            Liste des signaux détectés
        """
        signals = []
        now = datetime.utcnow()
        
        # Récupérer l'historique pour les tendances
        history = self.history_store.get_history(territory_code, days=90)
        trends = self.history_store.get_trends(territory_code, periods=[7, 30, 90])
        
        # 1. Signal STRESS_ENTREPRISES
        signal = self._check_stress_entreprises(
            territory_code, territory_name, current_metrics, now
        )
        if signal:
            signals.append(signal)
        
        # 2. Signal HEMORRAGIE
        signal = self._check_hemorragie(
            territory_code, territory_name, current_metrics, now
        )
        if signal:
            signals.append(signal)
        
        # 3. Signal CHOMAGE_CRITIQUE
        signal = self._check_chomage_critique(
            territory_code, territory_name, current_metrics, now
        )
        if signal:
            signals.append(signal)
        
        # 4. Signal ACCELERATION_NEGATIVE (si historique disponible)
        if trends:
            signal = self._check_acceleration_negative(
                territory_code, territory_name, trends, now
            )
            if signal:
                signals.append(signal)
        
        # 5. Signal DYNAMISME_EXCEPTIONNEL (positif)
        signal = self._check_dynamisme_exceptionnel(
            territory_code, territory_name, current_metrics, now
        )
        if signal:
            signals.append(signal)
        
        # 6. Signaux sectoriels
        if sector_analysis:
            sector_signals = self._check_sector_signals(
                territory_code, territory_name, sector_analysis, now
            )
            signals.extend(sector_signals)
        
        # Trier par sévérité
        severity_order = {
            SignalSeverity.CRITICAL: 0,
            SignalSeverity.ALERT: 1,
            SignalSeverity.WARNING: 2,
            SignalSeverity.INFO: 3,
        }
        signals.sort(key=lambda s: severity_order[s.severity])
        
        logger.info(f"Detected {len(signals)} signals for {territory_name}")
        return signals
    
    def _check_stress_entreprises(
        self, code: str, name: str, metrics: dict, now: datetime
    ) -> PredictiveSignal | None:
        """Vérifie le stress des entreprises (trop de modifications vs créations)."""
        creations = metrics.get("creations_count", 0) or metrics.get("creations", 0)
        modifications = metrics.get("modifications_count", 0) or metrics.get("modifications", 0)
        
        if creations == 0:
            return None
        
        ratio = modifications / creations
        threshold = self.THRESHOLDS["stress_ratio"]
        
        if ratio >= threshold:
            severity = SignalSeverity.ALERT if ratio >= threshold * 1.5 else SignalSeverity.WARNING
            return PredictiveSignal(
                signal_type=SignalType.STRESS_ENTREPRISES,
                severity=severity,
                territory_code=code,
                territory_name=name,
                detected_at=now,
                title="Stress entreprises élevé",
                description=f"Ratio modifications/créations de {ratio:.1f} (seuil: {threshold}). "
                           f"Les entreprises existantes subissent beaucoup de changements.",
                value=ratio,
                threshold=threshold,
                recommendation="Analyser les types de modifications (changement d'activité, restructuration, etc.)",
                data_sources=["BODACC"],
            )
        return None
    
    def _check_hemorragie(
        self, code: str, name: str, metrics: dict, now: datetime
    ) -> PredictiveSignal | None:
        """Vérifie si les fermetures dépassent les créations."""
        creations = metrics.get("creations_count", 0) or metrics.get("creations", 0)
        closures = metrics.get("closures_count", 0) or metrics.get("closures", 0)
        
        if creations == 0 and closures == 0:
            return None
        
        if creations == 0:
            ratio = float('inf')
        else:
            ratio = closures / creations
        
        threshold = self.THRESHOLDS["hemorragie_ratio"]
        
        if ratio >= threshold:
            severity = SignalSeverity.CRITICAL if ratio >= 2.0 else SignalSeverity.ALERT
            return PredictiveSignal(
                signal_type=SignalType.HEMORRAGIE,
                severity=severity,
                territory_code=code,
                territory_name=name,
                detected_at=now,
                title="Hémorragie entrepreneuriale",
                description=f"Ratio fermetures/créations de {ratio:.1f} (seuil: {threshold}). "
                           f"Le territoire perd plus d'entreprises qu'il n'en crée.",
                value=ratio,
                threshold=threshold,
                trend="falling",
                recommendation="Identifier les secteurs touchés et les causes (concurrence, charges, etc.)",
                data_sources=["BODACC", "SIRENE"],
            )
        return None
    
    def _check_chomage_critique(
        self, code: str, name: str, metrics: dict, now: datetime
    ) -> PredictiveSignal | None:
        """Vérifie si le taux de chômage est critique."""
        unemployment = metrics.get("unemployment_rate", 0)
        threshold = self.THRESHOLDS["chomage_critique"]
        
        if unemployment >= threshold:
            return PredictiveSignal(
                signal_type=SignalType.CHOMAGE_CRITIQUE,
                severity=SignalSeverity.ALERT,
                territory_code=code,
                territory_name=name,
                detected_at=now,
                title="Chômage critique",
                description=f"Taux de chômage de {unemployment:.1f}% (seuil: {threshold}%). "
                           f"Bien au-dessus de la moyenne nationale (~7%).",
                value=unemployment,
                threshold=threshold,
                recommendation="Analyser les secteurs porteurs et les formations disponibles",
                data_sources=["INSEE"],
            )
        return None
    
    def _check_acceleration_negative(
        self, code: str, name: str, trends: dict, now: datetime
    ) -> PredictiveSignal | None:
        """Vérifie si la tendance s'accélère négativement."""
        trend_30d = trends.get("30d", {})
        vitality_change = trend_30d.get("vitality_change", 0)
        threshold = -self.THRESHOLDS["vitality_drop"]
        
        if vitality_change <= threshold:
            return PredictiveSignal(
                signal_type=SignalType.ACCELERATION_NEGATIVE,
                severity=SignalSeverity.ALERT,
                territory_code=code,
                territory_name=name,
                detected_at=now,
                title="Dégradation rapide",
                description=f"La vitalité a chuté de {abs(vitality_change):.1f} points en 30 jours. "
                           f"Tendance préoccupante.",
                value=vitality_change,
                threshold=threshold,
                trend="falling",
                recommendation="Investiguer les causes et comparer avec les territoires voisins",
                data_sources=["Historique interne"],
            )
        return None
    
    def _check_dynamisme_exceptionnel(
        self, code: str, name: str, metrics: dict, now: datetime
    ) -> PredictiveSignal | None:
        """Vérifie si le territoire est exceptionnellement dynamique (signal positif)."""
        vitality = metrics.get("vitality_index", 50)
        threshold = self.THRESHOLDS["dynamisme_exceptionnel"]
        
        if vitality >= threshold:
            return PredictiveSignal(
                signal_type=SignalType.DYNAMISME_EXCEPTIONNEL,
                severity=SignalSeverity.INFO,
                territory_code=code,
                territory_name=name,
                detected_at=now,
                title="🌟 Dynamisme exceptionnel",
                description=f"Indice de vitalité de {vitality:.1f} (seuil: {threshold}). "
                           f"Territoire particulièrement attractif.",
                value=vitality,
                threshold=threshold,
                trend="rising",
                recommendation="Étudier les facteurs de succès pour les répliquer",
                data_sources=["Multi-sources"],
            )
        return None
    
    def _check_sector_signals(
        self, code: str, name: str, sector_analysis: dict, now: datetime
    ) -> list[PredictiveSignal]:
        """Génère des signaux basés sur l'analyse sectorielle."""
        signals = []
        
        # Secteurs en crise
        in_crisis = sector_analysis.get("summary", {}).get("in_crisis", [])
        for sector in in_crisis:
            if sector.get("net_creation", 0) <= -3:  # Au moins 3 fermetures nettes
                signals.append(PredictiveSignal(
                    signal_type=SignalType.SECTEUR_CRISE,
                    severity=SignalSeverity.WARNING,
                    territory_code=code,
                    territory_name=name,
                    detected_at=now,
                    title=f"Secteur en crise : {sector['short_name']}",
                    description=f"Le secteur {sector['name']} affiche un solde de "
                               f"{sector['net_creation']} (créations - fermetures).",
                    value=float(sector["net_creation"]),
                    threshold=-3.0,
                    sector=sector["code"],
                    trend="falling",
                    recommendation=f"Analyser les causes spécifiques au secteur {sector['short_name']}",
                    data_sources=["BODACC"],
                ))
        
        # Secteurs émergents (beaucoup de créations, peu de fermetures)
        top_creators = sector_analysis.get("summary", {}).get("top_creators", [])
        for sector in top_creators[:2]:  # Top 2
            if sector.get("creations", 0) >= 5 and sector.get("closures", 0) == 0:
                signals.append(PredictiveSignal(
                    signal_type=SignalType.SECTEUR_EMERGENT,
                    severity=SignalSeverity.INFO,
                    territory_code=code,
                    territory_name=name,
                    detected_at=now,
                    title=f"🚀 Secteur émergent : {sector['short_name']}",
                    description=f"Le secteur {sector['name']} affiche {sector['creations']} "
                               f"créations sans fermeture.",
                    value=float(sector["creations"]),
                    threshold=5.0,
                    sector=sector["code"],
                    trend="rising",
                    recommendation=f"Opportunité : accompagner le développement du secteur {sector['short_name']}",
                    data_sources=["BODACC"],
                ))
        
        return signals


# Singleton
_detector: PredictiveSignalDetector | None = None


def get_signal_detector() -> PredictiveSignalDetector:
    """Retourne le détecteur singleton."""
    global _detector
    if _detector is None:
        _detector = PredictiveSignalDetector()
    return _detector
