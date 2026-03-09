"""
Simulation Scenarios - Scénarios "What-If" prédéfinis.

Permet de simuler l'impact de politiques publiques avant déploiement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PolicyChange:
    """Un changement de politique à simuler."""

    type: str  # "tax_reduction", "subsidy", "infrastructure", "accessibility"
    target: str = ""  # Secteur NAF, type infrastructure, etc.
    value: float = 0.0  # Montant ou pourcentage
    description: str = ""


@dataclass
class WhatIfScenario:
    """Scénario hypothétique à simuler."""

    id: str
    name: str
    description: str
    changes: list[PolicyChange]
    duration_months: int = 36

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "duration_months": self.duration_months,
            "changes": [
                {
                    "type": c.type,
                    "target": c.target,
                    "value": c.value,
                    "description": c.description,
                }
                for c in self.changes
            ],
        }

    def apply_to_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Apply scenario changes to simulation context.

        Args:
            context: Base simulation context

        Returns:
            Modified context
        """
        modified = context.copy()

        for change in self.changes:
            if change.type == "tax_reduction":
                # Réduction fiscale -> améliore environnement économique
                current = modified.get("attractiveness", {})
                current["environnement_eco"] = current.get("environnement_eco", 50) + change.value * 50
                modified["attractiveness"] = current
                modified["policy_impact"] = modified.get("policy_impact", 0) + change.value * 0.5

            elif change.type == "subsidy":
                # Subvention -> améliore santé entreprises du secteur
                modified["subsidy_sectors"] = modified.get("subsidy_sectors", {})
                modified["subsidy_sectors"][change.target] = change.value
                modified["policy_impact"] = modified.get("policy_impact", 0) + 0.2

            elif change.type == "infrastructure":
                # Nouvel équipement -> améliore infrastructure
                current = modified.get("attractiveness", {})
                current["infrastructure"] = current.get("infrastructure", 50) + change.value
                modified["attractiveness"] = current

            elif change.type == "accessibility_boost":
                # Amélioration accessibilité (TGV, aéroport)
                current = modified.get("attractiveness", {})
                current["accessibilite"] = current.get("accessibilite", 50) + change.value
                modified["attractiveness"] = current

            elif change.type == "innovation_support":
                # Soutien innovation (incubateur, R&D)
                current = modified.get("attractiveness", {})
                current["innovation"] = current.get("innovation", 50) + change.value
                modified["attractiveness"] = current
                modified["policy_impact"] = modified.get("policy_impact", 0) + 0.15

            elif change.type == "housing_policy":
                # Politique logement
                current = modified.get("attractiveness", {})
                current["qualite_vie"] = current.get("qualite_vie", 50) + change.value
                modified["attractiveness"] = current

        return modified


# Scénarios prédéfinis
PREDEFINED_SCENARIOS: list[WhatIfScenario] = [
    WhatIfScenario(
        id="tax_reduction_10",
        name="Baisse impôts locaux 10%",
        description="Réduction de 10% de la taxe foncière pour attirer les entreprises",
        changes=[
            PolicyChange(
                type="tax_reduction",
                value=0.10,
                description="Réduction taxe foncière entreprises",
            )
        ],
        duration_months=36,
    ),
    WhatIfScenario(
        id="tax_reduction_20",
        name="Baisse impôts locaux 20%",
        description="Réduction significative de 20% pour compétitivité",
        changes=[
            PolicyChange(
                type="tax_reduction",
                value=0.20,
                description="Réduction taxe foncière entreprises",
            )
        ],
        duration_months=36,
    ),
    WhatIfScenario(
        id="new_tgv_line",
        name="Nouvelle ligne TGV",
        description="Construction d'une gare TGV réduisant le temps vers Paris",
        changes=[
            PolicyChange(
                type="accessibility_boost",
                value=25,
                description="Gain accessibilité +25 points",
            )
        ],
        duration_months=60,
    ),
    WhatIfScenario(
        id="tech_pole",
        name="Création pôle technologique",
        description="Investissement dans un incubateur tech avec subventions",
        changes=[
            PolicyChange(
                type="subsidy",
                target="62",
                value=5000000,
                description="Subvention 5M€ secteur informatique",
            ),
            PolicyChange(
                type="infrastructure",
                value=15,
                description="Incubateur 50 places",
            ),
            PolicyChange(
                type="innovation_support",
                value=20,
                description="Soutien R&D et startups",
            ),
        ],
        duration_months=48,
    ),
    WhatIfScenario(
        id="green_transition",
        name="Transition écologique",
        description="Plan de transition vers économie verte",
        changes=[
            PolicyChange(
                type="subsidy",
                target="35",
                value=3000000,
                description="Subvention énergies renouvelables",
            ),
            PolicyChange(
                type="innovation_support",
                value=10,
                description="Soutien cleantech",
            ),
        ],
        duration_months=60,
    ),
    WhatIfScenario(
        id="housing_boost",
        name="Plan logement",
        description="Construction logements sociaux et régulation prix",
        changes=[
            PolicyChange(
                type="housing_policy",
                value=15,
                description="Amélioration accès logement",
            )
        ],
        duration_months=48,
    ),
    WhatIfScenario(
        id="attractiveness_global",
        name="Plan attractivité global",
        description="Stratégie multi-axes pour améliorer l'attractivité",
        changes=[
            PolicyChange(
                type="tax_reduction",
                value=0.05,
                description="Légère baisse fiscale",
            ),
            PolicyChange(
                type="innovation_support",
                value=10,
                description="Soutien innovation",
            ),
            PolicyChange(
                type="housing_policy",
                value=10,
                description="Amélioration logement",
            ),
            PolicyChange(
                type="infrastructure",
                value=10,
                description="Modernisation infrastructures",
            ),
        ],
        duration_months=36,
    ),
]


def get_scenario(scenario_id: str) -> WhatIfScenario | None:
    """Get scenario by ID."""
    for scenario in PREDEFINED_SCENARIOS:
        if scenario.id == scenario_id:
            return scenario
    return None


def list_scenarios() -> list[dict[str, Any]]:
    """List all available scenarios."""
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "duration_months": s.duration_months,
        }
        for s in PREDEFINED_SCENARIOS
    ]
