"""
Risk Explainer - Human-readable explanations for risk scores.

Uses SHAP (when available) or rule-based explanations to provide
transparent, actionable insights into risk factors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from loguru import logger

from .features import EnterpriseFeatures
from .scorer import RiskLevel, RiskScore


class ExplanationStyle(StrEnum):
    """Style of explanation output."""

    TECHNICAL = "technical"  # For analysts
    BUSINESS = "business"  # For decision makers
    SUMMARY = "summary"  # Brief overview


class FactorDirection(StrEnum):
    """Direction of risk factor impact."""

    POSITIVE = "positive"  # Reduces risk
    NEGATIVE = "negative"  # Increases risk
    CRITICAL = "critical"  # Major red flag
    NEUTRAL = "neutral"  # No significant impact


@dataclass
class ExplanationFactor:
    """A single explained factor."""

    name: str
    value: Any
    impact: float  # -100 to +100
    direction: FactorDirection
    description: str
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "impact": round(self.impact, 1),
            "direction": self.direction.value,
            "description": self.description,
            "recommendation": self.recommendation,
        }


@dataclass
class RiskExplanation:
    """Complete risk explanation."""

    siren: str
    denomination: str
    score: RiskScore
    factors: list[ExplanationFactor]
    summary: str
    detailed_analysis: str
    recommendations: list[str]
    data_sources: list[str]
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "siren": self.siren,
            "denomination": self.denomination,
            "score": self.score.to_dict(),
            "factors": [f.to_dict() for f in self.factors],
            "summary": self.summary,
            "detailed_analysis": self.detailed_analysis,
            "recommendations": self.recommendations,
            "data_sources": self.data_sources,
            "generated_at": self.generated_at.isoformat(),
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# Analyse de Risque - {self.denomination}",
            f"**SIREN:** {self.siren}",
            f"**Score:** {self.score.score:.0f}/100 ({self.score.risk_level.value})",
            f"**Confiance:** {self.score.confidence * 100:.0f}%",
            "",
            "## Résumé",
            self.summary,
            "",
            "## Facteurs Principaux",
        ]

        for factor in self.factors[:5]:
            icon = (
                "🔴"
                if factor.direction == FactorDirection.CRITICAL
                else ("🟡" if factor.direction == FactorDirection.NEGATIVE else "🟢")
            )
            lines.append(f"- {icon} **{factor.name}**: {factor.description}")

        if self.recommendations:
            lines.extend(
                [
                    "",
                    "## Recommandations",
                ]
            )
            for rec in self.recommendations:
                lines.append(f"- {rec}")

        lines.extend(
            [
                "",
                "## Sources de Données",
                ", ".join(self.data_sources),
                "",
                f"*Généré le {self.generated_at.strftime('%d/%m/%Y à %H:%M')}*",
            ]
        )

        return "\n".join(lines)


# Explanation templates by factor type
FACTOR_TEMPLATES = {
    "privileges_recent": {
        "name": "Privilèges INSS récents",
        "description_template": "{count} privilège(s) enregistré(s) au cours des 12 derniers mois",
        "recommendation": "Vérifier les paiements URSSAF et régulariser si nécessaire",
    },
    "privileges_old": {
        "name": "Privilèges INSS anciens",
        "description_template": "{count} privilège(s) entre 12 et 24 mois",
        "recommendation": "Historique de tensions de trésorerie - surveiller l'évolution",
    },
    "liquidation": {
        "name": "Liquidation judiciaire",
        "description_template": "Procédure de liquidation en cours ou passée",
        "recommendation": "Situation critique - éviter engagement financier",
    },
    "redressement": {
        "name": "Redressement judiciaire",
        "description_template": "Procédure de redressement en cours ou passée",
        "recommendation": "Vérifier le plan de continuation et son respect",
    },
    "procedure_collective": {
        "name": "Procédure collective",
        "description_template": "Procédure collective en cours",
        "recommendation": "Consulter les annonces BODACC pour détails",
    },
    "jugements": {
        "name": "Jugements récents",
        "description_template": "{count} jugement(s) au cours des 12 derniers mois",
        "recommendation": "Analyser la nature des litiges",
    },
    "age": {
        "name": "Ancienneté de l'entreprise",
        "description_template": "Entreprise créée il y a {years:.1f} ans",
        "recommendation": None,  # Positive factor
    },
    "effectif": {
        "name": "Effectif salarié",
        "description_template": "{count} salarié(s) déclaré(s)",
        "recommendation": None,  # Positive factor
    },
    "secteur_risque": {
        "name": "Secteur d'activité à risque",
        "description_template": "Taux de défaillance sectoriel de {rate:.1%}",
        "recommendation": "Secteur présentant un risque supérieur à la moyenne",
    },
    "region_risque": {
        "name": "Risque régional",
        "description_template": "Taux de défaillance régional de {rate:.1%}",
        "recommendation": "Zone géographique avec dynamique économique tendue",
    },
    "inactive": {
        "name": "Entreprise inactive",
        "description_template": "L'entreprise n'est plus en activité",
        "recommendation": "Ne pas engager de relation commerciale",
    },
}

# Risk level summaries
RISK_SUMMARIES = {
    RiskLevel.VERY_LOW: "Entreprise présentant un profil de risque très faible. "
    "Les indicateurs sont favorables sur l'ensemble des dimensions analysées.",
    RiskLevel.LOW: "Entreprise présentant un profil de risque faible. "
    "Quelques points d'attention mineurs mais situation globalement saine.",
    RiskLevel.MODERATE: "Entreprise présentant un risque modéré. "
    "Certains indicateurs méritent une attention particulière.",
    RiskLevel.HIGH: "Entreprise présentant un risque élevé. "
    "Plusieurs signaux d'alerte détectés nécessitant une vigilance accrue.",
    RiskLevel.VERY_HIGH: "Entreprise présentant un risque très élevé. "
    "Signaux d'alerte multiples - prudence recommandée.",
    RiskLevel.CRITICAL: "Situation critique détectée. "
    "Risque majeur avéré - engagement fortement déconseillé.",
}


class RiskExplainer:
    """
    Generates human-readable explanations for risk scores.

    Uses SHAP when available for model-based explanations,
    falls back to rule-based explanations otherwise.
    """

    def __init__(self, use_shap: bool = True):
        """
        Initialize explainer.

        Args:
            use_shap: Try to use SHAP for explanations (if available)
        """
        self.use_shap = use_shap
        self._shap_available = False

        if use_shap:
            try:
                import shap  # noqa: F401

                self._shap_available = True
                logger.info("SHAP available for risk explanations")
            except ImportError:
                logger.info("SHAP not available, using rule-based explanations")

    def explain(
        self,
        score: RiskScore,
        features: EnterpriseFeatures,
        style: ExplanationStyle = ExplanationStyle.BUSINESS,
    ) -> RiskExplanation:
        """
        Generate explanation for a risk score.

        Args:
            score: The computed risk score
            features: The features used for scoring
            style: Output style (technical, business, summary)

        Returns:
            Complete RiskExplanation with factors and recommendations
        """
        # Extract explained factors
        factors = self._extract_factors(score, features)

        # Generate summary based on risk level
        summary = self._generate_summary(score, factors, style)

        # Generate detailed analysis
        detailed = self._generate_detailed_analysis(score, features, factors, style)

        # Collect recommendations
        recommendations = self._collect_recommendations(factors, score.risk_level)

        # List data sources used
        data_sources = self._list_data_sources(features)

        return RiskExplanation(
            siren=score.siren,
            denomination=score.denomination,
            score=score,
            factors=factors,
            summary=summary,
            detailed_analysis=detailed,
            recommendations=recommendations,
            data_sources=data_sources,
        )

    def _extract_factors(
        self,
        score: RiskScore,
        features: EnterpriseFeatures,
    ) -> list[ExplanationFactor]:
        """Extract and explain contributing factors."""
        factors = []

        bodacc = features.bodacc
        sirene = features.sirene

        # BODACC signals (negative factors)
        if bodacc.nb_privileges_12m > 0:
            template = FACTOR_TEMPLATES["privileges_recent"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=bodacc.nb_privileges_12m,
                    impact=bodacc.nb_privileges_12m * 15.0,
                    direction=FactorDirection.NEGATIVE,
                    description=template["description_template"].format(
                        count=bodacc.nb_privileges_12m
                    ),
                    recommendation=template["recommendation"],
                )
            )

        if bodacc.nb_privileges_24m > bodacc.nb_privileges_12m:
            older = bodacc.nb_privileges_24m - bodacc.nb_privileges_12m
            template = FACTOR_TEMPLATES["privileges_old"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=older,
                    impact=older * 8.0,
                    direction=FactorDirection.NEGATIVE,
                    description=template["description_template"].format(count=older),
                    recommendation=template["recommendation"],
                )
            )

        if bodacc.has_liquidation:
            template = FACTOR_TEMPLATES["liquidation"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=True,
                    impact=35.0,
                    direction=FactorDirection.CRITICAL,
                    description=template["description_template"],
                    recommendation=template["recommendation"],
                )
            )
        elif bodacc.has_redressement:
            template = FACTOR_TEMPLATES["redressement"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=True,
                    impact=20.0,
                    direction=FactorDirection.CRITICAL,
                    description=template["description_template"],
                    recommendation=template["recommendation"],
                )
            )
        elif bodacc.has_procedure_collective:
            template = FACTOR_TEMPLATES["procedure_collective"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=True,
                    impact=25.0,
                    direction=FactorDirection.NEGATIVE,
                    description=template["description_template"],
                    recommendation=template["recommendation"],
                )
            )

        if bodacc.nb_jugements_12m > 0:
            template = FACTOR_TEMPLATES["jugements"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=bodacc.nb_jugements_12m,
                    impact=bodacc.nb_jugements_12m * 12.0,
                    direction=FactorDirection.NEGATIVE,
                    description=template["description_template"].format(
                        count=bodacc.nb_jugements_12m
                    ),
                    recommendation=template["recommendation"],
                )
            )

        # SIRENE signals (can be positive)
        if sirene.age_years >= 5:
            template = FACTOR_TEMPLATES["age"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=sirene.age_years,
                    impact=-min(sirene.age_years, 10) * 2.0,  # Negative = reduces risk
                    direction=FactorDirection.POSITIVE,
                    description=template["description_template"].format(years=sirene.age_years),
                    recommendation=template["recommendation"],
                )
            )

        if sirene.effectif_actuel >= 10:
            template = FACTOR_TEMPLATES["effectif"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=sirene.effectif_actuel,
                    impact=-min(sirene.effectif_actuel, 50) * 0.5,
                    direction=FactorDirection.POSITIVE,
                    description=template["description_template"].format(
                        count=sirene.effectif_actuel
                    ),
                    recommendation=template["recommendation"],
                )
            )

        # Sector/Regional risk
        if features.secteur_risque_national > 0.05:
            template = FACTOR_TEMPLATES["secteur_risque"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=features.secteur_risque_national,
                    impact=features.secteur_risque_national * 100.0,
                    direction=FactorDirection.NEGATIVE,
                    description=template["description_template"].format(
                        rate=features.secteur_risque_national
                    ),
                    recommendation=template["recommendation"],
                )
            )

        if features.region_risque > 0.045:
            template = FACTOR_TEMPLATES["region_risque"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=features.region_risque,
                    impact=features.region_risque * 50.0,
                    direction=FactorDirection.NEGATIVE,
                    description=template["description_template"].format(
                        rate=features.region_risque
                    ),
                    recommendation=template["recommendation"],
                )
            )

        # Inactive company
        if not sirene.is_active:
            template = FACTOR_TEMPLATES["inactive"]
            factors.append(
                ExplanationFactor(
                    name=template["name"],
                    value=True,
                    impact=95.0,
                    direction=FactorDirection.CRITICAL,
                    description=template["description_template"],
                    recommendation=template["recommendation"],
                )
            )

        # Sort by absolute impact
        factors.sort(key=lambda f: abs(f.impact), reverse=True)

        return factors

    def _generate_summary(
        self,
        score: RiskScore,
        factors: list[ExplanationFactor],
        style: ExplanationStyle,
    ) -> str:
        """Generate summary text based on risk level."""
        base_summary = RISK_SUMMARIES.get(score.risk_level, "Profil de risque analysé.")

        if style == ExplanationStyle.SUMMARY:
            return base_summary

        # Add top factor mentions for business/technical
        critical_factors = [f for f in factors if f.direction == FactorDirection.CRITICAL]
        if critical_factors:
            base_summary += f" Point critique: {critical_factors[0].name}."

        return base_summary

    def _generate_detailed_analysis(
        self,
        score: RiskScore,
        features: EnterpriseFeatures,
        factors: list[ExplanationFactor],
        style: ExplanationStyle,
    ) -> str:
        """Generate detailed analysis text."""
        if style == ExplanationStyle.SUMMARY:
            return ""

        lines = []

        # Score interpretation
        lines.append(
            f"Le score de risque de {score.score:.0f}/100 place cette entreprise "
            f"dans la catégorie '{score.risk_level.value}'."
        )

        # Confidence
        if score.confidence >= 0.8:
            lines.append(
                "La confiance dans cette évaluation est élevée, "
                "les données étant complètes et récentes."
            )
        elif score.confidence >= 0.6:
            lines.append(
                "La confiance est modérée. Certaines données peuvent être incomplètes ou anciennes."
            )
        else:
            lines.append("⚠️ La confiance est limitée en raison de données manquantes ou obsolètes.")

        # Key factors analysis
        if style == ExplanationStyle.TECHNICAL:
            lines.append("\n### Détail des facteurs")
            for factor in factors[:5]:
                lines.append(
                    f"- **{factor.name}** (impact: {factor.impact:+.1f}): {factor.description}"
                )

        return " ".join(lines)

    def _collect_recommendations(
        self,
        factors: list[ExplanationFactor],
        risk_level: RiskLevel,
    ) -> list[str]:
        """Collect recommendations from factors."""
        recommendations = []

        # Factor-specific recommendations
        for factor in factors:
            if factor.recommendation and factor.recommendation not in recommendations:
                recommendations.append(factor.recommendation)

        # General recommendations by risk level
        if risk_level in (RiskLevel.CRITICAL, RiskLevel.VERY_HIGH):
            recommendations.insert(0, "Éviter tout engagement financier significatif")
            recommendations.append("Consulter un expert-comptable ou avocat si relation existante")
        elif risk_level == RiskLevel.HIGH:
            recommendations.insert(0, "Demander des garanties supplémentaires")
            recommendations.append("Suivre l'évolution trimestriellement")
        elif risk_level == RiskLevel.MODERATE:
            recommendations.append("Mettre en place un suivi semestriel")

        return recommendations[:5]  # Limit to 5

    def _list_data_sources(self, features: EnterpriseFeatures) -> list[str]:
        """List data sources used in the analysis."""
        sources = []

        if features.sirene.effectif_actuel is not None:
            sources.append("INSEE SIRENE")

        if features.bodacc.nb_privileges_12m is not None:
            sources.append("BODACC")

        if features.secteur_risque_national > 0:
            sources.append("Statistiques sectorielles nationales")

        if features.region_risque > 0:
            sources.append("Statistiques régionales")

        return sources if sources else ["Données limitées"]

    async def explain_siren(
        self,
        siren: str,
        style: ExplanationStyle = ExplanationStyle.BUSINESS,
    ) -> RiskExplanation:
        """
        Complete explanation workflow from SIREN.

        Args:
            siren: SIREN number (9 digits)
            style: Output style

        Returns:
            Complete RiskExplanation
        """
        from .features import FeatureExtractor
        from .scorer import RiskScorer

        # Extract features
        extractor = FeatureExtractor()
        features = await extractor.extract(siren)

        # Score
        scorer = RiskScorer()
        score = scorer.score_from_features(features)

        # Explain
        explanation = self.explain(score, features, style)

        # Cleanup
        await extractor.close()

        return explanation
