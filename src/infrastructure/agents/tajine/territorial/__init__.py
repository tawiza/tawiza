"""
Territorial Analyzer - Analyse et simulation de l'attractivité territoriale.

Modules:
- AttractivenessScorer: Score multi-dimensionnel (6 axes)
- CompetitorAnalyzer: Benchmarking territorial
- TerritorialSimulator: Simulation multi-agents
- SignalDetector: Détection de micro-signaux économiques
"""

from __future__ import annotations

from .attractiveness_scorer import (
    AttractiveAxis,
    AttractivenessScore,
    AttractivenessScorer,
    AxisScore,
)
from .competitor_analyzer import (
    CompetitorAnalysis,
    CompetitorAnalyzer,
    TerritoryComparison,
)
from .signal_detector import (
    DetectedSignal,
    SignalCategory,
    SignalDetector,
    SignalIndicator,
    SignalPattern,
    SignalSeverity,
    create_signal_detector,
)
from .simulator import (
    EnterpriseAgent,
    HouseholdAgent,
    SimulationResult,
    TerritorialSimulator,
    WhatIfScenario,
)
from .tools import AnalyzeTerritoryTool, ListScenariosToolTool, TerritorialAnalysis

__all__ = [
    # Scorer
    "AttractivenessScorer",
    "AttractivenessScore",
    "AxisScore",
    "AttractiveAxis",
    # Analyzer
    "CompetitorAnalyzer",
    "CompetitorAnalysis",
    "TerritoryComparison",
    # Simulator
    "TerritorialSimulator",
    "SimulationResult",
    "WhatIfScenario",
    "EnterpriseAgent",
    "HouseholdAgent",
    # Signal Detector
    "SignalDetector",
    "SignalPattern",
    "SignalIndicator",
    "DetectedSignal",
    "SignalSeverity",
    "SignalCategory",
    "create_signal_detector",
    # Tools
    "AnalyzeTerritoryTool",
    "TerritorialAnalysis",
    "ListScenariosToolTool",
]
