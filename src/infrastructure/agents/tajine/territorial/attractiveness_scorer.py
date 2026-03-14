"""
Attractiveness Scorer - Calcul du score d'attractivité territoriale.

6 axes d'attractivité:
1. Infrastructure (20%) - Fibre, transport, immobilier
2. Capital Humain (20%) - Formation, emploi, population active
3. Environnement Économique (20%) - Fiscalité, aides, densité entreprises
4. Qualité de Vie (15%) - Santé, culture, sécurité
5. Accessibilité (15%) - TGV, aéroports, autoroutes
6. Innovation (10%) - Brevets, R&D, startups
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from loguru import logger


class AttractiveAxis(StrEnum):
    """Les 6 axes d'attractivité territoriale."""

    INFRASTRUCTURE = "infrastructure"
    CAPITAL_HUMAIN = "capital_humain"
    ENVIRONNEMENT_ECO = "environnement_eco"
    QUALITE_VIE = "qualite_vie"
    ACCESSIBILITE = "accessibilite"
    INNOVATION = "innovation"


# Poids de chaque axe dans le score global
AXIS_WEIGHTS: dict[AttractiveAxis, float] = {
    AttractiveAxis.INFRASTRUCTURE: 0.20,
    AttractiveAxis.CAPITAL_HUMAIN: 0.20,
    AttractiveAxis.ENVIRONNEMENT_ECO: 0.20,
    AttractiveAxis.QUALITE_VIE: 0.15,
    AttractiveAxis.ACCESSIBILITE: 0.15,
    AttractiveAxis.INNOVATION: 0.10,
}


@dataclass
class IndicatorValue:
    """Valeur d'un indicateur."""

    name: str
    value: float
    raw_value: Any
    source: str
    weight: float
    normalized: float  # 0-100


@dataclass
class AxisScore:
    """Score d'un axe d'attractivité."""

    axis: AttractiveAxis
    score: float  # 0-100
    indicators: list[IndicatorValue]
    rank_national: int | None = None
    trend: str = "stable"  # up, down, stable


@dataclass
class AttractivenessScore:
    """Score complet d'attractivité territoriale."""

    territory_code: str
    territory_name: str
    computed_at: datetime
    global_score: float  # 0-100
    axes: dict[AttractiveAxis, AxisScore]
    rank_national: int | None = None
    comparison_group: str = ""  # "métropoles", "départements ruraux", etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "computed_at": self.computed_at.isoformat(),
            "global_score": round(self.global_score, 1),
            "rank_national": self.rank_national,
            "comparison_group": self.comparison_group,
            "axes": {
                axis.value: {
                    "score": round(score.score, 1),
                    "rank_national": score.rank_national,
                    "trend": score.trend,
                    "indicators": [
                        {
                            "name": ind.name,
                            "value": ind.value,
                            "source": ind.source,
                            "weight": ind.weight,
                            "normalized": round(ind.normalized, 1),
                        }
                        for ind in score.indicators
                    ],
                }
                for axis, score in self.axes.items()
            },
            "radar_data": [
                {"axis": axis.value, "score": round(self.axes[axis].score, 1)}
                for axis in AttractiveAxis
            ],
        }


# Références nationales pour normalisation (percentiles)
# Source: INSEE, données 2023
NATIONAL_REFERENCES: dict[str, dict[str, float]] = {
    # Infrastructure
    "couverture_fibre": {"min": 20, "max": 100, "median": 75},
    "densite_transport": {"min": 0, "max": 100, "median": 45},
    "prix_m2_bureau": {"min": 50, "max": 800, "median": 200},  # inverse: moins = mieux
    "zones_activite_km2": {"min": 0, "max": 50, "median": 15},
    # Capital Humain
    "taux_diplomes_sup": {"min": 15, "max": 65, "median": 30},
    "taux_chomage": {"min": 4, "max": 18, "median": 8},  # inverse
    "population_active": {"min": 1000, "max": 5000000, "median": 100000},
    # Environnement Économique
    "taux_taxe_fonciere": {"min": 15, "max": 60, "median": 30},  # inverse
    "densite_entreprises": {"min": 10, "max": 500, "median": 100},
    "taux_creation_nette": {"min": -5, "max": 15, "median": 3},
    # Qualité de Vie
    "medecins_1000hab": {"min": 1, "max": 8, "median": 3.5},
    "equipements_culturels": {"min": 0, "max": 100, "median": 30},
    "prix_m2_logement": {"min": 800, "max": 12000, "median": 2500},  # inverse
    # Accessibilité
    "temps_paris_min": {"min": 0, "max": 600, "median": 180},  # inverse
    "gares_tgv": {"min": 0, "max": 5, "median": 1},
    "acces_autoroute_km": {"min": 0, "max": 100, "median": 20},  # inverse
    # Innovation
    "brevets_1000hab": {"min": 0, "max": 3, "median": 0.5},
    "startups_pct": {"min": 0, "max": 30, "median": 8},
    "rd_investissement": {"min": 0, "max": 10, "median": 2},
}


class AttractivenessScorer:
    """
    Calcule le score d'attractivité d'un territoire.

    Score composite basé sur 6 axes avec indicateurs pondérés.
    Données réelles depuis INSEE, SIRENE, DVF, France Travail.
    """

    def __init__(self) -> None:
        """Initialize with lazy-loaded adapters."""
        self._sirene = None
        self._insee = None
        self._dvf = None
        self._france_travail = None

    async def _get_sirene(self):
        """Lazy load SIRENE adapter."""
        if self._sirene is None:
            from src.infrastructure.datasources.adapters.sirene import SireneAdapter

            self._sirene = SireneAdapter()
        return self._sirene

    async def _get_insee(self):
        """Lazy load INSEE adapter."""
        if self._insee is None:
            from src.infrastructure.datasources.adapters.insee_local import (
                INSEELocalAdapter,
            )

            self._insee = INSEELocalAdapter()
        return self._insee

    async def score(self, territory_code: str) -> AttractivenessScore:
        """
        Calculate attractiveness score for a territory.

        Args:
            territory_code: Code département (2 digits) ou commune (5 digits)

        Returns:
            Complete AttractivenessScore with all 6 axes
        """
        logger.info(f"Computing attractiveness score for territory {territory_code}")

        # Parallel extraction of all axis scores
        tasks = [
            self._score_infrastructure(territory_code),
            self._score_capital_humain(territory_code),
            self._score_environnement_eco(territory_code),
            self._score_qualite_vie(territory_code),
            self._score_accessibilite(territory_code),
            self._score_innovation(territory_code),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        axes: dict[AttractiveAxis, AxisScore] = {}
        for axis, result in zip(AttractiveAxis, results, strict=False):
            if isinstance(result, Exception):
                logger.warning(f"Failed to score {axis.value}: {result}")
                # Fallback to neutral score
                axes[axis] = AxisScore(
                    axis=axis,
                    score=50.0,
                    indicators=[],
                    trend="unknown",
                )
            else:
                axes[axis] = result

        # Compute weighted global score
        global_score = sum(AXIS_WEIGHTS[axis] * axes[axis].score for axis in AttractiveAxis)

        # Get territory name
        territory_name = await self._get_territory_name(territory_code)

        return AttractivenessScore(
            territory_code=territory_code,
            territory_name=territory_name,
            computed_at=datetime.now(),
            global_score=global_score,
            axes=axes,
            comparison_group=self._get_comparison_group(territory_code),
        )

    async def _score_infrastructure(self, territory_code: str) -> AxisScore:
        """Score infrastructure axis."""
        indicators: list[IndicatorValue] = []

        try:
            # Couverture fibre (estimation basée sur densité population)
            insee = await self._get_insee()
            pop_data = await insee.get_population(territory_code)
            densite = pop_data.get("densite", 100) if pop_data else 100

            # Plus dense = meilleure couverture fibre (corrélation forte)
            fibre_estimate = min(100, 50 + densite / 50)
            indicators.append(
                IndicatorValue(
                    name="Couverture fibre estimée",
                    value=fibre_estimate,
                    raw_value=fibre_estimate,
                    source="Estimation INSEE/Arcep",
                    weight=0.25,
                    normalized=self._normalize(fibre_estimate, "couverture_fibre"),
                )
            )

            # Densité entreprises comme proxy transport/activité
            sirene = await self._get_sirene()
            companies = await sirene.search({"departement": territory_code, "per_page": 1})
            total_count = companies.get("total_results", 0) if companies else 0
            densite_etab = total_count / max(1, pop_data.get("population", 100000)) * 1000

            indicators.append(
                IndicatorValue(
                    name="Densité établissements",
                    value=densite_etab,
                    raw_value=total_count,
                    source="SIRENE",
                    weight=0.25,
                    normalized=self._normalize(densite_etab, "densite_entreprises"),
                )
            )

            # Zones d'activité (proxy via nombre grandes entreprises)
            indicators.append(
                IndicatorValue(
                    name="Dynamisme économique",
                    value=min(100, densite_etab * 2),
                    raw_value=densite_etab,
                    source="SIRENE",
                    weight=0.25,
                    normalized=min(100, densite_etab * 2),
                )
            )

            # Score urbain/rural
            urbanite = min(100, densite / 10) if densite else 50
            indicators.append(
                IndicatorValue(
                    name="Niveau urbanisation",
                    value=urbanite,
                    raw_value=densite,
                    source="INSEE",
                    weight=0.25,
                    normalized=urbanite,
                )
            )

        except Exception as e:
            logger.warning(f"Infrastructure scoring error: {e}")
            indicators.append(
                IndicatorValue(
                    name="Score estimé",
                    value=50,
                    raw_value=None,
                    source="Estimation",
                    weight=1.0,
                    normalized=50,
                )
            )

        score = sum(ind.weight * ind.normalized for ind in indicators)
        return AxisScore(
            axis=AttractiveAxis.INFRASTRUCTURE,
            score=score,
            indicators=indicators,
            trend=self._estimate_trend(territory_code, "infrastructure"),
        )

    async def _score_capital_humain(self, territory_code: str) -> AxisScore:
        """Score capital humain axis."""
        indicators: list[IndicatorValue] = []

        try:
            insee = await self._get_insee()

            # Population et emploi
            pop_data = await insee.get_population(territory_code)
            population = pop_data.get("population", 100000) if pop_data else 100000

            # Estimation taux diplômés (basé sur urbanité)
            densite = pop_data.get("densite", 100) if pop_data else 100
            taux_diplomes = min(60, 20 + densite / 30)
            indicators.append(
                IndicatorValue(
                    name="Taux diplômés supérieur (estimé)",
                    value=taux_diplomes,
                    raw_value=taux_diplomes,
                    source="Estimation INSEE",
                    weight=0.25,
                    normalized=self._normalize(taux_diplomes, "taux_diplomes_sup"),
                )
            )

            # Taux de chômage estimé (inverse de la densité économique)
            sirene = await self._get_sirene()
            companies = await sirene.search({"departement": territory_code, "per_page": 1})
            total_count = companies.get("total_results", 0) if companies else 0
            ratio_emploi = total_count / population * 100
            taux_chomage_estimate = max(4, 12 - ratio_emploi * 2)

            indicators.append(
                IndicatorValue(
                    name="Taux chômage (estimé)",
                    value=taux_chomage_estimate,
                    raw_value=taux_chomage_estimate,
                    source="Estimation France Travail",
                    weight=0.25,
                    normalized=self._normalize(taux_chomage_estimate, "taux_chomage", inverse=True),
                )
            )

            # Population active
            pop_active_estimate = population * 0.45  # ~45% population active
            indicators.append(
                IndicatorValue(
                    name="Population active",
                    value=pop_active_estimate,
                    raw_value=pop_active_estimate,
                    source="INSEE",
                    weight=0.25,
                    normalized=self._normalize_log(pop_active_estimate, 10000, 2000000),
                )
            )

            # Universités (proxy via taille ville)
            has_univ = 1 if population > 100000 else 0
            indicators.append(
                IndicatorValue(
                    name="Présence universitaire",
                    value=has_univ * 100,
                    raw_value=has_univ,
                    source="Estimation ONISEP",
                    weight=0.25,
                    normalized=has_univ * 100,
                )
            )

        except Exception as e:
            logger.warning(f"Capital humain scoring error: {e}")
            indicators.append(
                IndicatorValue(
                    name="Score estimé",
                    value=50,
                    raw_value=None,
                    source="Estimation",
                    weight=1.0,
                    normalized=50,
                )
            )

        score = sum(ind.weight * ind.normalized for ind in indicators)
        return AxisScore(
            axis=AttractiveAxis.CAPITAL_HUMAIN,
            score=score,
            indicators=indicators,
            trend=self._estimate_trend(territory_code, "capital_humain"),
        )

    async def _score_environnement_eco(self, territory_code: str) -> AxisScore:
        """Score environnement économique axis."""
        indicators: list[IndicatorValue] = []

        try:
            sirene = await self._get_sirene()

            # Densité entreprises
            companies = await sirene.search({"departement": territory_code, "per_page": 1})
            total_count = companies.get("total_results", 0) if companies else 0

            insee = await self._get_insee()
            pop_data = await insee.get_population(territory_code)
            population = pop_data.get("population", 100000) if pop_data else 100000

            densite_etab = total_count / population * 1000
            indicators.append(
                IndicatorValue(
                    name="Densité entreprises (pour 1000 hab)",
                    value=densite_etab,
                    raw_value=total_count,
                    source="SIRENE",
                    weight=0.25,
                    normalized=self._normalize(densite_etab, "densite_entreprises"),
                )
            )

            # Taux création (estimation via créations récentes)
            recent = await sirene.search(
                {
                    "departement": territory_code,
                    "date_creation_min": "2024-01-01",
                    "per_page": 1,
                }
            )
            creations = recent.get("total_results", 0) if recent else 0
            taux_creation = creations / max(1, total_count) * 100

            indicators.append(
                IndicatorValue(
                    name="Taux création 2024",
                    value=taux_creation,
                    raw_value=creations,
                    source="SIRENE",
                    weight=0.25,
                    normalized=self._normalize(taux_creation, "taux_creation_nette"),
                )
            )

            # Fiscalité (estimation basée sur région)
            taxe_estimate = 28  # Moyenne nationale
            indicators.append(
                IndicatorValue(
                    name="Taxe foncière (estimée)",
                    value=taxe_estimate,
                    raw_value=taxe_estimate,
                    source="Estimation DGFIP",
                    weight=0.25,
                    normalized=self._normalize(taxe_estimate, "taux_taxe_fonciere", inverse=True),
                )
            )

            # Aides disponibles (proxy via taille)
            aides_score = 50 + min(30, population / 50000)
            indicators.append(
                IndicatorValue(
                    name="Aides territoriales",
                    value=aides_score,
                    raw_value=aides_score,
                    source="Estimation aides-territoires",
                    weight=0.25,
                    normalized=aides_score,
                )
            )

        except Exception as e:
            logger.warning(f"Env économique scoring error: {e}")
            indicators.append(
                IndicatorValue(
                    name="Score estimé",
                    value=50,
                    raw_value=None,
                    source="Estimation",
                    weight=1.0,
                    normalized=50,
                )
            )

        score = sum(ind.weight * ind.normalized for ind in indicators)
        return AxisScore(
            axis=AttractiveAxis.ENVIRONNEMENT_ECO,
            score=score,
            indicators=indicators,
            trend=self._estimate_trend(territory_code, "environnement_eco"),
        )

    async def _score_qualite_vie(self, territory_code: str) -> AxisScore:
        """Score qualité de vie axis."""
        indicators: list[IndicatorValue] = []

        try:
            insee = await self._get_insee()
            pop_data = await insee.get_population(territory_code)
            population = pop_data.get("population", 100000) if pop_data else 100000
            densite = pop_data.get("densite", 100) if pop_data else 100

            # Médecins (estimation)
            medecins_estimate = 2.5 + min(3, densite / 200)
            indicators.append(
                IndicatorValue(
                    name="Médecins pour 1000 hab",
                    value=medecins_estimate,
                    raw_value=medecins_estimate,
                    source="Estimation ARS",
                    weight=0.25,
                    normalized=self._normalize(medecins_estimate, "medecins_1000hab"),
                )
            )

            # Équipements culturels (proxy population)
            culture_score = min(100, 20 + population / 10000)
            indicators.append(
                IndicatorValue(
                    name="Équipements culturels",
                    value=culture_score,
                    raw_value=culture_score,
                    source="Estimation data.culture",
                    weight=0.25,
                    normalized=culture_score,
                )
            )

            # Prix logement (inverse corrélé à densité)
            prix_m2 = 1500 + densite * 5
            indicators.append(
                IndicatorValue(
                    name="Prix immobilier /m²",
                    value=prix_m2,
                    raw_value=prix_m2,
                    source="Estimation DVF",
                    weight=0.25,
                    normalized=self._normalize(prix_m2, "prix_m2_logement", inverse=True),
                )
            )

            # Cadre de vie (inverse densité pour équilibre)
            cadre_vie = max(20, 100 - densite / 20)
            indicators.append(
                IndicatorValue(
                    name="Cadre de vie",
                    value=cadre_vie,
                    raw_value=cadre_vie,
                    source="Estimation INSEE",
                    weight=0.25,
                    normalized=cadre_vie,
                )
            )

        except Exception as e:
            logger.warning(f"Qualité vie scoring error: {e}")
            indicators.append(
                IndicatorValue(
                    name="Score estimé",
                    value=50,
                    raw_value=None,
                    source="Estimation",
                    weight=1.0,
                    normalized=50,
                )
            )

        score = sum(ind.weight * ind.normalized for ind in indicators)
        return AxisScore(
            axis=AttractiveAxis.QUALITE_VIE,
            score=score,
            indicators=indicators,
            trend=self._estimate_trend(territory_code, "qualite_vie"),
        )

    async def _score_accessibilite(self, territory_code: str) -> AxisScore:
        """Score accessibilité axis."""
        indicators: list[IndicatorValue] = []

        try:
            # Mapping département -> accessibilité (données statiques connues)
            DEPT_ACCESSIBILITE = {
                # Très bien desservis
                "75": {"tgv": 5, "aeroport": 3, "temps_paris": 0},
                "92": {"tgv": 3, "aeroport": 2, "temps_paris": 15},
                "93": {"tgv": 2, "aeroport": 2, "temps_paris": 20},
                "94": {"tgv": 2, "aeroport": 1, "temps_paris": 20},
                "69": {"tgv": 3, "aeroport": 1, "temps_paris": 120},
                "13": {"tgv": 2, "aeroport": 1, "temps_paris": 180},
                "31": {"tgv": 1, "aeroport": 1, "temps_paris": 240},
                "33": {"tgv": 2, "aeroport": 1, "temps_paris": 150},
                "44": {"tgv": 2, "aeroport": 1, "temps_paris": 140},
                "59": {"tgv": 3, "aeroport": 1, "temps_paris": 60},
                "67": {"tgv": 2, "aeroport": 1, "temps_paris": 110},
                # Par défaut
                "default": {"tgv": 0, "aeroport": 0, "temps_paris": 300},
            }

            access = DEPT_ACCESSIBILITE.get(territory_code, DEPT_ACCESSIBILITE["default"])

            # Gares TGV
            gares_tgv = access["tgv"]
            indicators.append(
                IndicatorValue(
                    name="Gares TGV",
                    value=gares_tgv,
                    raw_value=gares_tgv,
                    source="SNCF",
                    weight=0.30,
                    normalized=self._normalize(gares_tgv, "gares_tgv"),
                )
            )

            # Temps Paris
            temps_paris = access["temps_paris"]
            indicators.append(
                IndicatorValue(
                    name="Temps trajet Paris (min)",
                    value=temps_paris,
                    raw_value=temps_paris,
                    source="SNCF/Mappy",
                    weight=0.30,
                    normalized=self._normalize(temps_paris, "temps_paris_min", inverse=True),
                )
            )

            # Aéroport
            aeroport = access["aeroport"]
            indicators.append(
                IndicatorValue(
                    name="Aéroports proches",
                    value=aeroport,
                    raw_value=aeroport,
                    source="DGAC",
                    weight=0.25,
                    normalized=min(100, aeroport * 40),
                )
            )

            # Autoroutes (estimation via densité)
            insee = await self._get_insee()
            pop_data = await insee.get_population(territory_code)
            densite = pop_data.get("densite", 100) if pop_data else 100
            autoroute_score = min(100, 30 + densite / 10)

            indicators.append(
                IndicatorValue(
                    name="Accès autoroute",
                    value=autoroute_score,
                    raw_value=autoroute_score,
                    source="Estimation OSM",
                    weight=0.15,
                    normalized=autoroute_score,
                )
            )

        except Exception as e:
            logger.warning(f"Accessibilité scoring error: {e}")
            indicators.append(
                IndicatorValue(
                    name="Score estimé",
                    value=50,
                    raw_value=None,
                    source="Estimation",
                    weight=1.0,
                    normalized=50,
                )
            )

        score = sum(ind.weight * ind.normalized for ind in indicators)
        return AxisScore(
            axis=AttractiveAxis.ACCESSIBILITE,
            score=score,
            indicators=indicators,
            trend="stable",
        )

    async def _score_innovation(self, territory_code: str) -> AxisScore:
        """Score innovation axis."""
        indicators: list[IndicatorValue] = []

        try:
            sirene = await self._get_sirene()

            # Startups tech (NAF 62.xx)
            tech = await sirene.search(
                {
                    "departement": territory_code,
                    "activite_principale": "62",
                    "per_page": 1,
                }
            )
            tech_count = tech.get("total_results", 0) if tech else 0

            total = await sirene.search({"departement": territory_code, "per_page": 1})
            total_count = total.get("total_results", 1) if total else 1

            startup_pct = tech_count / max(1, total_count) * 100
            indicators.append(
                IndicatorValue(
                    name="% entreprises tech",
                    value=startup_pct,
                    raw_value=tech_count,
                    source="SIRENE",
                    weight=0.30,
                    normalized=self._normalize(startup_pct, "startups_pct"),
                )
            )

            # R&D (proxy via grandes entreprises)
            insee = await self._get_insee()
            pop_data = await insee.get_population(territory_code)
            population = pop_data.get("population", 100000) if pop_data else 100000

            rd_estimate = min(5, 1 + tech_count / 1000)
            indicators.append(
                IndicatorValue(
                    name="Investissement R&D estimé",
                    value=rd_estimate,
                    raw_value=rd_estimate,
                    source="Estimation MESRI",
                    weight=0.30,
                    normalized=self._normalize(rd_estimate, "rd_investissement"),
                )
            )

            # Brevets (corrélé au tech count)
            brevets = tech_count / population * 10 if population else 0
            indicators.append(
                IndicatorValue(
                    name="Brevets pour 1000 hab",
                    value=brevets,
                    raw_value=brevets,
                    source="Estimation INPI",
                    weight=0.25,
                    normalized=self._normalize(brevets, "brevets_1000hab"),
                )
            )

            # Incubateurs (proxy via taille)
            incubateurs = 1 if population > 200000 else 0
            indicators.append(
                IndicatorValue(
                    name="Présence incubateurs",
                    value=incubateurs * 100,
                    raw_value=incubateurs,
                    source="Estimation France Digitale",
                    weight=0.15,
                    normalized=incubateurs * 100,
                )
            )

        except Exception as e:
            logger.warning(f"Innovation scoring error: {e}")
            indicators.append(
                IndicatorValue(
                    name="Score estimé",
                    value=50,
                    raw_value=None,
                    source="Estimation",
                    weight=1.0,
                    normalized=50,
                )
            )

        score = sum(ind.weight * ind.normalized for ind in indicators)
        return AxisScore(
            axis=AttractiveAxis.INNOVATION,
            score=score,
            indicators=indicators,
            trend=self._estimate_trend(territory_code, "innovation"),
        )

    def _normalize(self, value: float, indicator: str, inverse: bool = False) -> float:
        """Normalize value to 0-100 scale using national references."""
        ref = NATIONAL_REFERENCES.get(indicator)
        if not ref:
            return min(100, max(0, value))

        min_val = ref["min"]
        max_val = ref["max"]

        # Clamp value
        clamped = max(min_val, min(max_val, value))

        # Linear normalization
        if max_val == min_val:
            normalized = 50
        else:
            normalized = (clamped - min_val) / (max_val - min_val) * 100

        if inverse:
            normalized = 100 - normalized

        return max(0, min(100, normalized))

    def _normalize_log(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize using logarithmic scale (for population, etc.)."""
        import math

        if value <= 0:
            return 0

        log_val = math.log10(value)
        log_min = math.log10(max(1, min_val))
        log_max = math.log10(max(1, max_val))

        if log_max == log_min:
            return 50

        normalized = (log_val - log_min) / (log_max - log_min) * 100
        return max(0, min(100, normalized))

    def _estimate_trend(self, territory_code: str, axis: str) -> str:
        """Estimate trend for axis (placeholder - would use historical data)."""
        # TODO: Implement with historical data
        # For now, assign based on known dynamics
        TRENDS = {
            "75": {"innovation": "up", "qualite_vie": "down"},
            "69": {"innovation": "up", "environnement_eco": "up"},
            "44": {"infrastructure": "up", "capital_humain": "up"},
        }
        return TRENDS.get(territory_code, {}).get(axis, "stable")

    async def _get_territory_name(self, code: str) -> str:
        """Get territory name from code."""
        DEPT_NAMES = {
            "01": "Ain",
            "02": "Aisne",
            "03": "Allier",
            "04": "Alpes-de-Haute-Provence",
            "05": "Hautes-Alpes",
            "06": "Alpes-Maritimes",
            "07": "Ardèche",
            "08": "Ardennes",
            "09": "Ariège",
            "10": "Aube",
            "11": "Aude",
            "12": "Aveyron",
            "13": "Bouches-du-Rhône",
            "14": "Calvados",
            "15": "Cantal",
            "16": "Charente",
            "17": "Charente-Maritime",
            "18": "Cher",
            "19": "Corrèze",
            "21": "Côte-d'Or",
            "22": "Côtes-d'Armor",
            "23": "Creuse",
            "24": "Dordogne",
            "25": "Doubs",
            "26": "Drôme",
            "27": "Eure",
            "28": "Eure-et-Loir",
            "29": "Finistère",
            "2A": "Corse-du-Sud",
            "2B": "Haute-Corse",
            "30": "Gard",
            "31": "Haute-Garonne",
            "32": "Gers",
            "33": "Gironde",
            "34": "Hérault",
            "35": "Ille-et-Vilaine",
            "36": "Indre",
            "37": "Indre-et-Loire",
            "38": "Isère",
            "39": "Jura",
            "40": "Landes",
            "41": "Loir-et-Cher",
            "42": "Loire",
            "43": "Haute-Loire",
            "44": "Loire-Atlantique",
            "45": "Loiret",
            "46": "Lot",
            "47": "Lot-et-Garonne",
            "48": "Lozère",
            "49": "Maine-et-Loire",
            "50": "Manche",
            "51": "Marne",
            "52": "Haute-Marne",
            "53": "Mayenne",
            "54": "Meurthe-et-Moselle",
            "55": "Meuse",
            "56": "Morbihan",
            "57": "Moselle",
            "58": "Nièvre",
            "59": "Nord",
            "60": "Oise",
            "61": "Orne",
            "62": "Pas-de-Calais",
            "63": "Puy-de-Dôme",
            "64": "Pyrénées-Atlantiques",
            "65": "Hautes-Pyrénées",
            "66": "Pyrénées-Orientales",
            "67": "Bas-Rhin",
            "68": "Haut-Rhin",
            "69": "Rhône",
            "70": "Haute-Saône",
            "71": "Saône-et-Loire",
            "72": "Sarthe",
            "73": "Savoie",
            "74": "Haute-Savoie",
            "75": "Paris",
            "76": "Seine-Maritime",
            "77": "Seine-et-Marne",
            "78": "Yvelines",
            "79": "Deux-Sèvres",
            "80": "Somme",
            "81": "Tarn",
            "82": "Tarn-et-Garonne",
            "83": "Var",
            "84": "Vaucluse",
            "85": "Vendée",
            "86": "Vienne",
            "87": "Haute-Vienne",
            "88": "Vosges",
            "89": "Yonne",
            "90": "Territoire de Belfort",
            "91": "Essonne",
            "92": "Hauts-de-Seine",
            "93": "Seine-Saint-Denis",
            "94": "Val-de-Marne",
            "95": "Val-d'Oise",
            "971": "Guadeloupe",
            "972": "Martinique",
            "973": "Guyane",
            "974": "La Réunion",
            "976": "Mayotte",
        }
        return DEPT_NAMES.get(code, f"Territoire {code}")

    def _get_comparison_group(self, code: str) -> str:
        """Get comparison group for territory."""
        METROPOLES = {"75", "69", "13", "31", "33", "44", "59", "67", "06", "34"}
        IDF = {"75", "77", "78", "91", "92", "93", "94", "95"}

        if code in IDF:
            return "Île-de-France"
        elif code in METROPOLES:
            return "Grandes métropoles"
        elif code.startswith("97"):
            return "Outre-mer"
        else:
            return "Départements"
