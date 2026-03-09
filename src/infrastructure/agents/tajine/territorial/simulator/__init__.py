"""
Territorial Simulator - Simulation multi-agents du territoire.

Agents:
- EnterpriseAgent: Création, croissance, fermeture
- HouseholdAgent: Migration, emploi, consommation
- InstitutionAgent: CCI, Pôle Emploi
- PolicyAgent: Politiques publiques

Inspiré de SimCity et OASIS (Camel AI).
"""

from __future__ import annotations

from .agents.enterprise import EnterpriseAgent
from .agents.household import HouseholdAgent
from .engine import SimulationResult, TerritorialSimulator
from .scenarios import PREDEFINED_SCENARIOS, WhatIfScenario

__all__ = [
    "TerritorialSimulator",
    "SimulationResult",
    "WhatIfScenario",
    "PREDEFINED_SCENARIOS",
    "EnterpriseAgent",
    "HouseholdAgent",
]
