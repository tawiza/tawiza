"""
Enterprise Agent - Agent représentant une entreprise du territoire.

Comportements:
- Embauche/licenciement selon conditions marché
- Expansion vers nouveaux établissements
- Fermeture si santé financière critique
- Relocalisation vers territoires plus attractifs
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class EnterpriseAgent:
    """
    Agent représentant une entreprise du territoire.

    Inspiré du modèle SimCity adapté au contexte français.
    """

    # Identité
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    siren: str = ""
    denomination: str = ""
    secteur: str = ""  # NAF 2 digits

    # État
    effectif: int = 1
    ca: float = 0.0
    age_months: int = 0
    health_score: float = 0.5  # 0-1

    # Localisation
    territory_code: str = ""
    commune_code: str = ""

    # Historique
    history: list[dict[str, Any]] = field(default_factory=list)

    def decide_hiring(self, market_conditions: dict[str, float]) -> int:
        """
        Décide embauches/licenciements selon conditions marché.

        Args:
            market_conditions: Dict avec demand_growth, unemployment, attractiveness

        Returns:
            Variation effectif (positif = embauche, négatif = licenciement)
        """
        demand_growth = market_conditions.get("demand_growth", 0)
        unemployment = market_conditions.get("unemployment", 8)
        attractiveness = market_conditions.get("attractiveness", 50)

        # Facteurs influençant l'embauche
        # Demande croissante + bonne santé + attractivité = embauche
        hiring_pressure = (
            demand_growth * 0.4 + self.health_score * 0.3 + (attractiveness - 50) / 100 * 0.3
        )

        # Coût embauche inversement proportionnel au chômage
        hiring_cost = 1 - unemployment / 20  # Plus il y a de chômage, moins cher

        # Décision
        if hiring_pressure > 0.2 and self.health_score > 0.4:
            # Embauche possible
            new_hires = max(1, int(self.effectif * hiring_pressure * (1 - hiring_cost)))
            return min(new_hires, max(1, self.effectif // 5))  # Max 20% croissance
        elif hiring_pressure < -0.2 or self.health_score < 0.3:
            # Licenciement
            layoffs = max(1, int(self.effectif * abs(hiring_pressure)))
            return -min(layoffs, self.effectif - 1)  # Garde au moins 1
        else:
            return 0

    def decide_expansion(self, opportunities: list[dict]) -> bool:
        """
        Décide d'ouvrir nouvel établissement.

        Args:
            opportunities: Liste de territoires attractifs avec scores

        Returns:
            True si expansion décidée
        """
        # Conditions d'expansion
        if self.health_score < 0.6:
            return False
        if self.age_months < 24:
            return False
        if self.effectif < 10:
            return False

        # Probabilité d'expansion basée sur santé et taille
        expansion_prob = self.health_score * 0.3 + min(0.3, self.effectif / 100)

        return random.random() < expansion_prob

    def decide_closure(self, financial_health: float) -> bool:
        """
        Décide fermeture si santé critique.

        Args:
            financial_health: Score santé 0-1

        Returns:
            True si fermeture décidée
        """
        self.health_score = financial_health

        # Fermeture si santé < 0.1 avec certitude
        if financial_health < 0.1:
            return True

        # Probabilité croissante de fermeture si santé < 0.3
        if financial_health < 0.3:
            closure_prob = (0.3 - financial_health) * 2
            return random.random() < closure_prob

        return False

    def decide_relocation(
        self, current_attractiveness: float, alternatives: dict[str, float]
    ) -> str | None:
        """
        Décide migration vers autre territoire.

        Args:
            current_attractiveness: Score attractivité actuel
            alternatives: Dict code_territoire -> score attractivité

        Returns:
            Code du nouveau territoire ou None
        """
        # Jeunes entreprises plus mobiles
        mobility_factor = 1.0 if self.age_months < 36 else 0.5

        # Coût de relocalisation
        relocation_cost = 10  # Points d'attractivité minimum pour bouger

        for code, score in alternatives.items():
            delta = score - current_attractiveness
            if delta > relocation_cost * mobility_factor:
                # Probabilité proportionnelle au gain
                if random.random() < delta / 50:
                    return code

        return None

    def update_health(
        self,
        revenue_growth: float,
        market_conditions: dict[str, float],
        policy_impact: float = 0,
    ) -> None:
        """
        Met à jour la santé financière.

        Args:
            revenue_growth: Croissance CA (-1 to 1)
            market_conditions: Conditions marché
            policy_impact: Impact politiques publiques (-1 to 1)
        """
        # Base: croissance revenue
        health_delta = revenue_growth * 0.3

        # Impact marché
        demand = market_conditions.get("demand_growth", 0)
        health_delta += demand * 0.2

        # Impact politiques (subventions, fiscalité)
        health_delta += policy_impact * 0.2

        # Effet taille (grandes entreprises plus stables)
        size_stability = min(0.1, self.effectif / 500)
        health_delta += size_stability

        # Effet âge (entreprises établies plus stables)
        age_stability = min(0.1, self.age_months / 120)
        health_delta += age_stability

        # Update with decay toward equilibrium
        self.health_score = max(0, min(1, self.health_score + health_delta))

        # Record history
        self.history.append(
            {
                "month": self.age_months,
                "health": self.health_score,
                "effectif": self.effectif,
            }
        )

    def step(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute one simulation step.

        Args:
            context: Simulation context with market conditions, policies, etc.

        Returns:
            Actions taken this step
        """
        self.age_months += 1
        actions = {"agent_id": self.id, "type": "enterprise", "actions": []}

        # Update health
        revenue_growth = context.get("revenue_growth", 0)
        market = context.get("market_conditions", {})
        policy = context.get("policy_impact", 0)
        self.update_health(revenue_growth, market, policy)

        # Check closure
        if self.decide_closure(self.health_score):
            actions["actions"].append({"action": "closure", "effectif_lost": self.effectif})
            self.effectif = 0
            return actions

        # Hiring decision
        hiring_change = self.decide_hiring(market)
        if hiring_change != 0:
            self.effectif = max(1, self.effectif + hiring_change)
            actions["actions"].append({"action": "hiring", "delta": hiring_change})

        # Expansion decision
        if self.decide_expansion(context.get("opportunities", [])):
            actions["actions"].append({"action": "expansion"})

        # Relocation decision
        alternatives = context.get("attractiveness_alternatives", {})
        current_attr = context.get("current_attractiveness", 50)
        new_location = self.decide_relocation(current_attr, alternatives)
        if new_location:
            actions["actions"].append(
                {
                    "action": "relocation",
                    "from": self.territory_code,
                    "to": new_location,
                }
            )
            self.territory_code = new_location

        return actions

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "siren": self.siren,
            "denomination": self.denomination,
            "secteur": self.secteur,
            "effectif": self.effectif,
            "ca": self.ca,
            "age_months": self.age_months,
            "health_score": round(self.health_score, 2),
            "territory_code": self.territory_code,
        }

    @classmethod
    def from_sirene(cls, data: dict[str, Any]) -> EnterpriseAgent:
        """Create agent from SIRENE data."""
        return cls(
            siren=data.get("siren", ""),
            denomination=data.get("denomination", ""),
            secteur=data.get("activite_principale", "")[:2]
            if data.get("activite_principale")
            else "",
            effectif=cls._parse_effectif(data.get("tranche_effectif_salarie")),
            territory_code=data.get("code_postal", "")[:2] if data.get("code_postal") else "",
            age_months=cls._compute_age(data.get("date_creation")),
            health_score=0.5,  # Default neutral
        )

    @staticmethod
    def _parse_effectif(tranche: str | None) -> int:
        """Parse effectif from tranche code."""
        TRANCHES = {
            "00": 0,
            "01": 2,
            "02": 5,
            "03": 9,
            "11": 15,
            "12": 35,
            "21": 75,
            "22": 150,
            "31": 350,
            "32": 750,
            "41": 1500,
            "42": 3500,
            "51": 7500,
            "52": 10000,
        }
        return TRANCHES.get(tranche or "00", 1)

    @staticmethod
    def _compute_age(date_creation: str | None) -> int:
        """Compute age in months from creation date."""
        if not date_creation:
            return 60  # Default 5 years

        try:
            from datetime import datetime

            created = datetime.fromisoformat(date_creation)
            delta = datetime.now() - created
            return max(1, delta.days // 30)
        except (ValueError, TypeError):
            return 60
