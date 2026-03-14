"""
Simulation Engine - Moteur de simulation territoriale multi-agents.

Cycle de simulation mensuel:
1. UPDATE CONTEXT - Intégrer nouvelles données
2. AGENTS DECIDE - Entreprises/ménages prennent décisions
3. EXECUTE ACTIONS - Appliquer décisions
4. COMPUTE EFFECTS - Calculer impacts
5. RECORD STATE - Historiser
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

from .agents.enterprise import EnterpriseAgent
from .agents.household import HouseholdAgent
from .scenarios import WhatIfScenario


@dataclass
class MonthlySnapshot:
    """Snapshot d'un mois de simulation."""

    month: int
    date: str

    # Métriques clés
    total_enterprises: int
    total_employment: int
    creations: int
    closures: int
    relocations_in: int
    relocations_out: int

    total_households: int
    migrations_in: int
    migrations_out: int
    unemployment_rate: float

    # Attractivité
    attractiveness_score: float

    # Économique
    total_revenue: float
    fiscal_revenue: float


@dataclass
class SimulationResult:
    """Résultat complet d'une simulation."""

    territory_code: str
    territory_name: str
    scenario: WhatIfScenario | None
    duration_months: int
    computed_at: datetime

    # État initial et final
    initial_state: MonthlySnapshot
    final_state: MonthlySnapshot

    # Historique mensuel
    monthly_snapshots: list[MonthlySnapshot]

    # Métriques agrégées
    net_enterprise_change: int
    net_employment_change: int
    net_household_change: int
    avg_attractiveness_change: float

    # Analyse
    positive_effects: list[str]
    negative_effects: list[str]
    roi_estimate: float | None
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "scenario": self.scenario.to_dict() if self.scenario else None,
            "duration_months": self.duration_months,
            "computed_at": self.computed_at.isoformat(),
            "summary": {
                "net_enterprise_change": self.net_enterprise_change,
                "net_employment_change": self.net_employment_change,
                "net_household_change": self.net_household_change,
                "attractiveness_change": round(self.avg_attractiveness_change, 1),
            },
            "initial_state": self._snapshot_to_dict(self.initial_state),
            "final_state": self._snapshot_to_dict(self.final_state),
            "positive_effects": self.positive_effects,
            "negative_effects": self.negative_effects,
            "roi_estimate": self.roi_estimate,
            "recommendation": self.recommendation,
            "timeline": [
                {
                    "month": s.month,
                    "enterprises": s.total_enterprises,
                    "employment": s.total_employment,
                    "attractiveness": round(s.attractiveness_score, 1),
                }
                for s in self.monthly_snapshots[::3]  # Every 3 months
            ],
        }

    def _snapshot_to_dict(self, s: MonthlySnapshot) -> dict[str, Any]:
        return {
            "month": s.month,
            "enterprises": s.total_enterprises,
            "employment": s.total_employment,
            "households": s.total_households,
            "unemployment_rate": round(s.unemployment_rate, 1),
            "attractiveness": round(s.attractiveness_score, 1),
        }


class TerritorialSimulator:
    """
    Moteur de simulation territoriale multi-agents.

    Simule l'évolution d'un territoire sur plusieurs mois
    avec des agents entreprises et ménages autonomes.
    """

    def __init__(self) -> None:
        """Initialize the simulator."""
        self._enterprises: list[EnterpriseAgent] = []
        self._households: list[HouseholdAgent] = []
        self._attractiveness = 50.0
        self._scorer = None

    async def _get_scorer(self):
        """Lazy load attractiveness scorer."""
        if self._scorer is None:
            from ..attractiveness_scorer import AttractivenessScorer

            self._scorer = AttractivenessScorer()
        return self._scorer

    async def run(
        self,
        territory_code: str,
        scenario: WhatIfScenario | None = None,
        duration_months: int = 36,
        sample_size: int = 100,
    ) -> SimulationResult:
        """
        Run territorial simulation.

        Args:
            territory_code: Code département
            scenario: Optional What-If scenario to apply
            duration_months: Simulation duration in months
            sample_size: Number of enterprise agents (households = 10x)

        Returns:
            Complete SimulationResult
        """
        logger.info(
            f"Starting simulation for {territory_code}, "
            f"scenario={scenario.id if scenario else 'baseline'}, "
            f"duration={duration_months}m"
        )

        # Initialize agents
        await self._initialize_agents(territory_code, sample_size)

        # Get initial attractiveness
        scorer = await self._get_scorer()
        initial_score = await scorer.score(territory_code)
        self._attractiveness = initial_score.global_score

        # Record initial state
        initial_state = self._create_snapshot(0, initial_score.global_score)
        snapshots = [initial_state]

        # Base context - attractiveness dict for household agents
        attractiveness_dict = {
            axis.value: initial_score.axes[axis].score for axis in initial_score.axes
        }
        base_context = {
            "territory_code": territory_code,
            "current_attractiveness": attractiveness_dict,  # Dict for household agents
            "attractiveness": attractiveness_dict,
            "market_conditions": {
                "demand_growth": 0.02,
                "unemployment": 8,
                "attractiveness": initial_score.global_score,
            },
            "policy_impact": 0,
        }

        # Apply scenario if provided
        if scenario:
            base_context = scenario.apply_to_context(base_context)

        # Run simulation
        for month in range(1, duration_months + 1):
            # Update context with some randomness
            context = self._update_context(base_context, month)

            # Step all agents
            await self._step_all_agents(context)

            # Update attractiveness based on agent activity
            self._update_attractiveness(scenario is not None)

            # Record snapshot
            snapshot = self._create_snapshot(month, self._attractiveness)
            snapshots.append(snapshot)

            if month % 6 == 0:
                logger.debug(
                    f"Month {month}: {len(self._enterprises)} enterprises, "
                    f"attractiveness={self._attractiveness:.1f}"
                )

        # Final state
        final_state = snapshots[-1]

        # Analyze results
        result = self._analyze_results(
            territory_code=territory_code,
            territory_name=initial_score.territory_name,
            scenario=scenario,
            initial_state=initial_state,
            final_state=final_state,
            snapshots=snapshots,
        )

        logger.info(
            f"Simulation complete: {result.net_enterprise_change:+d} enterprises, "
            f"{result.net_employment_change:+d} employment"
        )

        return result

    async def _initialize_agents(self, territory_code: str, sample_size: int) -> None:
        """Initialize enterprise and household agents."""
        self._enterprises = []
        self._households = []

        # Try to load real enterprises from SIRENE
        try:
            from src.infrastructure.datasources.adapters.sirene import SireneAdapter

            sirene = SireneAdapter()
            data = await sirene.search(
                {"departement": territory_code, "per_page": min(sample_size, 25)}
            )
            results = data.get("results", []) if data else []

            for company in results:
                agent = EnterpriseAgent.from_sirene(company)
                self._enterprises.append(agent)

        except Exception as e:
            logger.warning(f"Could not load SIRENE data: {e}")

        # Fill remaining with synthetic agents
        while len(self._enterprises) < sample_size:
            agent = EnterpriseAgent(
                territory_code=territory_code,
                secteur=random.choice(["62", "47", "56", "70", "41", "86"]),
                effectif=random.randint(1, 50),
                health_score=random.gauss(0.5, 0.15),
                age_months=random.randint(6, 120),
            )
            self._enterprises.append(agent)

        # Create households (10x enterprises)
        household_count = sample_size * 10
        for _ in range(household_count):
            household = HouseholdAgent.create_random(territory_code)
            self._households.append(household)

        logger.info(
            f"Initialized {len(self._enterprises)} enterprises, {len(self._households)} households"
        )

    def _update_context(self, base_context: dict, month: int) -> dict:
        """Update context with monthly variations."""
        context = base_context.copy()

        # Add some randomness to market conditions
        market = context.get("market_conditions", {}).copy()
        market["demand_growth"] = market.get("demand_growth", 0) + random.gauss(0, 0.02)
        context["market_conditions"] = market

        # Seasonal effects
        if month % 12 in [6, 7, 8]:  # Summer
            context["market_conditions"]["demand_growth"] -= 0.01
        elif month % 12 in [11, 12, 1]:  # Holiday season
            context["market_conditions"]["demand_growth"] += 0.01

        return context

    async def _step_all_agents(self, context: dict) -> None:
        """Execute one simulation step for all agents."""
        # Step enterprises
        closures = []
        for enterprise in self._enterprises:
            # Add revenue growth variation
            ent_context = context.copy()
            ent_context["revenue_growth"] = random.gauss(0, 0.1)

            actions = enterprise.step(ent_context)

            # Track closures
            for action in actions.get("actions", []):
                if action.get("action") == "closure":
                    closures.append(enterprise)

        # Remove closed enterprises
        for closed in closures:
            self._enterprises.remove(closed)

        # Occasionally add new enterprises (creations)
        creation_rate = 0.02 + context.get("policy_impact", 0) * 0.01
        if random.random() < creation_rate:
            new_enterprise = EnterpriseAgent(
                territory_code=context["territory_code"],
                secteur=random.choice(["62", "70", "47"]),
                effectif=random.randint(1, 5),
                health_score=0.5,
                age_months=0,
            )
            self._enterprises.append(new_enterprise)

        # Step households (sample for performance)
        sample = random.sample(self._households, min(100, len(self._households)))
        for household in sample:
            household.step(context)

    def _update_attractiveness(self, has_scenario: bool) -> None:
        """Update attractiveness based on agent activity."""
        # Calculate enterprise health
        if self._enterprises:
            avg_health = sum(e.health_score for e in self._enterprises) / len(self._enterprises)
            total_employment = sum(e.effectif for e in self._enterprises)
        else:
            avg_health = 0.5
            total_employment = 0

        # Attractiveness influenced by enterprise health
        health_impact = (avg_health - 0.5) * 10

        # Employment impact
        employment_impact = min(5, total_employment / 1000)

        # Update attractiveness
        delta = health_impact + employment_impact
        if has_scenario:
            delta *= 1.2  # Scenarios have slightly amplified effect

        self._attractiveness = max(0, min(100, self._attractiveness + delta * 0.1))

    def _create_snapshot(self, month: int, attractiveness: float) -> MonthlySnapshot:
        """Create monthly snapshot of simulation state."""
        total_employment = sum(e.effectif for e in self._enterprises)

        employed_households = sum(1 for h in self._households if h.employment_status == "employed")
        total_active = sum(1 for h in self._households if h.employment_status != "retired")
        unemployment_rate = (1 - employed_households / total_active) * 100 if total_active else 8

        return MonthlySnapshot(
            month=month,
            date=f"M+{month}",
            total_enterprises=len(self._enterprises),
            total_employment=total_employment,
            creations=0,  # Would track from previous month
            closures=0,
            relocations_in=0,
            relocations_out=0,
            total_households=len(self._households),
            migrations_in=0,
            migrations_out=0,
            unemployment_rate=unemployment_rate,
            attractiveness_score=attractiveness,
            total_revenue=total_employment * 50000,  # Simplified
            fiscal_revenue=total_employment * 5000,  # Simplified
        )

    def _analyze_results(
        self,
        territory_code: str,
        territory_name: str,
        scenario: WhatIfScenario | None,
        initial_state: MonthlySnapshot,
        final_state: MonthlySnapshot,
        snapshots: list[MonthlySnapshot],
    ) -> SimulationResult:
        """Analyze simulation results and generate insights."""
        # Calculate changes
        net_enterprise = final_state.total_enterprises - initial_state.total_enterprises
        net_employment = final_state.total_employment - initial_state.total_employment
        net_household = final_state.total_households - initial_state.total_households
        attr_change = final_state.attractiveness_score - initial_state.attractiveness_score

        # Identify effects
        positive_effects = []
        negative_effects = []

        if net_enterprise > 0:
            positive_effects.append(f"+{net_enterprise} créations d'entreprises nettes")
        elif net_enterprise < 0:
            negative_effects.append(f"{net_enterprise} entreprises (solde négatif)")

        if net_employment > 0:
            positive_effects.append(f"+{net_employment} emplois créés")
        elif net_employment < 0:
            negative_effects.append(f"{net_employment} emplois perdus")

        if attr_change > 2:
            positive_effects.append(f"+{attr_change:.1f} points d'attractivité")
        elif attr_change < -2:
            negative_effects.append(f"{attr_change:.1f} points d'attractivité")

        if final_state.unemployment_rate < initial_state.unemployment_rate:
            positive_effects.append(
                f"Baisse chômage: {initial_state.unemployment_rate:.1f}% → "
                f"{final_state.unemployment_rate:.1f}%"
            )
        elif final_state.unemployment_rate > initial_state.unemployment_rate:
            negative_effects.append(
                f"Hausse chômage: {initial_state.unemployment_rate:.1f}% → "
                f"{final_state.unemployment_rate:.1f}%"
            )

        # ROI estimate (simplified)
        roi = None
        if scenario:
            # Estimate fiscal return vs investment
            fiscal_gain = final_state.fiscal_revenue - initial_state.fiscal_revenue
            # Very simplified ROI
            roi = fiscal_gain / 1000000 if fiscal_gain > 0 else -1

        # Recommendation
        if net_employment > 100 and attr_change > 0:
            recommendation = "Scénario fortement recommandé - impact positif significatif"
        elif net_employment > 0 and attr_change >= 0:
            recommendation = "Scénario recommandé - impact globalement positif"
        elif net_employment < -100 or attr_change < -5:
            recommendation = "Scénario déconseillé - risque d'impact négatif"
        else:
            recommendation = "Impact neutre - évaluer d'autres critères"

        return SimulationResult(
            territory_code=territory_code,
            territory_name=territory_name,
            scenario=scenario,
            duration_months=len(snapshots) - 1,
            computed_at=datetime.now(),
            initial_state=initial_state,
            final_state=final_state,
            monthly_snapshots=snapshots,
            net_enterprise_change=net_enterprise,
            net_employment_change=net_employment,
            net_household_change=net_household,
            avg_attractiveness_change=attr_change,
            positive_effects=positive_effects,
            negative_effects=negative_effects,
            roi_estimate=roi,
            recommendation=recommendation,
        )
