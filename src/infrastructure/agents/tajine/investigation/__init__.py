"""
Investigation Engine - Assistant d'investigation entreprise.

Approche: Pas un prédicteur binaire, mais un assistant qui:
- Agrège toutes les sources publiques disponibles
- Identifie signaux faibles et incohérences
- Génère questions à poser au demandeur
- Suit une approche bayésienne transparente
"""

from .bayesian_reasoner import BayesianReasoner, RiskAssessment
from .investigation_tool import InvestigateEnterpriseTool
from .report_generator import InvestigationReport, ReportGenerator
from .signal_extractor import Signal, SignalCategory, SignalExtractor

__all__ = [
    "SignalExtractor",
    "Signal",
    "SignalCategory",
    "BayesianReasoner",
    "RiskAssessment",
    "ReportGenerator",
    "InvestigationReport",
    "InvestigateEnterpriseTool",
]
