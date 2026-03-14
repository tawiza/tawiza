"""
Territorial Analysis Tools - Outils TAJINE pour analyse territoriale.

Ces outils permettent à l'agent TAJINE d'analyser des territoires:
- Attractivité multi-axes
- Comparaison avec voisins/concurrents
- Simulation What-If

Usage:
    from src.infrastructure.agents.tajine.territorial.tools import AnalyzeTerritoryTool

    tool = AnalyzeTerritoryTool()
    result = await tool.execute(code="75", aspects=["attractiveness", "competitors"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.infrastructure.tools.base import BaseTool, ToolResult

from .attractiveness_scorer import AttractivenessScore, AttractivenessScorer
from .competitor_analyzer import CompetitorAnalysis, CompetitorAnalyzer
from .simulator import SimulationResult, TerritorialSimulator, WhatIfScenario
from .simulator.scenarios import get_scenario, list_scenarios


@dataclass
class TerritorialAnalysis:
    """Résultat complet d'une analyse territoriale."""

    territory_code: str
    territory_name: str

    # Analyses effectuées
    attractiveness: AttractivenessScore | None = None
    competitors: CompetitorAnalysis | None = None
    simulation: SimulationResult | None = None

    # Synthèse
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    threats: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "swot": {
                "strengths": self.strengths,
                "weaknesses": self.weaknesses,
                "opportunities": self.opportunities,
                "threats": self.threats,
            },
            "recommendation": self.recommendation,
        }

        if self.attractiveness:
            result["attractiveness"] = self.attractiveness.to_dict()

        if self.competitors:
            result["competitors"] = self.competitors.to_dict()

        if self.simulation:
            result["simulation"] = self.simulation.to_dict()

        return result

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [f"## Analyse territoriale: {self.territory_name} ({self.territory_code})"]

        if self.attractiveness:
            lines.append(f"\n### Attractivité globale: {self.attractiveness.global_score:.1f}/100")
            if self.attractiveness.rank_national:
                lines.append(f"- Rang national: #{self.attractiveness.rank_national}")
            for axis, score in self.attractiveness.axes.items():
                # trend is a string: "up", "down", "stable"
                trend = "↑" if score.trend == "up" else "↓" if score.trend == "down" else "→"
                lines.append(f"- {axis.value}: {score.score:.1f}/100 {trend}")

        if self.competitors:
            lines.append("\n### Position concurrentielle")
            lines.append(f"- Écart vs voisins: {self.competitors.gap_vs_neighbors:+.1f} points")
            if self.competitors.ranking:
                lines.append(f"- Meilleur axe: {self.competitors.ranking[0].code}")

        if self.simulation:
            lines.append(f"\n### Simulation ({self.simulation.duration_months} mois)")
            lines.append(f"- Entreprises: {self.simulation.net_enterprise_change:+d}")
            lines.append(f"- Emplois: {self.simulation.net_employment_change:+d}")
            lines.append(f"- Attractivité: {self.simulation.avg_attractiveness_change:+.1f}")

        if self.strengths:
            lines.append("\n### Forces")
            for s in self.strengths[:3]:
                lines.append(f"- {s}")

        if self.weaknesses:
            lines.append("\n### Faiblesses")
            for w in self.weaknesses[:3]:
                lines.append(f"- {w}")

        if self.recommendation:
            lines.append(f"\n### Recommandation\n{self.recommendation}")

        return "\n".join(lines)


class AnalyzeTerritoryTool(BaseTool):
    """
    Outil TAJINE pour analyse territoriale complète.

    Permet d'analyser un département français selon plusieurs aspects:
    - attractiveness: Score d'attractivité multi-axes
    - competitors: Comparaison avec voisins et territoires similaires
    - simulation: Simulation What-If avec scénarios de politique publique

    Example:
        result = await tool.execute(
            code="69",
            aspects=["attractiveness", "competitors"],
            scenario="tech_pole"
        )
    """

    def __init__(self) -> None:
        """Initialize with lazy-loaded analyzers."""
        self._scorer: AttractivenessScorer | None = None
        self._competitor_analyzer: CompetitorAnalyzer | None = None
        self._simulator: TerritorialSimulator | None = None

    @property
    def name(self) -> str:
        """Tool name."""
        return "analyze_territory"

    @property
    def description(self) -> str:
        """Tool description for LLM."""
        return """Analyse un territoire français (département) selon plusieurs dimensions:
- attractiveness: Score d'attractivité sur 6 axes
- competitors: Comparaison avec départements voisins
- simulation: Simulation What-If de politiques publiques

Paramètres:
- code: Code département (ex: "75" pour Paris, "69" pour Rhône)
- aspects: Liste des analyses ["attractiveness", "competitors", "simulation"]
- scenario: ID de scénario pour simulation (optionnel)"""

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Code département français (2-3 chiffres)",
                },
                "aspects": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Types d'analyses: attractiveness, competitors, simulation",
                    "default": ["attractiveness"],
                },
                "scenario": {
                    "type": "string",
                    "description": "ID de scénario pour simulation What-If",
                },
                "simulation_months": {
                    "type": "integer",
                    "description": "Durée de simulation en mois",
                    "default": 36,
                },
            },
            "required": ["code"],
        }

    async def _get_scorer(self) -> AttractivenessScorer:
        """Lazy load attractiveness scorer."""
        if self._scorer is None:
            self._scorer = AttractivenessScorer()
        return self._scorer

    async def _get_competitor_analyzer(self) -> CompetitorAnalyzer:
        """Lazy load competitor analyzer."""
        if self._competitor_analyzer is None:
            self._competitor_analyzer = CompetitorAnalyzer()
        return self._competitor_analyzer

    async def _get_simulator(self) -> TerritorialSimulator:
        """Lazy load simulator."""
        if self._simulator is None:
            self._simulator = TerritorialSimulator()
        return self._simulator

    async def execute(
        self,
        code: str,
        aspects: list[str] | None = None,
        scenario: str | None = None,
        simulation_months: int = 36,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute territorial analysis.

        Args:
            code: Department code (e.g., "75", "69")
            aspects: List of analysis types to perform
            scenario: Scenario ID for simulation
            simulation_months: Duration of simulation in months

        Returns:
            ToolResult with TerritorialAnalysis
        """
        if aspects is None:
            aspects = ["attractiveness"]

        logger.info(f"Analyzing territory {code} with aspects: {aspects}")

        # Validate code
        if not code or not code.isdigit() or len(code) > 3:
            return ToolResult(
                success=False,
                error=f"Invalid department code: {code}. Expected 2-3 digit code.",
            )

        # Initialize result
        territory_name = await self._get_territory_name(code)
        analysis = TerritorialAnalysis(
            territory_code=code,
            territory_name=territory_name,
        )

        try:
            # Run requested analyses
            if "attractiveness" in aspects:
                scorer = await self._get_scorer()
                analysis.attractiveness = await scorer.score(code)
                logger.debug(f"Attractiveness score: {analysis.attractiveness.global_score:.1f}")

            if "competitors" in aspects:
                # Need attractiveness first
                if analysis.attractiveness is None:
                    scorer = await self._get_scorer()
                    analysis.attractiveness = await scorer.score(code)

                analyzer = await self._get_competitor_analyzer()
                analysis.competitors = await analyzer.compare(code, analysis.attractiveness)
                logger.debug(f"Competitor gap: {analysis.competitors.gap_vs_neighbors:+.1f}")

            if "simulation" in aspects:
                simulator = await self._get_simulator()

                # Get scenario if specified
                what_if: WhatIfScenario | None = None
                if scenario:
                    what_if = get_scenario(scenario)
                    if what_if is None:
                        available = [s["id"] for s in list_scenarios()]
                        return ToolResult(
                            success=False,
                            error=f"Unknown scenario: {scenario}. Available: {available}",
                        )

                analysis.simulation = await simulator.run(
                    territory_code=code,
                    scenario=what_if,
                    duration_months=simulation_months,
                )
                logger.debug(f"Simulation: {analysis.simulation.net_employment_change:+d} emplois")

            # Generate SWOT analysis
            self._generate_swot(analysis)

            # Generate recommendation
            analysis.recommendation = self._generate_recommendation(analysis)

            return ToolResult(
                success=True,
                output=analysis.to_dict(),
                metadata={"summary": analysis.summary()},
            )

        except Exception as e:
            logger.exception(f"Error analyzing territory {code}")
            return ToolResult(
                success=False,
                error=f"Analysis failed: {e!s}",
            )

    async def _get_territory_name(self, code: str) -> str:
        """Get territory name from code."""
        DEPT_NAMES = {
            "01": "Ain",
            "02": "Aisne",
            "03": "Allier",
            "04": "Alpes-de-Haute-Provence",
            "05": "Hautes-Alpes",
            "06": "Alpes-Maritimes",
            "07": "Ardèche",
            "08": "Ardennes",
            "09": "Ariège",
            "10": "Aube",
            "11": "Aude",
            "12": "Aveyron",
            "13": "Bouches-du-Rhône",
            "14": "Calvados",
            "15": "Cantal",
            "16": "Charente",
            "17": "Charente-Maritime",
            "18": "Cher",
            "19": "Corrèze",
            "21": "Côte-d'Or",
            "22": "Côtes-d'Armor",
            "23": "Creuse",
            "24": "Dordogne",
            "25": "Doubs",
            "26": "Drôme",
            "27": "Eure",
            "28": "Eure-et-Loir",
            "29": "Finistère",
            "2A": "Corse-du-Sud",
            "2B": "Haute-Corse",
            "30": "Gard",
            "31": "Haute-Garonne",
            "32": "Gers",
            "33": "Gironde",
            "34": "Hérault",
            "35": "Ille-et-Vilaine",
            "36": "Indre",
            "37": "Indre-et-Loire",
            "38": "Isère",
            "39": "Jura",
            "40": "Landes",
            "41": "Loir-et-Cher",
            "42": "Loire",
            "43": "Haute-Loire",
            "44": "Loire-Atlantique",
            "45": "Loiret",
            "46": "Lot",
            "47": "Lot-et-Garonne",
            "48": "Lozère",
            "49": "Maine-et-Loire",
            "50": "Manche",
            "51": "Marne",
            "52": "Haute-Marne",
            "53": "Mayenne",
            "54": "Meurthe-et-Moselle",
            "55": "Meuse",
            "56": "Morbihan",
            "57": "Moselle",
            "58": "Nièvre",
            "59": "Nord",
            "60": "Oise",
            "61": "Orne",
            "62": "Pas-de-Calais",
            "63": "Puy-de-Dôme",
            "64": "Pyrénées-Atlantiques",
            "65": "Hautes-Pyrénées",
            "66": "Pyrénées-Orientales",
            "67": "Bas-Rhin",
            "68": "Haut-Rhin",
            "69": "Rhône",
            "70": "Haute-Saône",
            "71": "Saône-et-Loire",
            "72": "Sarthe",
            "73": "Savoie",
            "74": "Haute-Savoie",
            "75": "Paris",
            "76": "Seine-Maritime",
            "77": "Seine-et-Marne",
            "78": "Yvelines",
            "79": "Deux-Sèvres",
            "80": "Somme",
            "81": "Tarn",
            "82": "Tarn-et-Garonne",
            "83": "Var",
            "84": "Vaucluse",
            "85": "Vendée",
            "86": "Vienne",
            "87": "Haute-Vienne",
            "88": "Vosges",
            "89": "Yonne",
            "90": "Territoire de Belfort",
            "91": "Essonne",
            "92": "Hauts-de-Seine",
            "93": "Seine-Saint-Denis",
            "94": "Val-de-Marne",
            "95": "Val-d'Oise",
            "971": "Guadeloupe",
            "972": "Martinique",
            "973": "Guyane",
            "974": "La Réunion",
            "976": "Mayotte",
        }
        return DEPT_NAMES.get(code, f"Département {code}")

    def _generate_swot(self, analysis: TerritorialAnalysis) -> None:
        """Generate SWOT analysis from results."""
        # Strengths from high attractiveness scores
        if analysis.attractiveness:
            for axis, score in analysis.attractiveness.axes.items():
                if score.score >= 60:
                    analysis.strengths.append(f"{axis.value} ({score.score:.0f}/100)")
                elif score.score <= 40:
                    analysis.weaknesses.append(f"{axis.value} ({score.score:.0f}/100)")

        # Competitive position
        if analysis.competitors:
            if analysis.competitors.gap_vs_neighbors > 5:
                analysis.strengths.append(
                    f"Position concurrentielle favorable (+{analysis.competitors.gap_vs_neighbors:.1f} vs voisins)"
                )
            elif analysis.competitors.gap_vs_neighbors < -5:
                analysis.threats.append(
                    f"Position concurrentielle défavorable ({analysis.competitors.gap_vs_neighbors:.1f} vs voisins)"
                )

            # Best and worst performers
            if analysis.competitors.ranking:
                best = analysis.competitors.ranking[0]
                analysis.opportunities.append(
                    f"S'inspirer de {best.name} ({best.global_score:.1f}/100)"
                )

        # Simulation insights
        if analysis.simulation:
            if analysis.simulation.net_employment_change > 0:
                analysis.opportunities.append(
                    f"Potentiel création {analysis.simulation.net_employment_change} emplois"
                )
            elif analysis.simulation.net_employment_change < 0:
                analysis.threats.append(
                    f"Risque perte {abs(analysis.simulation.net_employment_change)} emplois"
                )

    def _generate_recommendation(self, analysis: TerritorialAnalysis) -> str:
        """Generate strategic recommendation."""
        recommendations = []

        # Based on attractiveness
        if analysis.attractiveness:
            # Find weakest axis
            weakest = min(
                analysis.attractiveness.axes.items(),
                key=lambda x: x[1].score,
            )
            if weakest[1].score < 40:
                recommendations.append(
                    f"Priorité: renforcer {weakest[0].value} "
                    f"(actuellement {weakest[1].score:.0f}/100)"
                )

            # Find axes with negative trends
            declining = [
                (axis, score)
                for axis, score in analysis.attractiveness.axes.items()
                if score.trend == "down"
            ]
            if declining:
                for axis, score in declining[:2]:
                    recommendations.append(
                        f"Attention: {axis.value} en déclin (tendance: {score.trend})"
                    )

        # Based on competitors
        if analysis.competitors and analysis.competitors.gap_vs_neighbors < 0:
            recommendations.append("Stratégie: combler l'écart avec les territoires voisins")

        # Based on simulation
        if analysis.simulation:
            if analysis.simulation.recommendation:
                recommendations.append(analysis.simulation.recommendation)

        if not recommendations:
            recommendations.append(
                "Maintenir les acquis et surveiller l'évolution des territoires voisins"
            )

        return " | ".join(recommendations)


class ListScenariosToolTool(BaseTool):
    """Tool to list available What-If scenarios."""

    name = "list_territorial_scenarios"
    description = "Liste les scénarios What-If disponibles pour la simulation territoriale"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """List available scenarios."""
        scenarios = list_scenarios()
        return ToolResult(
            success=True,
            output={"scenarios": scenarios},
            metadata={"message": f"Scénarios disponibles: {', '.join(s['id'] for s in scenarios)}"},
        )
