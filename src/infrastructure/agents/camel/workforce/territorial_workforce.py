"""TerritorialWorkforce - Multi-agent system for territorial intelligence.

Coordinates DataAgent, GeoAgent, WebAgent, and AnalystAgent to perform
comprehensive territorial market analysis.
"""

from typing import Any

from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.societies.workforce import Workforce
from camel.societies.workforce.single_agent_worker import SingleAgentWorker
from camel.tasks import Task
from camel.types import ModelPlatformType
from loguru import logger

from .agents import (
    create_analyst_agent,
    create_data_agent,
    create_geo_agent,
    create_web_agent,
)


class TerritorialWorkforce:
    """Workforce for territorial market analysis.

    Orchestrates 4 specialized agents:
    - DataAgent: Collects enterprise data from Sirene
    - GeoAgent: Creates maps and handles geolocation
    - WebAgent: Enriches data from company websites
    - AnalystAgent: Synthesizes and generates reports
    """

    def __init__(
        self,
        model_id: str = "qwen3.5:27b",
        ollama_url: str = "http://localhost:11434/v1",
        enable_web_enrichment: bool = True,
    ):
        """Initialize the territorial workforce.

        Args:
            model_id: Ollama model to use for all agents
            ollama_url: Ollama API URL
            enable_web_enrichment: Whether to enable web scraping (slower but richer)
        """
        self.model_id = model_id
        self.ollama_url = ollama_url
        self.enable_web_enrichment = enable_web_enrichment

        # Create specialized agents
        self.data_agent = create_data_agent(model_id, ollama_url)
        self.geo_agent = create_geo_agent(model_id, ollama_url)
        self.analyst_agent = create_analyst_agent(model_id, ollama_url)

        if enable_web_enrichment:
            self.web_agent = create_web_agent(model_id, ollama_url)
        else:
            self.web_agent = None

        # Create workforce
        self._workforce = self._build_workforce()

        logger.info(
            f"TerritorialWorkforce initialized with {model_id}, "
            f"web_enrichment={'enabled' if enable_web_enrichment else 'disabled'}"
        )

    def _create_ollama_model(self):
        """Create an Ollama model instance."""
        return ModelFactory.create(
            model_platform=ModelPlatformType.OLLAMA,
            model_type=self.model_id,
            url=self.ollama_url,
            model_config_dict={"max_tokens": 4096},
        )

    def _create_coordinator(self) -> ChatAgent:
        """Create a coordinator agent using Ollama."""
        coordinator_system = """Tu es le coordinateur d'une équipe d'agents spécialisés
en intelligence territoriale française.

Ton rôle est de:
1. Comprendre la demande d'analyse
2. Déléguer les tâches aux agents spécialisés
3. Orchestrer le workflow de façon efficace
4. Synthétiser les résultats

Agents disponibles:
- DataAgent: Collecte de données Sirene (recherche entreprises, SIRET)
- GeoAgent: Cartographie et géolocalisation (cartes, coordonnées)
- WebAgent: Enrichissement web (scraping sites entreprises)
- AnalystAgent: Analyse et rapports (synthèse, recommandations)

Pour chaque tâche, identifie quel agent est le plus approprié.
Réponds toujours en français."""

        return ChatAgent(
            system_message=coordinator_system,
            model=self._create_ollama_model(),
        )

    def _create_task_agent(self) -> ChatAgent:
        """Create a task planning agent using Ollama."""
        task_system = """Tu es un expert en planification de tâches d'intelligence économique.

Ton rôle est de:
1. Décomposer les demandes complexes en sous-tâches
2. Identifier les dépendances entre tâches
3. Prioriser les actions
4. Valider que les résultats sont complets

Pour une analyse territoriale typique:
1. D'abord collecter les données (DataAgent)
2. Puis géolocaliser et cartographier (GeoAgent)
3. Enrichir avec données web si demandé (WebAgent)
4. Enfin analyser et synthétiser (AnalystAgent)

Réponds toujours en français avec des instructions claires."""

        return ChatAgent(
            system_message=task_system,
            model=self._create_ollama_model(),
        )

    def _build_workforce(self) -> Workforce:
        """Build the Camel Workforce with workers."""
        # Create coordinator and task agent using Ollama (not OpenAI default)
        coordinator = self._create_coordinator()
        task_agent = self._create_task_agent()

        # Create workers from agents
        workers = [
            SingleAgentWorker(
                description="Collecte les données d'entreprises via l'API Sirene. "
                "Peut rechercher par nom, activité, région, effectif.",
                worker=self.data_agent,
            ),
            SingleAgentWorker(
                description="Génère des cartes interactives et gère la géolocalisation. "
                "Peut créer des cartes Folium avec marqueurs.",
                worker=self.geo_agent,
            ),
            SingleAgentWorker(
                description="Analyse les données collectées et génère des rapports structurés. "
                "Peut créer des synthèses, identifier des tendances, formuler des recommandations.",
                worker=self.analyst_agent,
            ),
        ]

        if self.web_agent:
            workers.append(
                SingleAgentWorker(
                    description="Enrichit les données depuis les sites web des entreprises. "
                    "Peut extraire descriptions, services, contacts, actualités.",
                    worker=self.web_agent,
                )
            )

        # Create workforce with Ollama coordinator AND task_agent
        workforce = Workforce(
            description="Analyse de marché territorial - Intelligence économique française",
            coordinator_agent=coordinator,
            task_agent=task_agent,
            children=workers,
        )

        return workforce

    def get_status(self) -> dict[str, Any]:
        """Get current workforce status.

        Returns:
            Dict containing:
                - model_id: The LLM model being used
                - web_enrichment: Whether web enrichment is enabled
                - agents: List of available agents and their status
        """
        agents = [
            {"name": "DataAgent", "status": "ready", "role": "data_collection"},
            {"name": "GeoAgent", "status": "ready", "role": "geolocation"},
            {"name": "AnalystAgent", "status": "ready", "role": "analysis"},
        ]
        if self.web_agent:
            agents.append({"name": "WebAgent", "status": "ready", "role": "web_enrichment"})

        return {
            "model_id": self.model_id,
            "ollama_url": self.ollama_url,
            "web_enrichment": self.enable_web_enrichment,
            "agents": agents,
            "workforce_ready": self._workforce is not None,
        }

    async def analyze_market(
        self,
        query: str,
        output_dir: str = "./outputs/analyses",
    ) -> dict[str, Any]:
        """Perform a complete territorial market analysis.

        Args:
            query: Analysis request (e.g., "Analyse le marché du conseil IT à Lille")
            output_dir: Directory for output files

        Returns:
            Dictionary with:
            - success: Boolean
            - report_dir: Path to generated files
            - enterprises_count: Number of enterprises analyzed
            - map_file: Path to generated map (if any)
            - summary: Brief summary of findings
        """
        logger.info(f"Starting market analysis: {query}")

        # Process the task through the workforce
        task_content = f"""
        Effectue une analyse de marché territoriale complète pour:
        "{query}"

        Étapes à suivre:
        1. DataAgent: Recherche les entreprises correspondantes dans Sirene
        2. GeoAgent: Génère une carte des entreprises trouvées
        3. {"WebAgent: Enrichit les données depuis les sites web" if self.enable_web_enrichment else ""}
        4. AnalystAgent: Analyse les données et génère un rapport complet

        Le rapport doit être sauvegardé dans: {output_dir}
        Formats: Markdown (.md), données brutes (.csv), carte (.html)
        """

        # Create a proper Task object for Camel AI
        task = Task(content=task_content)
        result = await self._workforce.process_task(task)

        return {
            "success": True,
            "result": result,
            "output_dir": output_dir,
        }

    def process_sync(self, query: str, output_dir: str = "./outputs/analyses") -> dict[str, Any]:
        """Synchronous wrapper for analyze_market."""
        import asyncio

        return asyncio.run(self.analyze_market(query, output_dir))


def create_territorial_workforce(
    model_id: str = "qwen3.5:27b",
    ollama_url: str = "http://localhost:11434/v1",
    enable_web_enrichment: bool = False,
) -> TerritorialWorkforce:
    """Create a TerritorialWorkforce instance.

    Args:
        model_id: Ollama model to use
        ollama_url: Ollama API URL
        enable_web_enrichment: Enable web scraping (slower)

    Returns:
        Configured TerritorialWorkforce
    """
    return TerritorialWorkforce(
        model_id=model_id,
        ollama_url=ollama_url,
        enable_web_enrichment=enable_web_enrichment,
    )
