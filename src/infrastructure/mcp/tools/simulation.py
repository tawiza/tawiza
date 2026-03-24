"""MCP Tools for Economic Scenario Simulation.

Simulates the impact of economic events on a territorial market using
LLM-powered predictions. Inspired by OASIS but adapted for territorial
intelligence use cases.

Reference: https://github.com/camel-ai/oasis
"""

import json
from dataclasses import dataclass, field

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP


@dataclass
class Actor:
    """An economic actor in the simulation."""

    id: str
    type: str  # enterprise, institution, investor, media
    name: str
    influence: float  # 0-100
    sector: str
    position: str  # for institutions: supportive, neutral, restrictive
    resources: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "influence": self.influence,
            "sector": self.sector,
            "position": self.position,
            "resources": self.resources,
        }


@dataclass
class SimulationEvent:
    """An event in the simulation."""

    type: str
    description: str
    affected_sectors: list[str]
    magnitude: float  # 0-100 impact magnitude
    duration: str  # short, medium, long

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "description": self.description,
            "affected_sectors": self.affected_sectors,
            "magnitude": self.magnitude,
            "duration": self.duration,
        }


@dataclass
class SimulationResult:
    """Results from a scenario simulation."""

    scenario: str
    territory: str
    event: SimulationEvent
    impacts: list[dict]
    predictions: dict
    recommendations: list[str]
    confidence: float

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "territory": self.territory,
            "event": self.event.to_dict(),
            "impacts": self.impacts,
            "predictions": self.predictions,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
        }


# Predefined scenarios
SCENARIOS = {
    "new_startup": {
        "name": "Nouvelle startup innovante",
        "description": "Une nouvelle startup leve des fonds et s'installe sur le territoire",
        "event_type": "market_entry",
        "magnitude": 40,
        "duration": "medium",
        "affected_sectors": ["tech", "innovation", "emploi"],
    },
    "company_closure": {
        "name": "Fermeture d'entreprise majeure",
        "description": "Une entreprise importante ferme ses portes",
        "event_type": "market_exit",
        "magnitude": 70,
        "duration": "long",
        "affected_sectors": ["emploi", "immobilier", "sous-traitance"],
    },
    "new_regulation": {
        "name": "Nouvelle reglementation",
        "description": "Introduction d'une nouvelle reglementation impactant le secteur",
        "event_type": "regulatory",
        "magnitude": 50,
        "duration": "long",
        "affected_sectors": ["compliance", "juridique", "adaptation"],
    },
    "funding_round": {
        "name": "Levee de fonds importante",
        "description": "Une entreprise locale realise une levee de fonds significative",
        "event_type": "investment",
        "magnitude": 55,
        "duration": "medium",
        "affected_sectors": ["tech", "emploi", "immobilier"],
    },
    "market_expansion": {
        "name": "Expansion de marche",
        "description": "Un acteur majeur etend ses activites sur le territoire",
        "event_type": "market_entry",
        "magnitude": 60,
        "duration": "long",
        "affected_sectors": ["emploi", "concurrence", "partenariats"],
    },
    "tech_disruption": {
        "name": "Disruption technologique",
        "description": "Une nouvelle technologie bouleverse le marche local",
        "event_type": "disruption",
        "magnitude": 75,
        "duration": "long",
        "affected_sectors": ["tech", "formation", "emploi", "investissement"],
    },
    "economic_crisis": {
        "name": "Crise economique locale",
        "description": "Ralentissement economique affectant le territoire",
        "event_type": "crisis",
        "magnitude": 80,
        "duration": "long",
        "affected_sectors": ["emploi", "investissement", "immobilier", "consommation"],
    },
    "public_investment": {
        "name": "Investissement public majeur",
        "description": "Annonce d'un programme d'investissement public important",
        "event_type": "investment",
        "magnitude": 65,
        "duration": "long",
        "affected_sectors": ["infrastructure", "emploi", "attractivite"],
    },
}


SIMULATION_PROMPT = """Tu es un expert en economie territoriale. Simule l'impact de cet evenement sur le territoire.

**Territoire**: {territory}
**Secteur principal**: {sector}

**Evenement**:
- Type: {event_type}
- Description: {event_description}
- Magnitude: {magnitude}/100
- Duree: {duration}

**Contexte du marche**:
- Entreprises sur le territoire: {enterprises_count}
- Secteurs principaux: {main_sectors}

**Analyse et reponds en JSON**:
{{
    "short_term_impacts": [
        {{"actor_type": "<type>", "impact": "<description>", "severity": <1-10>}},
        ...
    ],
    "medium_term_impacts": [
        {{"actor_type": "<type>", "impact": "<description>", "severity": <1-10>}},
        ...
    ],
    "predictions": {{
        "emploi": "<impact prevu sur l'emploi>",
        "investissement": "<impact prevu sur les investissements>",
        "attractivite": "<impact prevu sur l'attractivite territoriale>",
        "concurrence": "<impact prevu sur la concurrence>"
    }},
    "winners": ["<acteurs qui beneficient>"],
    "losers": ["<acteurs qui perdent>"],
    "recommendations": [
        "<recommandation strategique 1>",
        "<recommandation strategique 2>",
        "<recommandation strategique 3>"
    ],
    "confidence": <0-100>
}}
"""


def register_simulation_tools(mcp: FastMCP) -> None:
    """Register simulation tools on the MCP server."""

    @mcp.tool()
    async def tawiza_simulate(
        scenario: str,
        territory: str,
        sector: str = "tech",
        custom_event: str | None = None,
        use_agent: bool = True,
        ctx: Context = None,
    ) -> str:
        """Simule l'impact d'un scenario economique sur un territoire.

        Utilise un agent CAMEL AI specialise (SimulationAgent) pour predire
        les reactions des acteurs territoriaux et les impacts a court/moyen terme.

        Args:
            scenario: Type de scenario predefini:
                - new_startup: Nouvelle startup innovante
                - company_closure: Fermeture d'entreprise majeure
                - new_regulation: Nouvelle reglementation
                - funding_round: Levee de fonds importante
                - market_expansion: Expansion de marche
                - tech_disruption: Disruption technologique
                - economic_crisis: Crise economique locale
                - public_investment: Investissement public majeur
                - custom: Evenement personnalise (utiliser custom_event)
            territory: Territoire concerne (ex: "Lille", "Lyon")
            sector: Secteur principal concerne (ex: "tech", "industrie", "sante")
            custom_event: Description de l'evenement personnalise (si scenario=custom)
            use_agent: Utiliser le SimulationAgent CAMEL (defaut: True)

        Returns:
            JSON avec impacts, predictions et recommandations
        """
        from src.infrastructure.agents.camel.tools.territorial_tools import sirene_search
        from src.infrastructure.agents.camel.workforce.agents import create_simulation_agent

        def notify(msg: str, progress: int = None):
            if ctx:
                try:
                    ctx.info(msg)
                    if progress is not None:
                        ctx.report_progress(progress, 100, msg)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        notify(f"Simulation: {scenario} sur {territory}", 0)

        # Get scenario details
        if scenario == "custom":
            if not custom_event:
                return json.dumps(
                    {
                        "success": False,
                        "error": "custom_event requis pour scenario 'custom'",
                    },
                    ensure_ascii=False,
                )
            event = SimulationEvent(
                type="custom",
                description=custom_event,
                affected_sectors=[sector],
                magnitude=50,
                duration="medium",
            )
            scenario_name = "Scenario personnalise"
        elif scenario in SCENARIOS:
            sc = SCENARIOS[scenario]
            event = SimulationEvent(
                type=sc["event_type"],
                description=sc["description"],
                affected_sectors=sc["affected_sectors"],
                magnitude=sc["magnitude"],
                duration=sc["duration"],
            )
            scenario_name = sc["name"]
        else:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Scenario inconnu: {scenario}. Disponibles: {list(SCENARIOS.keys())}",
                },
                ensure_ascii=False,
            )

        notify(f"[Simulation] Scenario: {scenario_name}", 10)

        # =====================================================================
        # MODE AGENT CAMEL (use_agent=True)
        # =====================================================================
        if use_agent:
            notify("[SimulationAgent] Initialisation agent IA...", 15)
            try:
                simulation_agent = create_simulation_agent()
                notify("[SimulationAgent] Agent cree", 20)

                # Build simulation prompt
                agent_prompt = f"""Simule l'impact economique du scenario suivant:

**Scenario**: {scenario_name}
**Type**: {event.type}
**Description**: {event.description}
**Magnitude**: {event.magnitude}/100
**Duree**: {event.duration}
**Territoire**: {territory}
**Secteur principal**: {sector}
**Secteurs affectés**: {", ".join(event.affected_sectors)}

Utilise l'outil sirene_search pour analyser le contexte territorial (entreprises présentes).
Puis génère une analyse complète avec:
- Impacts court terme et moyen terme
- Winners et losers
- Prédictions par dimension (emploi, investissement, attractivité, concurrence)
- Recommandations stratégiques
- Score de confiance"""

                notify("[SimulationAgent] Execution simulation...", 30)
                agent_response = simulation_agent.step(agent_prompt)

                agent_result = str(agent_response.msg.content)
                notify("[SimulationAgent] Simulation terminee", 90)

                return json.dumps(
                    {
                        "success": True,
                        "mode": "agent",
                        "scenario": scenario_name,
                        "territory": territory,
                        "event": event.to_dict(),
                        "agent_analysis": agent_result,
                        "report_md": f"# Simulation: {scenario_name}\\n\\n{agent_result}",
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )

            except Exception as e:
                logger.error(f"SimulationAgent failed: {e}, falling back to direct LLM")
                notify(f"[SimulationAgent] Erreur, mode direct: {str(e)[:30]}", 20)

        # =====================================================================
        # MODE DIRECT LLM (fallback)
        # =====================================================================
        # Get territory context
        notify("[Simulation] Analyse du contexte territorial...", 20)

        try:
            result = sirene_search(query=f"{sector} {territory}", limite=50)
            enterprises = result.get("enterprises", []) if result.get("success") else []
        except Exception as e:
            logger.debug(f"Sirene search failed for {sector} {territory}: {e}")
            enterprises = []

        enterprises_count = len(enterprises)

        # Analyze sectors present
        sectors = {}
        for ent in enterprises:
            naf = ent.get("naf", ent.get("activite", ""))[:2]
            if naf:
                sectors[naf] = sectors.get(naf, 0) + 1
        main_sectors = sorted(sectors.keys(), key=lambda x: sectors[x], reverse=True)[:5]

        notify(
            f"[Simulation] Contexte: {enterprises_count} entreprises, secteurs: {main_sectors}", 40
        )

        # Run LLM simulation
        notify("[Simulation] Generation des predictions LLM...", 50)

        try:
            from src.infrastructure.llm import OllamaClient

            client = OllamaClient(model="qwen3.5:27b")

            prompt = SIMULATION_PROMPT.format(
                territory=territory,
                sector=sector,
                event_type=event.type,
                event_description=event.description,
                magnitude=event.magnitude,
                duration=event.duration,
                enterprises_count=enterprises_count,
                main_sectors=", ".join(main_sectors) if main_sectors else "divers",
            )

            response = await client.generate(prompt=prompt, max_tokens=800)

            # Parse JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            sim_data = json.loads(json_str.strip())

            impacts = sim_data.get("short_term_impacts", []) + sim_data.get(
                "medium_term_impacts", []
            )
            predictions = sim_data.get("predictions", {})
            recommendations = sim_data.get("recommendations", [])
            confidence = sim_data.get("confidence", 70)

            notify(f"[Simulation] Predictions generees (confiance: {confidence}%)", 80)

        except Exception as e:
            logger.error(f"LLM simulation failed: {e}")
            # Fallback to rule-based simulation
            impacts = [
                {
                    "actor_type": "entreprises",
                    "impact": f"Impact {event.type} sur le secteur {sector}",
                    "severity": int(event.magnitude / 10),
                },
                {
                    "actor_type": "emploi",
                    "impact": "Variations possibles de l'emploi local",
                    "severity": int(event.magnitude / 15),
                },
            ]
            predictions = {
                "emploi": "Impact modere a evaluer",
                "investissement": "Fluctuations possibles",
                "attractivite": "A surveiller",
                "concurrence": "Reajustements previsibles",
            }
            recommendations = [
                "Surveiller l'evolution du marche",
                "Preparer des actions correctives",
                "Communiquer avec les acteurs locaux",
            ]
            confidence = 50
            notify("[Simulation] Fallback rule-based (LLM indisponible)", 80)

        # Build result
        result = SimulationResult(
            scenario=scenario_name,
            territory=territory,
            event=event,
            impacts=impacts,
            predictions=predictions,
            recommendations=recommendations,
            confidence=confidence,
        )

        # Generate markdown report
        report_md = f"""# Simulation: {scenario_name}

## Contexte
- **Territoire**: {territory}
- **Secteur**: {sector}
- **Entreprises concernees**: ~{enterprises_count}

## Evenement Simule
- **Type**: {event.type}
- **Description**: {event.description}
- **Magnitude**: {event.magnitude}/100
- **Duree**: {event.duration}

## Impacts Prevus

| Acteur | Impact | Severite |
|--------|--------|----------|
"""
        for impact in impacts[:6]:
            report_md += f"| {impact.get('actor_type', 'N/A')} | {impact.get('impact', 'N/A')} | {impact.get('severity', '?')}/10 |\n"

        report_md += f"""
## Predictions

| Dimension | Prediction |
|-----------|------------|
| Emploi | {predictions.get("emploi", "N/A")} |
| Investissement | {predictions.get("investissement", "N/A")} |
| Attractivite | {predictions.get("attractivite", "N/A")} |
| Concurrence | {predictions.get("concurrence", "N/A")} |

## Recommandations

"""
        for i, rec in enumerate(recommendations[:5], 1):
            report_md += f"{i}. {rec}\n"

        report_md += f"""
---
*Simulation generee par Tawiza (confiance: {confidence}%)*
*Base sur {enterprises_count} entreprises du secteur {sector} a {territory}*
"""

        notify(f"Simulation terminee (confiance: {confidence}%)", 100)

        return json.dumps(
            {
                "success": True,
                **result.to_dict(),
                "report_md": report_md,
                "context": {
                    "enterprises_count": enterprises_count,
                    "main_sectors": main_sectors,
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    @mcp.tool()
    async def tawiza_scenarios_list(ctx: Context = None) -> str:
        """Liste les scenarios de simulation disponibles.

        Returns:
            Liste des scenarios predefinis avec descriptions
        """
        scenarios_list = []
        for key, sc in SCENARIOS.items():
            scenarios_list.append(
                {
                    "id": key,
                    "name": sc["name"],
                    "description": sc["description"],
                    "magnitude": sc["magnitude"],
                    "duration": sc["duration"],
                    "affected_sectors": sc["affected_sectors"],
                }
            )

        return json.dumps(
            {
                "success": True,
                "scenarios": scenarios_list,
                "custom_available": True,
                "usage": "tawiza_simulate(scenario='<id>', territory='<ville>', sector='<secteur>')",
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def tawiza_impact_analysis(
        territory: str,
        sector: str,
        event_description: str,
        ctx: Context = None,
    ) -> str:
        """Analyse rapide de l'impact d'un evenement sur un territoire.

        Version simplifiee de la simulation pour une analyse rapide.

        Args:
            territory: Territoire concerne
            sector: Secteur principal
            event_description: Description de l'evenement

        Returns:
            Analyse d'impact rapide
        """
        if ctx:
            ctx.info(f"[Impact] Analyse: {event_description[:30]}...")

        try:
            from src.infrastructure.llm import OllamaClient

            client = OllamaClient(model="qwen3.5:27b")

            prompt = f"""Analyse rapidement l'impact de cet evenement economique.

Territoire: {territory}
Secteur: {sector}
Evenement: {event_description}

Reponds en JSON:
{{
    "impact_global": "<positif|negatif|neutre>",
    "score_impact": <-100 a +100>,
    "acteurs_impactes": ["<acteur1>", "<acteur2>"],
    "risques": ["<risque1>", "<risque2>"],
    "opportunites": ["<opportunite1>", "<opportunite2>"],
    "action_prioritaire": "<action recommandee>"
}}"""

            response = await client.generate(prompt=prompt, max_tokens=400)

            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            analysis = json.loads(json_str.strip())

            return json.dumps(
                {
                    "success": True,
                    "territory": territory,
                    "sector": sector,
                    "event": event_description,
                    "analysis": analysis,
                },
                ensure_ascii=False,
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": str(e),
                },
                ensure_ascii=False,
            )
