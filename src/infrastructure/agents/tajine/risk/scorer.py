"""
Risk Scorer - ML-based enterprise risk prediction.

Uses XGBoost (or fallback to heuristic scoring) for risk assessment.
Provides 0-100 risk score with confidence intervals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

import numpy as np
from loguru import logger

from .features import EnterpriseFeatures, FeatureExtractor


class RiskLevel(StrEnum):
    """Risk level classification."""

    VERY_LOW = "TRES_FAIBLE"
    LOW = "FAIBLE"
    MODERATE = "MODERE"
    HIGH = "ELEVE"
    VERY_HIGH = "TRES_ELEVE"
    CRITICAL = "CRITIQUE"


@dataclass
class RiskScore:
    """Complete risk score result."""

    siren: str
    denomination: str
    score: float  # 0-100
    risk_level: RiskLevel
    confidence: float  # 0-1
    confidence_interval: tuple[float, float]  # (lower, upper)
    data_quality: float  # 0-1
    computed_at: datetime = field(default_factory=datetime.now)

    # Top contributing factors
    top_factors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "siren": self.siren,
            "denomination": self.denomination,
            "score": round(self.score, 1),
            "risk_level": self.risk_level.value,
            "confidence": round(self.confidence, 2),
            "confidence_interval": [
                round(self.confidence_interval[0], 1),
                round(self.confidence_interval[1], 1),
            ],
            "data_quality": round(self.data_quality, 2),
            "computed_at": self.computed_at.isoformat(),
            "top_factors": self.top_factors,
        }


# Risk thresholds for classification
RISK_THRESHOLDS = {
    RiskLevel.VERY_LOW: 15,
    RiskLevel.LOW: 30,
    RiskLevel.MODERATE: 50,
    RiskLevel.HIGH: 70,
    RiskLevel.VERY_HIGH: 85,
    RiskLevel.CRITICAL: 100,
}

# Feature weights for heuristic scoring (when XGBoost not available)
FEATURE_WEIGHTS = {
    "nb_privileges_12m": 15.0,
    "nb_privileges_24m": 8.0,
    "has_procedure_collective": 25.0,
    "has_liquidation": 35.0,
    "has_redressement": 20.0,
    "nb_jugements_12m": 12.0,
    "age_years_penalty": -2.0,  # Negative = reduces risk per year
    "effectif_bonus": -0.5,  # Negative = reduces risk per employee
    "secteur_risque_national": 100.0,  # Multiplied by sector risk rate
    "region_risque": 50.0,  # Multiplied by regional risk rate
}


class RiskScorer:
    """
    ML-based risk scorer for enterprises.

    Uses XGBoost when available, falls back to heuristic scoring.
    """

    def __init__(self, model_path: str | None = None):
        """
        Initialize scorer.

        Args:
            model_path: Path to trained XGBoost model (optional)
        """
        self.model = None
        self.model_path = model_path
        self._feature_extractor = None

        # Try to load XGBoost model
        if model_path:
            self._load_model(model_path)

    def _load_model(self, path: str) -> None:
        """Load XGBoost model from path."""
        try:
            import xgboost as xgb

            self.model = xgb.Booster()
            self.model.load_model(path)
            logger.info(f"Loaded XGBoost model from {path}")
        except ImportError:
            logger.warning("XGBoost not installed, using heuristic scoring")
        except Exception as e:
            logger.warning(f"Failed to load model: {e}, using heuristic scoring")

    async def score(self, siren: str) -> RiskScore:
        """
        Compute risk score for a SIREN.

        Args:
            siren: SIREN number (9 digits)

        Returns:
            Complete RiskScore with factors and confidence
        """
        # Extract features
        if self._feature_extractor is None:
            self._feature_extractor = FeatureExtractor()

        features = await self._feature_extractor.extract(siren)

        # Score using model or heuristics
        if self.model is not None:
            return self._score_with_model(features)
        else:
            return self._score_heuristic(features)

    def score_from_features(self, features: EnterpriseFeatures) -> RiskScore:
        """
        Compute risk score from pre-extracted features.

        Args:
            features: Pre-extracted enterprise features

        Returns:
            Complete RiskScore
        """
        if self.model is not None:
            return self._score_with_model(features)
        else:
            return self._score_heuristic(features)

    def _score_with_model(self, features: EnterpriseFeatures) -> RiskScore:
        """Score using XGBoost model."""
        import xgboost as xgb

        # Prepare input
        input_data = features.to_model_input()

        # Convert to DMatrix (XGBoost format)
        # Note: Categorical features need encoding - simplified here
        numeric_features = [
            input_data["nb_privileges_12m"],
            input_data["nb_privileges_24m"],
            input_data["montant_privileges"],
            input_data["nb_jugements_12m"],
            input_data["has_procedure_collective"],
            input_data["has_plan_sauvegarde"],
            input_data["age_years"],
            input_data["effectif_actuel"],
            input_data["nb_etablissements"],
            input_data["is_active"],
            input_data["ratio_age_privileges"],
            input_data["secteur_risque_national"],
            input_data["region_risque"],
        ]

        dmatrix = xgb.DMatrix(np.array([numeric_features]))

        # Predict
        prediction = self.model.predict(dmatrix)[0]
        score = float(prediction) * 100  # Convert to 0-100

        # Clamp score
        score = max(0, min(100, score))

        # Classify risk level
        risk_level = self._classify_risk(score)

        # Calculate confidence based on data quality
        confidence = features.data_quality * 0.8 + 0.2  # Minimum 20% confidence

        # Confidence interval (simplified - would use bootstrap in production)
        margin = (1 - confidence) * 20
        ci = (max(0, score - margin), min(100, score + margin))

        # Extract top factors (would use SHAP in production)
        top_factors = self._extract_factors_heuristic(features)

        return RiskScore(
            siren=features.siren,
            denomination=features.denomination,
            score=score,
            risk_level=risk_level,
            confidence=confidence,
            confidence_interval=ci,
            data_quality=features.data_quality,
            top_factors=top_factors[:5],
        )

    def _score_heuristic(self, features: EnterpriseFeatures) -> RiskScore:
        """Score using heuristic rules when model not available."""
        score = 20.0  # Base score

        factors = []

        # BODACC signals
        bodacc = features.bodacc

        if bodacc.nb_privileges_12m > 0:
            contrib = bodacc.nb_privileges_12m * FEATURE_WEIGHTS["nb_privileges_12m"]
            score += contrib
            factors.append(
                {
                    "name": "Privilèges récents (12 mois)",
                    "value": bodacc.nb_privileges_12m,
                    "contribution": contrib,
                    "direction": "negative",
                }
            )

        if bodacc.nb_privileges_24m > bodacc.nb_privileges_12m:
            older = bodacc.nb_privileges_24m - bodacc.nb_privileges_12m
            contrib = older * FEATURE_WEIGHTS["nb_privileges_24m"]
            score += contrib
            factors.append(
                {
                    "name": "Privilèges anciens (12-24 mois)",
                    "value": older,
                    "contribution": contrib,
                    "direction": "negative",
                }
            )

        if bodacc.has_liquidation:
            contrib = FEATURE_WEIGHTS["has_liquidation"]
            score += contrib
            factors.append(
                {
                    "name": "Liquidation judiciaire",
                    "value": True,
                    "contribution": contrib,
                    "direction": "critical",
                }
            )
        elif bodacc.has_redressement:
            contrib = FEATURE_WEIGHTS["has_redressement"]
            score += contrib
            factors.append(
                {
                    "name": "Redressement judiciaire",
                    "value": True,
                    "contribution": contrib,
                    "direction": "negative",
                }
            )
        elif bodacc.has_procedure_collective:
            contrib = FEATURE_WEIGHTS["has_procedure_collective"]
            score += contrib
            factors.append(
                {
                    "name": "Procédure collective",
                    "value": True,
                    "contribution": contrib,
                    "direction": "negative",
                }
            )

        if bodacc.nb_jugements_12m > 0:
            contrib = bodacc.nb_jugements_12m * FEATURE_WEIGHTS["nb_jugements_12m"]
            score += contrib
            factors.append(
                {
                    "name": "Jugements récents",
                    "value": bodacc.nb_jugements_12m,
                    "contribution": contrib,
                    "direction": "negative",
                }
            )

        # SIRENE signals
        sirene = features.sirene

        # Age bonus (older = less risky)
        if sirene.age_years > 0:
            age_reduction = min(sirene.age_years, 10) * abs(FEATURE_WEIGHTS["age_years_penalty"])
            score -= age_reduction
            if sirene.age_years >= 5:
                factors.append(
                    {
                        "name": "Entreprise établie",
                        "value": f"{sirene.age_years:.1f} ans",
                        "contribution": -age_reduction,
                        "direction": "positive",
                    }
                )

        # Size bonus (larger = less risky)
        if sirene.effectif_actuel > 0:
            size_reduction = min(sirene.effectif_actuel, 50) * abs(
                FEATURE_WEIGHTS["effectif_bonus"]
            )
            score -= size_reduction
            if sirene.effectif_actuel >= 10:
                factors.append(
                    {
                        "name": "Effectif significatif",
                        "value": sirene.effectif_actuel,
                        "contribution": -size_reduction,
                        "direction": "positive",
                    }
                )

        # Sector risk
        if features.secteur_risque_national > 0.05:
            contrib = features.secteur_risque_national * FEATURE_WEIGHTS["secteur_risque_national"]
            score += contrib
            factors.append(
                {
                    "name": "Secteur à risque",
                    "value": f"{features.secteur_risque_national * 100:.1f}%",
                    "contribution": contrib,
                    "direction": "negative",
                }
            )

        # Regional risk
        if features.region_risque > 0.045:
            contrib = features.region_risque * FEATURE_WEIGHTS["region_risque"]
            score += contrib
            factors.append(
                {
                    "name": "Région à risque",
                    "value": f"{features.region_risque * 100:.1f}%",
                    "contribution": contrib,
                    "direction": "negative",
                }
            )

        # Inactive company is critical
        if not sirene.is_active:
            score = 95.0
            factors.insert(
                0,
                {
                    "name": "Entreprise inactive",
                    "value": True,
                    "contribution": 95.0,
                    "direction": "critical",
                },
            )

        # Clamp score
        score = max(0, min(100, score))

        # Classify
        risk_level = self._classify_risk(score)

        # Confidence based on data quality
        confidence = features.data_quality * 0.7 + 0.3

        # Confidence interval
        margin = (1 - confidence) * 25
        ci = (max(0, score - margin), min(100, score + margin))

        # Sort factors by absolute contribution
        factors.sort(key=lambda f: abs(f["contribution"]), reverse=True)

        return RiskScore(
            siren=features.siren,
            denomination=features.denomination,
            score=score,
            risk_level=risk_level,
            confidence=confidence,
            confidence_interval=ci,
            data_quality=features.data_quality,
            top_factors=factors[:5],
        )

    def _classify_risk(self, score: float) -> RiskLevel:
        """Classify score into risk level."""
        for level, threshold in sorted(RISK_THRESHOLDS.items(), key=lambda x: x[1]):
            if score <= threshold:
                return level
        return RiskLevel.CRITICAL

    def _extract_factors_heuristic(self, features: EnterpriseFeatures) -> list[dict]:
        """Extract contributing factors using heuristics."""
        factors = []

        bodacc = features.bodacc
        sirene = features.sirene

        if bodacc.has_liquidation:
            factors.append(
                {
                    "name": "Liquidation",
                    "contribution": 35.0,
                    "direction": "critical",
                }
            )

        if bodacc.nb_privileges_12m > 0:
            factors.append(
                {
                    "name": f"{bodacc.nb_privileges_12m} privilèges",
                    "contribution": bodacc.nb_privileges_12m * 15.0,
                    "direction": "negative",
                }
            )

        if sirene.age_years >= 10:
            factors.append(
                {
                    "name": "Ancienneté",
                    "contribution": -20.0,
                    "direction": "positive",
                }
            )

        return factors

    async def close(self) -> None:
        """Cleanup resources."""
        if self._feature_extractor:
            await self._feature_extractor.close()
