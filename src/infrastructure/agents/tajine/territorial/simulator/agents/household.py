"""
Household Agent - Agent représentant un ménage.

Comportements:
- Migration vers territoires attractifs
- Recherche d'emploi
- Consommation locale/externe
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class HouseholdAgent:
    """
    Agent représentant un ménage du territoire.

    Simule les décisions de migration, emploi et consommation.
    """

    # Identité
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    size: int = 2  # Nombre de personnes

    # État
    income: float = 30000.0  # Revenu annuel
    employment_status: str = "employed"  # employed, unemployed, retired
    skills_level: str = "medium"  # low, medium, high

    # Localisation
    territory_code: str = ""
    commune_code: str = ""

    # Préférences (pondération 0-1)
    pref_employment: float = 0.4
    pref_quality_life: float = 0.3
    pref_cost: float = 0.3

    # Historique
    months_unemployed: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def decide_migration(
        self,
        current_attractiveness: dict[str, float],
        alternatives: dict[str, dict[str, float]],
    ) -> str | None:
        """
        Décide déménagement vers autre territoire.

        Args:
            current_attractiveness: Scores par axe du territoire actuel
            alternatives: Dict code -> scores par axe

        Returns:
            Code du nouveau territoire ou None
        """
        # Coût de déménagement (points d'utilité)
        moving_cost = 15

        # Calculer utilité actuelle
        current_utility = self._compute_utility(current_attractiveness)

        best_alternative = None
        best_gain = 0

        for code, scores in alternatives.items():
            utility = self._compute_utility(scores)
            gain = utility - current_utility - moving_cost

            # Bonus si chômeur et territoire offre meilleur emploi
            if self.employment_status == "unemployed":
                employment_boost = scores.get("capital_humain", 50) - current_attractiveness.get(
                    "capital_humain", 50
                )
                gain += employment_boost * 0.5

            if gain > best_gain:
                best_gain = gain
                best_alternative = code

        # Probabilité de migration proportionnelle au gain
        if best_alternative and random.random() < min(0.8, best_gain / 50):
            return best_alternative

        return None

    def _compute_utility(self, attractiveness: dict[str, float]) -> float:
        """Compute utility from attractiveness scores."""
        employment_score = attractiveness.get("capital_humain", 50)
        quality_score = attractiveness.get("qualite_vie", 50)
        cost_score = 100 - attractiveness.get("prix_logement", 50)  # Inverse

        return (
            self.pref_employment * employment_score
            + self.pref_quality_life * quality_score
            + self.pref_cost * cost_score
        )

    def decide_consumption(
        self, local_offer: dict[str, float]
    ) -> dict[str, float]:
        """
        Répartit consommation locale/externe.

        Args:
            local_offer: Quality scores by category

        Returns:
            Dict with local_pct and external_pct
        """
        # Base: 70% local, 30% external
        local_pct = 0.7

        # Ajuster selon qualité offre locale
        commerce_quality = local_offer.get("commerce", 50)
        services_quality = local_offer.get("services", 50)

        quality_factor = (commerce_quality + services_quality) / 100 - 0.5
        local_pct = max(0.3, min(0.9, local_pct + quality_factor * 0.3))

        return {"local_pct": local_pct, "external_pct": 1 - local_pct}

    def decide_job_search(
        self, offers: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """
        Accepte/refuse offres d'emploi.

        Args:
            offers: Liste d'offres avec salary, location, sector

        Returns:
            Offre acceptée ou None
        """
        if self.employment_status == "employed":
            # Employed: only consider significant improvements
            min_improvement = 1.2  # 20% raise minimum
        else:
            # Unemployed: more flexible
            min_improvement = 0.8

        for offer in offers:
            salary = offer.get("salary", 0)
            if salary >= self.income * min_improvement:
                # Location check
                if offer.get("location") == self.territory_code:
                    return offer
                # Remote or willing to relocate if unemployed
                if offer.get("remote") or self.months_unemployed > 6:
                    return offer

        return None

    def update_employment(self, found_job: bool, lost_job: bool) -> None:
        """Update employment status."""
        if found_job and self.employment_status == "unemployed":
            self.employment_status = "employed"
            self.months_unemployed = 0
        elif lost_job and self.employment_status == "employed":
            self.employment_status = "unemployed"
            self.months_unemployed = 0
        elif self.employment_status == "unemployed":
            self.months_unemployed += 1

    def step(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute one simulation step.

        Args:
            context: Simulation context

        Returns:
            Actions taken this step
        """
        actions = {"agent_id": self.id, "type": "household", "actions": []}

        # Migration decision
        current_attr = context.get("current_attractiveness", {})
        alternatives = context.get("attractiveness_alternatives", {})
        new_location = self.decide_migration(current_attr, alternatives)
        if new_location:
            actions["actions"].append(
                {
                    "action": "migration",
                    "from": self.territory_code,
                    "to": new_location,
                }
            )
            self.territory_code = new_location

        # Job search if unemployed
        if self.employment_status == "unemployed":
            offers = context.get("job_offers", [])
            accepted = self.decide_job_search(offers)
            if accepted:
                self.update_employment(found_job=True, lost_job=False)
                self.income = accepted.get("salary", self.income)
                actions["actions"].append(
                    {"action": "job_found", "salary": self.income}
                )
            else:
                self.months_unemployed += 1

        # Consumption
        local_offer = context.get("local_offer", {})
        consumption = self.decide_consumption(local_offer)
        actions["consumption"] = consumption

        # Record history
        self.history.append(
            {
                "territory": self.territory_code,
                "employment": self.employment_status,
                "income": self.income,
            }
        )

        return actions

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "size": self.size,
            "income": self.income,
            "employment_status": self.employment_status,
            "skills_level": self.skills_level,
            "territory_code": self.territory_code,
            "months_unemployed": self.months_unemployed,
        }

    @classmethod
    def create_random(
        cls, territory_code: str, income_median: float = 30000
    ) -> HouseholdAgent:
        """Create a random household agent."""
        # Random income around median
        income = max(15000, income_median * random.gauss(1, 0.3))

        # Random employment (based on typical rates)
        if random.random() < 0.08:  # ~8% unemployment
            status = "unemployed"
        elif random.random() < 0.25:  # ~25% retired
            status = "retired"
        else:
            status = "employed"

        # Skills correlated with income
        if income > income_median * 1.5:
            skills = "high"
        elif income < income_median * 0.7:
            skills = "low"
        else:
            skills = "medium"

        return cls(
            territory_code=territory_code,
            income=income,
            employment_status=status,
            skills_level=skills,
            size=random.choice([1, 2, 2, 3, 3, 4]),
        )
