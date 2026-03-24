"""
Risk Scoring Module for TAJINE.

Provides ML-based enterprise risk assessment using:
- BODACC signals (privileges, procedures)
- SIRENE data (effectifs, age, sector)
- Derived features (sector risk, regional patterns)

Main components:
- RiskScorer: XGBoost-based risk prediction (0-100)
- FeatureExtractor: Collects features from APIs
- RiskExplainer: SHAP-based explanations
"""

from src.infrastructure.agents.tajine.risk.explainer import (
    ExplanationFactor,
    ExplanationStyle,
    RiskExplainer,
    RiskExplanation,
)
from src.infrastructure.agents.tajine.risk.features import (
    EnterpriseFeatures,
    FeatureExtractor,
)
from src.infrastructure.agents.tajine.risk.scorer import (
    RiskLevel,
    RiskScore,
    RiskScorer,
)

__all__ = [
    "RiskScorer",
    "RiskScore",
    "RiskLevel",
    "FeatureExtractor",
    "EnterpriseFeatures",
    "RiskExplainer",
    "RiskExplanation",
    "ExplanationStyle",
    "ExplanationFactor",
]
