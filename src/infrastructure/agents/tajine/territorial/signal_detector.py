"""
Signal Detector - Détection de micro-signaux économiques territoriaux.

Ce module implémente la détection de patterns économiques basés sur le croisement
de multiples sources de données (SIRENE, BODACC, France Travail, DVF, etc.)
pour identifier des tendances AVANT qu'elles soient visibles dans les stats officielles.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class SignalSeverity(StrEnum):
    """Niveau de sévérité d'un signal détecté."""

    CRITICAL = "critical"  # 🔴 Action immédiate requise
    WARNING = "warning"  # 🟡 À surveiller
    INFO = "info"  # 🟢 Information
    OPPORTUNITY = "opportunity"  # 🔵 Opportunité détectée


class SignalCategory(StrEnum):
    """Catégorie de signal."""

    CRISIS = "crisis"  # Crise / Alerte
    GROWTH = "growth"  # Dynamisme / Croissance
    MUTATION = "mutation"  # Transformation / Mutation
    EMPLOYMENT = "employment"  # Emploi / Social
    PUBLIC_MARKET = "public_market"  # Marchés publics
    INNOVATION = "innovation"  # Innovation


@dataclass
class SignalIndicator:
    """Un indicateur individuel contribuant à un signal."""

    name: str
    source: str  # sirene, bodacc, france_travail, dvf, etc.
    value: float
    threshold: float
    direction: str  # "up", "down", "stable"
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_triggered(self) -> bool:
        """Vérifie si l'indicateur dépasse son seuil."""
        if self.direction == "up":
            return self.value > self.threshold
        elif self.direction == "down":
            return self.value < self.threshold
        return abs(self.value - self.threshold) < 0.01


@dataclass
class DetectedSignal:
    """Un signal détecté avec tous ses détails."""

    pattern_id: str
    pattern_name: str
    category: SignalCategory
    severity: SignalSeverity
    territory_code: str
    territory_name: str
    confidence: float  # 0-1
    indicators: list[SignalIndicator]
    description: str
    recommendation: str
    detected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire pour sérialisation."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "category": self.category.value,
            "severity": self.severity.value,
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "confidence": self.confidence,
            "indicators": [
                {
                    "name": ind.name,
                    "source": ind.source,
                    "value": ind.value,
                    "threshold": ind.threshold,
                    "direction": ind.direction,
                    "triggered": ind.is_triggered,
                }
                for ind in self.indicators
            ],
            "description": self.description,
            "recommendation": self.recommendation,
            "detected_at": self.detected_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SignalPattern:
    """Définition d'un pattern de signal à détecter."""

    id: str
    name: str
    category: SignalCategory
    description: str
    indicators_config: list[dict[str, Any]]  # Config des indicateurs requis
    min_indicators_triggered: int  # Nombre minimum d'indicateurs pour déclencher
    severity_rules: dict[int, SignalSeverity]  # nb indicateurs -> sévérité
    recommendation_template: str

    def evaluate_severity(self, triggered_count: int) -> SignalSeverity:
        """Détermine la sévérité basée sur le nombre d'indicateurs déclenchés."""
        for threshold, severity in sorted(self.severity_rules.items(), reverse=True):
            if triggered_count >= threshold:
                return severity
        return SignalSeverity.INFO


class SignalDetector:
    """
    Détecteur de micro-signaux économiques territoriaux.

    Utilise les datasources pour collecter des indicateurs et les croise
    selon des patterns prédéfinis pour détecter des tendances précoces.
    """

    def __init__(
        self,
        datasource_manager: Any = None,  # DataSourceManager
        cache_ttl_minutes: int = 60,
    ) -> None:
        """
        Initialise le détecteur.

        Args:
            datasource_manager: Gestionnaire des sources de données
            cache_ttl_minutes: Durée de vie du cache en minutes
        """
        self.datasource_manager = datasource_manager
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._patterns: dict[str, SignalPattern] = {}
        self._cache: dict[str, tuple[datetime, Any]] = {}

        # Charger les patterns par défaut
        self._load_default_patterns()

    def _load_default_patterns(self) -> None:
        """Charge les patterns de détection par défaut."""

        # Pattern 1: Crise sectorielle locale
        self._patterns["crisis_sectoral"] = SignalPattern(
            id="crisis_sectoral",
            name="Crise sectorielle locale",
            category=SignalCategory.CRISIS,
            description="Signaux convergents de difficultés dans un secteur sur le territoire",
            indicators_config=[
                {
                    "name": "job_offers_decline",
                    "source": "france_travail",
                    "metric": "job_offers_variation",
                    "direction": "down",
                    "threshold": -0.15,  # -15%
                    "weight": 1.0,
                },
                {
                    "name": "bodacc_procedures",
                    "source": "bodacc",
                    "metric": "collective_procedures_count",
                    "direction": "up",
                    "threshold": 1.5,  # +50% vs moyenne
                    "weight": 1.2,
                },
                {
                    "name": "sirene_closures",
                    "source": "sirene",
                    "metric": "closure_rate",
                    "direction": "up",
                    "threshold": 0.08,  # >8%
                    "weight": 1.0,
                },
            ],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.CRITICAL, 2: SignalSeverity.WARNING},
            recommendation_template="Surveiller de près le secteur {sector} sur {territory}. "
            "Envisager des actions de soutien aux entreprises fragilisées.",
        )

        # Pattern 2: Zone en décollage
        self._patterns["growth_takeoff"] = SignalPattern(
            id="growth_takeoff",
            name="Zone en décollage",
            category=SignalCategory.GROWTH,
            description="Signaux convergents de dynamisme économique",
            indicators_config=[
                {
                    "name": "sirene_creations",
                    "source": "sirene",
                    "metric": "creation_rate",
                    "direction": "up",
                    "threshold": 0.12,  # >12%
                    "weight": 1.0,
                },
                {
                    "name": "job_offers_growth",
                    "source": "france_travail",
                    "metric": "job_offers_variation",
                    "direction": "up",
                    "threshold": 0.10,  # +10%
                    "weight": 1.0,
                },
                {
                    "name": "dvf_transactions",
                    "source": "dvf",
                    "metric": "transaction_volume_variation",
                    "direction": "up",
                    "threshold": 0.15,  # +15%
                    "weight": 0.8,
                },
                {
                    "name": "dvf_prices",
                    "source": "dvf",
                    "metric": "price_variation",
                    "direction": "up",
                    "threshold": 0.05,  # +5%
                    "weight": 0.6,
                },
            ],
            min_indicators_triggered=2,
            severity_rules={
                4: SignalSeverity.OPPORTUNITY,
                3: SignalSeverity.OPPORTUNITY,
                2: SignalSeverity.INFO,
            },
            recommendation_template="Territoire {territory} en croissance. "
            "Opportunité d'accompagner le développement et d'attirer de nouveaux acteurs.",
        )

        # Pattern 3: Désertification commerciale
        self._patterns["commercial_desert"] = SignalPattern(
            id="commercial_desert",
            name="Désertification commerciale",
            category=SignalCategory.CRISIS,
            description="Fermetures de commerces en centre-ville",
            indicators_config=[
                {
                    "name": "bodacc_commerce_closures",
                    "source": "bodacc",
                    "metric": "commerce_closures_rate",
                    "direction": "up",
                    "threshold": 0.10,  # >10%
                    "weight": 1.2,
                },
                {
                    "name": "sirene_commerce_stock",
                    "source": "sirene",
                    "metric": "commerce_stock_variation",
                    "direction": "down",
                    "threshold": -0.05,  # -5%
                    "weight": 1.0,
                },
                {
                    "name": "job_offers_retail",
                    "source": "france_travail",
                    "metric": "retail_job_offers_variation",
                    "direction": "down",
                    "threshold": -0.20,  # -20%
                    "weight": 0.8,
                },
            ],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.CRITICAL, 2: SignalSeverity.WARNING},
            recommendation_template="Risque de dévitalisation commerciale sur {territory}. "
            "Actions recommandées: aide à la reprise, animation commerciale, urbanisme.",
        )

        # Pattern 4: Tension métiers
        self._patterns["job_tension"] = SignalPattern(
            id="job_tension",
            name="Tension métiers",
            category=SignalCategory.EMPLOYMENT,
            description="Pénurie de main d'œuvre sur certains métiers",
            indicators_config=[
                {
                    "name": "offers_vs_seekers",
                    "source": "france_travail",
                    "metric": "offers_to_seekers_ratio",
                    "direction": "up",
                    "threshold": 1.5,  # 1.5 offre par demandeur
                    "weight": 1.2,
                },
                {
                    "name": "offer_duration",
                    "source": "france_travail",
                    "metric": "avg_offer_duration_days",
                    "direction": "up",
                    "threshold": 45,  # >45 jours
                    "weight": 1.0,
                },
                {
                    "name": "salary_increase",
                    "source": "france_travail",
                    "metric": "avg_salary_variation",
                    "direction": "up",
                    "threshold": 0.08,  # >8%
                    "weight": 0.8,
                },
            ],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.WARNING, 2: SignalSeverity.INFO},
            recommendation_template="Tension sur les métiers {jobs} dans {territory}. "
            "Actions: formation, attractivité, recrutement hors zone.",
        )

        # Pattern 5: Opportunité marchés publics
        self._patterns["public_market_opportunity"] = SignalPattern(
            id="public_market_opportunity",
            name="Opportunité marchés publics",
            category=SignalCategory.PUBLIC_MARKET,
            description="Hausse des marchés publics dans un secteur avec peu d'acteurs locaux",
            indicators_config=[
                {
                    "name": "boamp_volume",
                    "source": "boamp",
                    "metric": "market_volume_variation",
                    "direction": "up",
                    "threshold": 0.20,  # +20%
                    "weight": 1.0,
                },
                {
                    "name": "local_companies_ratio",
                    "source": "sirene",
                    "metric": "local_companies_in_sector",
                    "direction": "down",
                    "threshold": 5,  # <5 entreprises locales
                    "weight": 1.2,
                },
            ],
            min_indicators_triggered=2,
            severity_rules={2: SignalSeverity.OPPORTUNITY},
            recommendation_template="Opportunité: marchés publics en hausse dans {sector} "
            "avec peu d'acteurs locaux sur {territory}. Potentiel d'implantation.",
        )

        # Pattern 6: Cluster émergent
        self._patterns["emerging_cluster"] = SignalPattern(
            id="emerging_cluster",
            name="Cluster émergent",
            category=SignalCategory.GROWTH,
            description="Concentration d'activités dans un secteur innovant",
            indicators_config=[
                {
                    "name": "sirene_sector_concentration",
                    "source": "sirene",
                    "metric": "sector_creation_concentration",
                    "direction": "up",
                    "threshold": 2.0,  # 2x la moyenne nationale
                    "weight": 1.2,
                },
                {
                    "name": "specialized_jobs",
                    "source": "france_travail",
                    "metric": "specialized_job_offers_growth",
                    "direction": "up",
                    "threshold": 0.25,  # +25%
                    "weight": 1.0,
                },
                {
                    "name": "inpi_patents",
                    "source": "inpi",
                    "metric": "patents_in_domain",
                    "direction": "up",
                    "threshold": 0.30,  # +30%
                    "weight": 1.5,
                },
            ],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.OPPORTUNITY, 2: SignalSeverity.INFO},
            recommendation_template="Cluster {sector} en émergence sur {territory}. "
            "Opportunité de structuration et d'accompagnement de la filière.",
        )

        # Pattern 7: Mutation territoriale
        self._patterns["territorial_mutation"] = SignalPattern(
            id="territorial_mutation",
            name="Mutation centre-périphérie",
            category=SignalCategory.MUTATION,
            description="Déplacement d'activité du centre vers la périphérie",
            indicators_config=[
                {
                    "name": "center_closures",
                    "source": "bodacc",
                    "metric": "center_closures_rate",
                    "direction": "up",
                    "threshold": 0.08,  # >8%
                    "weight": 1.0,
                },
                {
                    "name": "periphery_creations",
                    "source": "sirene",
                    "metric": "periphery_creation_rate",
                    "direction": "up",
                    "threshold": 0.15,  # >15%
                    "weight": 1.0,
                },
                {
                    "name": "dvf_periphery",
                    "source": "dvf",
                    "metric": "periphery_price_growth",
                    "direction": "up",
                    "threshold": 0.10,  # >10%
                    "weight": 0.8,
                },
            ],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.WARNING, 2: SignalSeverity.INFO},
            recommendation_template="Mutation territoriale en cours sur {territory}. "
            "Vigilance sur la dévitalisation du centre, accompagner la transition.",
        )

        # Pattern 8: Vieillissement entrepreneurial
        self._patterns["entrepreneurial_aging"] = SignalPattern(
            id="entrepreneurial_aging",
            name="Vieillissement entrepreneurial",
            category=SignalCategory.MUTATION,
            description="Enjeu de transmission d'entreprises",
            indicators_config=[
                {
                    "name": "senior_leaders",
                    "source": "sirene",
                    "metric": "leaders_over_55_ratio",
                    "direction": "up",
                    "threshold": 0.35,  # >35%
                    "weight": 1.2,
                },
                {
                    "name": "transmission_offers",
                    "source": "cession_pme",
                    "metric": "transmission_offers_count",
                    "direction": "up",
                    "threshold": 1.2,  # +20% vs année précédente
                    "weight": 1.0,
                },
                {
                    "name": "creation_vs_transmission",
                    "source": "sirene",
                    "metric": "creations_to_transmissions_ratio",
                    "direction": "down",
                    "threshold": 3.0,  # <3 créations par transmission
                    "weight": 0.8,
                },
            ],
            min_indicators_triggered=2,
            severity_rules={3: SignalSeverity.WARNING, 2: SignalSeverity.INFO},
            recommendation_template="Enjeu de transmission sur {territory}. "
            "{count} entreprises potentiellement concernées. Actions: accompagnement cédants/repreneurs.",
        )

        logger.info(f"Loaded {len(self._patterns)} default signal patterns")

    def register_pattern(self, pattern: SignalPattern) -> None:
        """Enregistre un nouveau pattern de détection."""
        self._patterns[pattern.id] = pattern
        logger.info(f"Registered signal pattern: {pattern.id}")

    def get_patterns(self) -> list[SignalPattern]:
        """Retourne tous les patterns enregistrés."""
        return list(self._patterns.values())

    async def _fetch_indicator_data(
        self,
        territory_code: str,
        indicator_config: dict[str, Any],
        period_months: int = 12,
    ) -> SignalIndicator | None:
        """
        Récupère les données pour un indicateur donné.

        Args:
            territory_code: Code INSEE du territoire
            indicator_config: Configuration de l'indicateur
            period_months: Période d'analyse en mois

        Returns:
            SignalIndicator si données disponibles, None sinon
        """
        if not self.datasource_manager:
            logger.warning("No datasource manager configured")
            return None

        source = indicator_config["source"]
        metric = indicator_config["metric"]
        cache_key = f"{territory_code}:{source}:{metric}"

        # Vérifier le cache
        if cache_key in self._cache:
            cached_time, cached_value = self._cache[cache_key]
            if datetime.utcnow() - cached_time < self.cache_ttl:
                return cached_value

        try:
            # Récupérer les données via le datasource manager
            adapter = self.datasource_manager.adapters.get(source)
            if not adapter:
                logger.warning(f"Adapter not found: {source}")
                return None

            # Construire la requête selon la source
            query = {
                "territory_code": territory_code,
                "metric": metric,
                "period_months": period_months,
            }

            results = await adapter.search(query)

            if not results:
                return None

            # Calculer la valeur de l'indicateur
            value = self._compute_metric_value(results, metric)

            indicator = SignalIndicator(
                name=indicator_config["name"],
                source=source,
                value=value,
                threshold=indicator_config["threshold"],
                direction=indicator_config["direction"],
                weight=indicator_config.get("weight", 1.0),
                metadata={"raw_count": len(results)},
            )

            # Mettre en cache
            self._cache[cache_key] = (datetime.utcnow(), indicator)

            return indicator

        except Exception as e:
            logger.error(f"Error fetching indicator {metric} from {source}: {e}")
            return None

    def _compute_metric_value(
        self,
        results: list[dict[str, Any]],
        metric: str,
    ) -> float:
        """
        Calcule la valeur d'une métrique à partir des résultats bruts.

        Cette méthode devrait être étendue selon les métriques supportées.
        """
        # Implémentation simplifiée - à enrichir selon les métriques
        if not results:
            return 0.0

        if "variation" in metric:
            # Pour les variations, calculer le taux de changement
            if len(results) >= 2:
                old_count = results[0].get("count", 1)
                new_count = results[-1].get("count", 1)
                if old_count > 0:
                    return (new_count - old_count) / old_count
            return 0.0

        if "rate" in metric:
            # Pour les taux, chercher la valeur directe
            return results[0].get("rate", 0.0)

        if "ratio" in metric:
            return results[0].get("ratio", 0.0)

        if "count" in metric:
            return float(results[0].get("count", 0))

        # Par défaut, retourner la première valeur trouvée
        return float(results[0].get("value", 0.0))

    async def detect_signals(
        self,
        territory_code: str,
        territory_name: str,
        pattern_ids: list[str] | None = None,
        period_months: int = 12,
    ) -> list[DetectedSignal]:
        """
        Détecte les signaux pour un territoire donné.

        Args:
            territory_code: Code INSEE du territoire
            territory_name: Nom du territoire
            pattern_ids: Liste des patterns à évaluer (None = tous)
            period_months: Période d'analyse en mois

        Returns:
            Liste des signaux détectés
        """
        detected_signals: list[DetectedSignal] = []
        patterns_to_check = (
            [self._patterns[pid] for pid in pattern_ids if pid in self._patterns]
            if pattern_ids
            else list(self._patterns.values())
        )

        for pattern in patterns_to_check:
            try:
                signal = await self._evaluate_pattern(
                    pattern, territory_code, territory_name, period_months
                )
                if signal:
                    detected_signals.append(signal)
            except Exception as e:
                logger.error(f"Error evaluating pattern {pattern.id}: {e}")

        # Trier par sévérité (critical > warning > info > opportunity)
        severity_order = {
            SignalSeverity.CRITICAL: 0,
            SignalSeverity.WARNING: 1,
            SignalSeverity.INFO: 3,
            SignalSeverity.OPPORTUNITY: 2,
        }
        detected_signals.sort(key=lambda s: severity_order.get(s.severity, 99))

        logger.info(
            f"Detected {len(detected_signals)} signals for {territory_name} ({territory_code})"
        )

        return detected_signals

    async def _evaluate_pattern(
        self,
        pattern: SignalPattern,
        territory_code: str,
        territory_name: str,
        period_months: int,
    ) -> DetectedSignal | None:
        """
        Évalue un pattern sur un territoire.

        Returns:
            DetectedSignal si le pattern est déclenché, None sinon
        """
        # Récupérer tous les indicateurs en parallèle
        indicator_tasks = [
            self._fetch_indicator_data(territory_code, config, period_months)
            for config in pattern.indicators_config
        ]
        indicators = await asyncio.gather(*indicator_tasks)

        # Filtrer les indicateurs valides
        valid_indicators = [ind for ind in indicators if ind is not None]

        if not valid_indicators:
            return None

        # Compter les indicateurs déclenchés
        triggered_indicators = [ind for ind in valid_indicators if ind.is_triggered]
        triggered_count = len(triggered_indicators)

        if triggered_count < pattern.min_indicators_triggered:
            return None

        # Calculer la confiance
        confidence = triggered_count / len(pattern.indicators_config)

        # Ajuster par les poids
        total_weight = sum(ind.weight for ind in triggered_indicators)
        max_weight = sum(config.get("weight", 1.0) for config in pattern.indicators_config)
        weighted_confidence = total_weight / max_weight if max_weight > 0 else confidence

        # Déterminer la sévérité
        severity = pattern.evaluate_severity(triggered_count)

        # Générer la description
        description = self._generate_description(pattern, triggered_indicators, territory_name)

        # Générer la recommandation
        recommendation = pattern.recommendation_template.format(
            territory=territory_name,
            sector="",  # À enrichir avec le secteur détecté
            jobs="",  # À enrichir avec les métiers concernés
            count=triggered_count,
        )

        return DetectedSignal(
            pattern_id=pattern.id,
            pattern_name=pattern.name,
            category=pattern.category,
            severity=severity,
            territory_code=territory_code,
            territory_name=territory_name,
            confidence=weighted_confidence,
            indicators=valid_indicators,
            description=description,
            recommendation=recommendation,
            metadata={
                "triggered_count": triggered_count,
                "total_indicators": len(pattern.indicators_config),
                "period_months": period_months,
            },
        )

    def _generate_description(
        self,
        pattern: SignalPattern,
        triggered_indicators: list[SignalIndicator],
        territory_name: str,
    ) -> str:
        """Génère une description textuelle du signal détecté."""
        parts = [f"{pattern.name} détecté sur {territory_name}."]

        parts.append("Indicateurs déclenchés:")
        for ind in triggered_indicators:
            direction_text = "en hausse" if ind.direction == "up" else "en baisse"
            parts.append(f"- {ind.name} ({ind.source}): {ind.value:.2f} {direction_text}")

        return " ".join(parts)

    async def compute_territorial_indices(
        self,
        territory_code: str,
        territory_name: str,
    ) -> dict[str, float]:
        """
        Calcule les indices synthétiques pour un territoire.

        Returns:
            Dictionnaire des indices (vitality, resilience, attractiveness, innovation, transition)
        """
        # Implémentation simplifiée - à enrichir avec les vrais calculs
        indices = {
            "vitality": 0.0,
            "resilience": 0.0,
            "attractiveness": 0.0,
            "innovation": 0.0,
            "transition": 0.0,
        }

        # TODO: Implémenter les calculs réels basés sur les formules documentées
        # dans DATASOURCES_CATALOG.md

        logger.info(f"Computed indices for {territory_name}: {indices}")
        return indices


# Factory function pour créer un détecteur configuré
def create_signal_detector(
    datasource_manager: Any = None,
    additional_patterns: list[SignalPattern] | None = None,
) -> SignalDetector:
    """
    Crée un SignalDetector configuré.

    Args:
        datasource_manager: Gestionnaire des sources de données
        additional_patterns: Patterns additionnels à enregistrer

    Returns:
        SignalDetector configuré
    """
    detector = SignalDetector(datasource_manager=datasource_manager)

    if additional_patterns:
        for pattern in additional_patterns:
            detector.register_pattern(pattern)

    return detector
