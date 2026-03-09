"""Delegation functions for TAJINEAgent.

Extracted from tajine_agent.py to reduce file size.
Each function takes the agent instance as first parameter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.tajine_agent import TAJINEAgent


async def create_manus_agent(agent: TAJINEAgent):
    """Create ManusAgent with shared tool registry.

    Shares the unified ToolRegistry between TAJINEAgent and ManusAgent
    to ensure consistent tool access and avoid duplicate registrations.

    Returns:
        ManusAgent instance or None if creation fails
    """
    # Don't retry if we already attempted and failed
    if agent._manus_creation_attempted and agent._manus_agent is None:
        return None

    agent._manus_creation_attempted = True

    try:
        from src.infrastructure.agents.manus import ManusAgent
        from src.infrastructure.llm.ollama_client import OllamaClient

        # Create LLM client
        llm_client = OllamaClient(
            base_url="http://localhost:11434",
            model=agent.powerful_model,
        )

        # Create ManusAgent with SHARED tool registry
        manus = ManusAgent(
            llm_client=llm_client,
            tool_registry=agent.tool_registry,  # Share the registry!
            max_iterations=5,
            model=agent.powerful_model,
        )

        # Health check LLM
        healthy = await llm_client.health_check()
        if not healthy:
            logger.warning(f"Ollama health check failed for {agent.powerful_model}")

        logger.info(
            f"ManusAgent created with shared registry "
            f"({len(agent.tool_registry)} tools, model={agent.powerful_model})"
        )
        return manus

    except ImportError as e:
        logger.warning(f"ManusAgent import failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"ManusAgent creation failed: {e}")
        return None


async def fallback_delegate(agent: TAJINEAgent, subtask: dict[str, Any]) -> dict[str, Any]:
    """Fallback when ManusAgent is unavailable.

    Executes tools directly via the shared ToolRegistry.
    Uses TAJINE browser tools for browser_action to enable Agent Live streaming.
    Falls back to simulation only if tool is not found.

    Args:
        agent: TAJINEAgent instance
        subtask: Subtask to process

    Returns:
        Tool execution result or simulated result dict
    """
    tool_name = subtask.get("tool", "unknown")
    params = subtask.get("params", {})

    logger.info(f"Direct tool execution via registry: {tool_name}")

    # Special handling for browser_action - use TAJINE tool with WebSocket streaming
    if tool_name == "browser_action":
        return await execute_browser_action(agent, subtask)

    # Try to execute via shared tool registry
    try:
        tool = agent.tool_registry.get_tool(tool_name)
        if tool:
            logger.info(f"Executing {tool_name} directly via ToolRegistry")

            # Execute the tool
            result = await tool.execute(**params)

            # Handle ToolResult dataclass
            if hasattr(result, "success"):
                return {
                    "status": "completed" if result.success else "failed",
                    "tool": tool_name,
                    "result": result.output if hasattr(result, "output") else result,
                    "success": result.success,
                    "metadata": {
                        "agent": "tool_registry",
                        "execution_time_ms": getattr(result, "execution_time_ms", None),
                    },
                }
            else:
                return {
                    "status": "completed",
                    "tool": tool_name,
                    "result": result,
                    "success": True,
                    "metadata": {"agent": "tool_registry"},
                }
        else:
            logger.warning(f"Tool '{tool_name}' not found in registry")

    except Exception as e:
        logger.warning(f"Tool registry execution failed for {tool_name}: {e}")
        return {
            "status": "failed",
            "tool": tool_name,
            "error": str(e),
            "success": False,
            "metadata": {"agent": "tool_registry"},
        }

    # Return simulation if tool not found
    logger.warning(f"Simulating execution for unknown tool: {tool_name}")
    return {
        "status": "completed",
        "tool": tool_name,
        "result": {
            "message": f"Simulated execution of {tool_name}",
            "params_received": params,
            "fallback": True,
            "available_tools": agent.tool_registry.list_tools()
            if hasattr(agent.tool_registry, "list_tools")
            else [],
        },
        "success": True,
        "metadata": {"agent": "simulation"},
    }


async def execute_browser_action(agent: TAJINEAgent, subtask: dict[str, Any]) -> dict[str, Any]:
    """Execute browser action with Agent Live WebSocket streaming.

    Uses TAJINE's BrowserActionTool which integrates with WebSocket
    for real-time screenshot streaming to the Agent Live panel.

    Args:
        agent: TAJINEAgent instance
        subtask: Subtask with browser action params

    Returns:
        Browser action result
    """
    from src.infrastructure.agents.tajine.callbacks import TAJINECallback, TAJINEEvent
    from src.infrastructure.agents.tajine.tools.browser_tools import BrowserActionTool

    params = subtask.get("params", {})
    # Check for query under different param names (raw_query or query)
    raw_query = params.get("raw_query") or params.get("query", "")

    logger.info(
        f"Executing browser_action with Agent Live streaming (task_id={agent._current_task_id})"
    )

    try:
        # Create tool with WebSocket integration
        browser_tool = BrowserActionTool()
        browser_tool.session_id = agent.session_id

        # Set task_id for WebSocket screenshot streaming
        if agent._current_task_id:
            browser_tool.set_task_id(agent._current_task_id)

        # Emit event for Agent Live UI
        agent.emit(
            TAJINECallback(
                event=TAJINEEvent.DELEGATE_TOOL,
                task_id=agent._current_task_id,
                phase="delegate",
                message="Starting browser for web research",
                data={"tool": "browser_action", "action": "navigate"},
            )
        )

        # Determine action based on params
        # Normalize action names (planning may use different names)
        action = params.get("action", "navigate")
        action_normalization = {
            "open_page": "navigate",
            "search": "navigate",
            "goto": "navigate",
            "open": "navigate",
        }
        action = action_normalization.get(action.lower(), action.lower())
        url = params.get("url")

        # If no URL provided, build search URL from raw_query
        if not url and raw_query:
            # Use DuckDuckGo HTML version (more reliable for automation)
            import urllib.parse

            search_query = urllib.parse.quote(raw_query)
            # Use lite.duckduckgo.com for HTML-only version
            url = f"https://lite.duckduckgo.com/lite/?q={search_query}"
            action = "navigate"

        # Execute browser action
        result = await browser_tool.execute(
            action=action,
            url=url,
            selector=params.get("selector"),
            text=params.get("text"),
            wait_for=params.get("wait_for"),
            timeout=params.get("timeout", 30000),
        )

        # Extract text content if navigation successful
        if result.get("success") and action == "navigate":
            extract_result = await browser_tool.execute(
                action="extract",
                selector="body",
            )
            if extract_result.get("success"):
                result["extracted_content"] = extract_result.get("data", {}).get(
                    "extracted_data"
                )

        return {
            "status": "completed" if result.get("success") else "failed",
            "tool": "browser_action",
            "result": result,
            "success": result.get("success", False),
            "metadata": {
                "agent": "tajine_browser",
                "url": url,
                "action": action,
                "has_screenshot": result.get("data", {}).get("has_screenshot", False),
            },
        }

    except Exception as e:
        logger.error(f"Browser action failed: {e}")
        return {
            "status": "failed",
            "tool": "browser_action",
            "error": str(e),
            "success": False,
            "metadata": {"agent": "tajine_browser"},
        }


async def run_data_hunt(
    agent: TAJINEAgent,
    perception: dict[str, Any],
    mode: str = "normal",
    task_id: str | None = None,
) -> dict[str, Any]:
    """Run DataHunter to collect real data from APIs and sources.

    Integrates with the PPDSL delegate phase to gather data from:
    - Structured APIs (SIRENE, BODACC, BOAMP, INSEE, etc.)
    - Semantic search (pgvector/Qdrant)
    - Graph expansion (Knowledge Graph)
    - Hypothesis-driven search
    - Bandit UCB1 optimization

    Args:
        agent: TAJINEAgent instance
        perception: Result from perceive() with territory, sector, intent
        mode: Hunt mode - "normal", "question", "hybrid", "semantic", "rare"
        task_id: Task ID for WebSocket events

    Returns:
        Dict with hunt results and metrics
    """
    from src.infrastructure.agents.tajine.callbacks import TAJINECallback, TAJINEEvent
    from src.infrastructure.agents.tajine.core.types import HuntContext

    territory = perception.get("territory", "France")
    query = perception.get("query", "")
    intent = perception.get("intent", "")

    # Determine hunt mode based on analysis mode
    # Use "hybrid" for complete mode (includes semantic search)
    hunt_mode = mode if mode in agent.data_hunter.MODE_WEIGHTS else "normal"

    logger.info(f"Starting DataHunter (mode={hunt_mode}, territory={territory})")

    # Emit hunt start event
    if task_id:
        agent.emit(
            TAJINECallback(
                event=TAJINEEvent.DELEGATE_TOOL,
                task_id=task_id,
                phase="delegate",
                message=f"DataHunter: Collecting real data for {territory}",
                data={"tool": "data_hunter", "mode": hunt_mode, "territory": territory},
            )
        )

    try:
        # Build HuntContext from perception
        hunt_context = HuntContext(
            query=query or intent,  # Use query or fallback to intent
            territory=territory,
            mode=hunt_mode,
            kg_state=perception.get("kg_state"),
            max_sources=5 if hunt_mode == "hybrid" else 3,
            timeout_seconds=60 if hunt_mode in ("hybrid", "rare") else 30,
        )

        # Execute hunt
        hunt_result = await agent.data_hunter.hunt(hunt_context)

        # Extract data from hunt result
        collected_data = []
        sources_used = set()

        # NOTE: HuntResult/ResilientHuntResult has 'data' attribute, not 'raw_data'
        if hasattr(hunt_result, "data"):
            for raw in hunt_result.data:
                collected_data.append(
                    {
                        "source": raw.source,
                        "content": raw.content,
                        "url": raw.url,
                        "quality": raw.quality_hint,
                    }
                )
                sources_used.add(raw.source)

        # Build result dict
        result = {
            "success": True,
            "data": collected_data,
            "data_count": len(collected_data),
            "sources_used": list(sources_used),
            "metrics": {
                "cache_hits": getattr(hunt_result, "cache_hits", 0),
                "fallbacks_used": getattr(hunt_result, "fallbacks_used", 0),
                "retry_count": getattr(hunt_result, "retry_count", 0),
            },
            "territory": territory,
            "mode": hunt_mode,
        }

        # Emit success event
        if task_id:
            agent.emit(
                TAJINECallback(
                    event=TAJINEEvent.DELEGATE_TOOL,
                    task_id=task_id,
                    phase="delegate",
                    message=f"DataHunter: Collected {len(collected_data)} data points from {len(sources_used)} sources",
                    data={
                        "tool": "data_hunter",
                        "count": len(collected_data),
                        "sources": list(sources_used),
                    },
                )
            )

        # Enrich with signals DB data (bridge to collector pipeline)
        try:
            from src.infrastructure.agents.tajine.tools.signals_bridge import (
                DepartmentProfileTool,
                MicroSignalsTool,
            )

            # Get micro-signals
            ms_tool = MicroSignalsTool()
            ms_result = await ms_tool.execute(
                {"department": territory if len(str(territory)) <= 3 else None}
            )
            if ms_result.get("status") == "success" and ms_result.get("micro_signals"):
                collected_data.append(
                    {
                        "source": "tawiza_microsignals",
                        "content": ms_result,
                        "url": "internal://signals_db/micro_signals",
                        "quality": 0.95,
                    }
                )
                sources_used.add("tawiza_microsignals")

            # Get department profile if territory is a department code
            if territory and len(str(territory)) <= 3:
                profile_tool = DepartmentProfileTool()
                profile_result = await profile_tool.execute({"department": str(territory)})
                if profile_result.get("status") == "success":
                    collected_data.append(
                        {
                            "source": "tawiza_profile",
                            "content": profile_result,
                            "url": f"internal://signals_db/department/{territory}",
                            "quality": 0.95,
                        }
                    )
                    sources_used.add("tawiza_profile")

            result["data"] = collected_data
            result["data_count"] = len(collected_data)
            result["sources_used"] = list(sources_used)
        except Exception as e:
            logger.warning(f"Signals bridge enrichment failed: {e}")

        # Bridge: trigger relation graph discovery in background
        # when territory looks like a French department code
        dept_code = str(territory).strip() if territory else ""
        if dept_code and len(dept_code) <= 3 and dept_code not in ("France", ""):
            import asyncio

            asyncio.create_task(bridge_relations_discover(agent, dept_code, task_id))

        logger.info(
            f"DataHunter completed: {len(collected_data)} items from {list(sources_used)}"
        )
        return result

    except Exception as e:
        logger.error(f"DataHunter failed: {e}")
        # Emit failure event
        if task_id:
            agent.emit(
                TAJINECallback(
                    event=TAJINEEvent.DELEGATE_TOOL,
                    task_id=task_id,
                    phase="delegate",
                    message=f"DataHunter: Failed - {str(e)[:50]}",
                    data={"tool": "data_hunter", "error": str(e)},
                )
            )
        return {
            "success": False,
            "data": [],
            "data_count": 0,
            "sources_used": [],
            "error": str(e),
            "territory": territory,
            "mode": hunt_mode,
        }


async def bridge_relations_discover(
    agent: TAJINEAgent, department_code: str, task_id: str | None = None
) -> None:
    """Bridge DataHunter -> RelationService: trigger relation discovery in background.

    Runs lightweight extractors (sirene, bodacc, ofgl, dvf, france_travail,
    insee_local) to refresh the actor-relation graph for the territory being
    analyzed.  Runs as a fire-and-forget ``asyncio.Task`` so it never blocks
    the main PPDSL pipeline.
    """
    from src.infrastructure.agents.tajine.callbacks import TAJINECallback, TAJINEEvent

    try:
        from src.application.services.relation_service import RelationService

        service = RelationService()
        # Run a focused set of fast extractors (skip slow enrichers)
        fast_sources = [
            "sirene",
            "bodacc",
            "boamp",
            "rna",
            "ofgl",
            "dvf",
            "france_travail",
            "insee_local",
            "nature_juridique",
        ]
        result = await service.discover(department_code, fast_sources)
        l1 = result.get("l1_relations", 0)
        actors = result.get("actors_upserted", 0)
        logger.info(
            "Relations bridge: dept={} -> {} actors, {} L1 relations refreshed",
            department_code,
            actors,
            l1,
        )
        if task_id:
            agent.emit(
                TAJINECallback(
                    event=TAJINEEvent.DELEGATE_TOOL,
                    task_id=task_id,
                    phase="delegate",
                    message=f"Relations graph refreshed: {actors} actors, {l1} L1 relations",
                    data={"tool": "relations_bridge", "actors": actors, "l1": l1},
                )
            )
    except Exception as e:
        logger.warning(f"Relations bridge failed for dept {department_code}: {e}")
