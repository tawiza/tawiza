"""High-level MCP tools for Tawiza.

These tools provide simple, powerful interfaces for common tasks:
- tawiza/analyze: Complete market analysis
- tawiza/search: Multi-source search
- tawiza/validate: Multi-agent debate validation
- tawiza/map: Generate interactive map
- tawiza/chat: Conversational assistant

All tools support real-time progress notifications via MCP Context.
"""

import json
from typing import Literal

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP


def register_high_level_tools(mcp: FastMCP) -> None:
    """Register high-level tools on the MCP server."""

    @mcp.tool()
    async def tawiza_analyze(
        query: str,
        limit: int = 20,
        with_map: bool = True,
        ctx: Context = None,
    ) -> str:
        """Analyse complète d'un marché territorial.

        Effectue une recherche multi-sources (8 sources), valide les données
        avec un débat multi-agents LLM, et génère un rapport détaillé.

        Envoie des notifications de progression en temps réel.

        Args:
            query: Requête de recherche (ex: "startup IA Lille")
            limit: Nombre maximum de résultats par source
            with_map: Générer une carte interactive

        Returns:
            Rapport d'analyse au format JSON avec:
            - rapport_md: Rapport en Markdown
            - entreprises: Liste des entreprises trouvées
            - confidence: Score de confiance (0-100)
            - sources_stats: Statistiques par source
            - map_html: Carte HTML (si with_map=True)
        """
        from src.application.orchestration.data_orchestrator import DataOrchestrator
        from src.domain.debate.debate_system import DebateSystem
        from src.infrastructure.llm import create_debate_system_with_llm

        total_steps = 4 if with_map else 3

        # Helper for progress reporting
        def report(step: int, message: str):
            if ctx:
                try:
                    ctx.report_progress(step, total_steps, message)
                except Exception as e:
                    logger.debug(f"Failed to report progress: {e}")

        # Step 1: Multi-source search
        report(0, "[1/4] Recherche multi-sources en cours...")
        if ctx:
            ctx.info(f"Querying 8 sources for: {query}")

        orchestrator = DataOrchestrator()
        orch_result = await orchestrator.search(query=query, limit_per_source=limit)

        # Report source results
        for sr in orch_result.source_results:
            if ctx:
                status = f"{len(sr.results)} results" if sr.results else sr.error or "0 results"
                ctx.info(f"[Source] {sr.source}: {status} ({sr.duration_ms:.0f}ms)")

        report(1, f"[1/4] ✓ {orch_result.total_results} résultats de {len(orch_result.source_results)} sources")

        # Step 2: Debate validation
        report(1, "[2/4] Validation multi-agents LLM...")
        if ctx:
            ctx.info("Starting multi-agent debate validation")

        try:
            debate = create_debate_system_with_llm(text_model="qwen3.5:27b")
            if ctx:
                ctx.info("[Debate] Using LLM-enhanced agents (qwen3.5:27b)")
        except Exception as e:
            debate = DebateSystem()
            if ctx:
                ctx.info(f"[Debate] Using rule-based agents (LLM unavailable: {e})")

        all_results = [item for sr in orch_result.source_results for item in sr.results]

        # Custom callback for agent progress
        agent_count = 0
        async def on_agent_message(agent_name: str, confidence: float):
            nonlocal agent_count
            agent_count += 1
            if ctx:
                ctx.info(f"[Agent] {agent_name}: confidence {confidence:.0f}%")

        debate_result = await debate.validate(
            query=query,
            data={
                "results": all_results,
                "sources": [sr.source for sr in orch_result.source_results],
            },
        )

        # Report agent results
        for msg in debate_result.messages:
            if ctx:
                ctx.info(f"[Agent] {msg.agent} ({msg.role}): {msg.confidence:.0f}%")

        report(2, f"[2/4] ✓ Validation: {debate_result.final_confidence:.0f}% confiance")

        # Step 3: Generate map if requested
        map_html = None
        if with_map:
            report(2, "[3/4] Génération de la carte...")
            if ctx:
                ctx.info("Generating interactive map")

            from src.cli.v2.agents.tools import register_all_tools
            from src.cli.v2.agents.unified.tools import ToolRegistry

            registry = ToolRegistry()
            register_all_tools(registry)

            locations = []
            for item in all_results:
                geo = item.get("geo")
                name = item.get("nom") or item.get("name") or item.get("title", "N/A")
                if geo and geo.get("lat"):
                    locations.append({
                        "nom": name,
                        "lat": geo["lat"],
                        "lon": geo["lon"],
                        "type": "entreprise",
                        "source": item.get("source", "unknown"),
                    })

            if locations:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
                    map_path = f.name

                map_result = await registry.execute('geo.map', {
                    'locations': locations,
                    'title': f"Analyse: {query[:30]}",
                    'output_path': map_path,
                })
                if map_result.get("success"):
                    with open(map_path) as f:
                        map_html = f.read()
                    if ctx:
                        ctx.info(f"[Map] Generated with {len(locations)} markers")

            report(3, f"[3/4] ✓ Carte: {len(locations)} points")

        # Step 4: Build report
        step_num = 3 if with_map else 2
        report(step_num, f"[{step_num+1}/{total_steps}] Génération du rapport...")

        rapport_md = f"""# Analyse: {query}

## Résumé
- **Confiance**: {debate_result.final_confidence}%
- **Verdict**: {debate_result.verdict}
- **Sources interrogées**: {len(orch_result.source_results)}
- **Résultats totaux**: {orch_result.total_results}

## Sources

| Source | Résultats | Durée |
|--------|-----------|-------|
"""
        for sr in orch_result.source_results:
            rapport_md += f"| {sr.source} | {len(sr.results)} | {sr.duration_ms:.0f}ms |\n"

        if debate_result.issues:
            rapport_md += "\n## Issues détectés\n"
            for issue in debate_result.issues:
                rapport_md += f"- {issue}\n"

        rapport_md += "\n## Entreprises principales\n"
        for i, item in enumerate(all_results[:10]):
            name = item.get("nom") or item.get("name") or item.get("title", "N/A")
            siret = item.get("siret", "")
            source = item.get("source", "")
            rapport_md += f"{i+1}. **{name}** ({siret}) - _{source}_\n"

        result = {
            "success": True,
            "rapport_md": rapport_md,
            "entreprises": all_results[:50],
            "confidence": debate_result.final_confidence,
            "verdict": debate_result.verdict,
            "sources_stats": {
                sr.source: {"count": len(sr.results), "duration_ms": sr.duration_ms}
                for sr in orch_result.source_results
            },
        }

        if map_html:
            result["map_html"] = map_html

        report(total_steps, "✓ Analyse terminée!")
        if ctx:
            ctx.info(f"Analysis complete: {debate_result.final_confidence:.0f}% confidence, {len(all_results)} results")

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def tawiza_search(
        query: str,
        sources: str | None = None,
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Recherche multi-sources dans les bases de données françaises.

        Interroge jusqu'à 8 sources en parallèle pour trouver des entreprises.
        Envoie des notifications en temps réel pour chaque source.

        Args:
            query: Requête de recherche (ex: "conseil IT Lyon")
            sources: Sources à interroger, séparées par des virgules
                    (sirene,bodacc,boamp,ban,gdelt,google_news,subventions)
                    Par défaut: toutes les sources
            limit: Nombre maximum de résultats par source

        Returns:
            Résultats JSON avec données de chaque source
        """
        from src.application.orchestration.data_orchestrator import DataOrchestrator

        if ctx:
            ctx.info(f"Starting multi-source search: {query}")
            ctx.report_progress(0, 100, "Initializing search...")

        orchestrator = DataOrchestrator()

        # Parse sources filter
        source_filter = None
        if sources:
            source_filter = [s.strip() for s in sources.split(",")]
            if ctx:
                ctx.info(f"Filtering sources: {source_filter}")

        if ctx:
            ctx.report_progress(10, 100, "Querying sources...")

        orch_result = await orchestrator.search(
            query=query,
            limit_per_source=limit,
            sources=source_filter,
        )

        # Report each source
        for i, sr in enumerate(orch_result.source_results):
            if ctx:
                status = f"{len(sr.results)} results" if sr.results else sr.error or "0"
                ctx.info(f"[Source] {sr.source}: {status} ({sr.duration_ms:.0f}ms)")
                progress = 10 + (80 * (i + 1) / len(orch_result.source_results))
                ctx.report_progress(progress, 100, f"Source {sr.source}: {status}")

        result = {
            "success": True,
            "query": query,
            "total_results": orch_result.total_results,
            "duration_ms": orch_result.total_duration_ms,
            "sources": {},
        }

        for sr in orch_result.source_results:
            result["sources"][sr.source] = {
                "results": sr.results,
                "count": len(sr.results),
                "duration_ms": sr.duration_ms,
                "error": sr.error,
            }

        if ctx:
            ctx.report_progress(100, 100, f"✓ Search complete: {orch_result.total_results} results")

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def tawiza_validate(
        query: str,
        data: str,
        mode: Literal["standard", "extended"] = "extended",
        ctx: Context = None,
    ) -> str:
        """Valide des données avec le système de débat multi-agents LLM.

        6 agents analysent et vérifient les données:
        Chercheur → SourceRanker → Critique → FactChecker → Vérificateur → Synthèse

        Envoie des notifications pour chaque agent.

        Args:
            query: Contexte de la validation (ex: "startup IA Lille")
            data: Données à valider au format JSON (résultats de recherche)
            mode: Mode de débat - "standard" (3 agents) ou "extended" (6 agents)

        Returns:
            Résultat de validation avec score de confiance et verdict
        """
        from src.domain.debate import DebateMode
        from src.domain.debate.debate_system import DebateSystem
        from src.infrastructure.llm import create_debate_system_with_llm

        if ctx:
            ctx.info(f"Starting debate validation: {query}")
            ctx.report_progress(0, 100, "Initializing debate system...")

        # Parse input data
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON data"})

        # Create debate system
        debate_mode = DebateMode.EXTENDED if mode == "extended" else DebateMode.STANDARD
        num_agents = 6 if mode == "extended" else 3

        try:
            debate = create_debate_system_with_llm(
                text_model="qwen3.5:27b",
                mode=debate_mode,
            )
            if ctx:
                ctx.info(f"Using LLM-enhanced debate ({num_agents} agents)")
        except Exception as e:
            debate = DebateSystem(mode=debate_mode)
            if ctx:
                ctx.info(f"Using rule-based debate: {e}")

        if ctx:
            ctx.report_progress(10, 100, f"Running {num_agents}-agent debate...")

        debate_result = await debate.validate(query=query, data=parsed_data)

        # Report each agent
        for i, msg in enumerate(debate_result.messages):
            if ctx:
                ctx.info(f"[Agent] {msg.agent}: {msg.confidence:.0f}% confidence")
                progress = 10 + (80 * (i + 1) / len(debate_result.messages))
                ctx.report_progress(progress, 100, f"Agent {msg.agent}: {msg.confidence:.0f}%")

        result = {
            "success": True,
            "confidence": debate_result.final_confidence,
            "verdict": debate_result.verdict,
            "issues": debate_result.issues,
            "agents": [
                {
                    "agent": msg.agent,
                    "role": msg.role,
                    "confidence": msg.confidence,
                    "content": msg.content[:500] + "..." if len(msg.content) > 500 else msg.content,
                }
                for msg in debate_result.messages
            ],
        }

        if ctx:
            ctx.report_progress(100, 100, f"✓ Validation complete: {debate_result.final_confidence:.0f}%")

        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def tawiza_map(
        locations: str,
        title: str = "Carte Tawiza",
        ctx: Context = None,
    ) -> str:
        """Génère une carte interactive avec les localisations fournies.

        Args:
            locations: Liste de localisations au format JSON
                      Chaque location doit avoir: nom, lat, lon
                      Optionnel: type, effectif, commune, url
            title: Titre de la carte

        Returns:
            URL vers la carte HTML interactive (Folium)
        """
        from datetime import datetime
        from pathlib import Path

        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        if ctx:
            ctx.info(f"Generating map: {title}")
            ctx.report_progress(0, 100, "Parsing locations...")

        # Parse locations
        try:
            locs = json.loads(locations)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON locations"})

        if not isinstance(locs, list):
            return json.dumps({"success": False, "error": "locations must be a list"})

        if ctx:
            ctx.report_progress(20, 100, f"Processing {len(locs)} locations...")

        registry = ToolRegistry()
        register_all_tools(registry)

        # Save map to outputs directory with unique name
        outputs_dir = Path(__file__).parent.parent.parent.parent.parent / "outputs" / "maps"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = title.replace(" ", "_").replace("/", "-")[:30]
        map_filename = f"{timestamp}_{safe_title}.html"
        map_path = outputs_dir / map_filename

        if ctx:
            ctx.report_progress(50, 100, "Generating map...")

        map_result = await registry.execute('geo.map', {
            'locations': locs,
            'title': title,
            'output_path': str(map_path),
        })

        if map_result.get("success"):
            if ctx:
                ctx.report_progress(100, 100, f"✓ Map generated: {map_result.get('markers', len(locs))} markers")
                ctx.info(f"Map saved with {map_result.get('markers', len(locs))} markers")

            # Return URL for file server (port = MCP port + 1)
            map_url = f"http://localhost:8766/maps/{map_filename}"

            return json.dumps({
                "success": True,
                "map_url": map_url,
                "map_path": str(map_path),
                "markers_count": map_result.get("markers", len(locs)),
                "message": f"Carte interactive disponible: {map_url}"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": map_result.get("error", "Map generation failed"),
            })

    @mcp.tool()
    async def tawiza_chat(
        message: str,
        mode: Literal["assistant", "analyst", "data"] = "assistant",
        context: str | None = None,
        ctx: Context = None,
    ) -> str:
        """Assistant conversationnel Tawiza.

        Répond aux questions sur les entreprises françaises en utilisant
        automatiquement les outils de recherche et d'analyse.

        Args:
            message: Message de l'utilisateur
            mode: Mode de réponse
                - "assistant": Réponses naturelles avec données
                - "analyst": Analyse approfondie avec débat multi-agents
                - "data": Données brutes sans reformulation
            context: Contexte additionnel (JSON) - entreprises précédentes, filtres, etc.

        Returns:
            Réponse avec données structurées
        """
        from src.infrastructure.llm import OllamaClient

        if ctx:
            ctx.info(f"Chat message: {message[:50]}...")
            ctx.report_progress(0, 100, "Analyzing message...")

        # Detect intent from message
        keywords_search = ["cherche", "trouve", "liste", "quelles", "quels", "entreprises", "startups", "sociétés"]
        keywords_compare = ["compare", "différence", "versus", "vs", "entre"]
        keywords_analyze = ["analyse", "évalue", "examine", "détail"]

        message_lower = message.lower()

        # Determine action
        needs_search = any(kw in message_lower for kw in keywords_search)
        needs_compare = any(kw in message_lower for kw in keywords_compare)
        needs_analyze = any(kw in message_lower for kw in keywords_analyze) or mode == "analyst"

        result = {
            "success": True,
            "response": "",
            "data": None,
            "sources_used": [],
            "confidence": None,
        }

        # Execute search if needed
        if needs_search or needs_compare or needs_analyze:
            if ctx:
                ctx.report_progress(20, 100, "Searching data sources...")
                ctx.info("Detected search intent, querying sources...")

            from src.application.orchestration.data_orchestrator import DataOrchestrator

            orchestrator = DataOrchestrator()
            orch_result = await orchestrator.search(query=message, limit_per_source=10)

            all_results = [item for sr in orch_result.source_results for item in sr.results]
            result["sources_used"] = [sr.source for sr in orch_result.source_results if sr.results]
            result["data"] = {
                "entreprises": all_results[:20],
                "total": len(all_results),
            }

            if ctx:
                ctx.info(f"Found {len(all_results)} results from {len(result['sources_used'])} sources")

            # Run debate if analyst mode
            if needs_analyze or mode == "analyst":
                if ctx:
                    ctx.report_progress(50, 100, "Running multi-agent analysis...")
                    ctx.info("Starting debate validation...")

                from src.domain.debate.debate_system import DebateSystem
                from src.infrastructure.llm import create_debate_system_with_llm

                try:
                    debate = create_debate_system_with_llm(text_model="qwen3.5:27b")
                except Exception as e:
                    logger.debug(f"Failed to create LLM-enhanced debate system: {e}")
                    debate = DebateSystem()

                debate_result = await debate.validate(
                    query=message,
                    data={"results": all_results, "sources": result["sources_used"]},
                )
                result["confidence"] = debate_result.final_confidence
                result["data"]["verdict"] = debate_result.verdict
                result["data"]["issues"] = debate_result.issues

                if ctx:
                    ctx.info(f"Debate complete: {debate_result.final_confidence:.0f}% confidence")

        # Generate natural response if not data mode
        if mode != "data":
            if ctx:
                ctx.report_progress(80, 100, "Generating response...")

            try:
                client = OllamaClient(model="qwen3.5:27b")

                context_str = ""
                if result["data"]:
                    enterprises = result["data"].get("entreprises", [])[:5]
                    context_str = f"\n\nDonnées trouvées ({result['data'].get('total', 0)} résultats):\n"
                    for e in enterprises:
                        name = e.get("nom") or e.get("name", "N/A")
                        context_str += f"- {name}\n"

                prompt = f"""Tu es un assistant expert en données d'entreprises françaises.
Réponds à cette question de manière concise et utile.

Question: {message}
{context_str}

Réponds en français, de manière professionnelle et informative."""

                response = await client.generate(prompt=prompt)
                result["response"] = response

            except Exception as e:
                # Fallback to simple response
                if result["data"]:
                    count = result["data"].get("total", 0)
                    result["response"] = f"J'ai trouvé {count} résultats pour votre recherche."
                else:
                    result["response"] = f"Je n'ai pas pu traiter votre demande: {str(e)}"
        else:
            result["response"] = "Données brutes retournées."

        if ctx:
            ctx.report_progress(100, 100, "✓ Response ready")

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)
