"""
StrategicPlanner - Task decomposition and planning for TAJINEAgent.

Provides intelligent task decomposition with:
- Intent-to-tool mapping (rule-based baseline)
- LLM-powered decomposition via Ollama
- Tool registry integration for validation
- Complexity estimation for resource planning
"""

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.memory.episodic_store import EpisodicStore
    from src.infrastructure.llm.ollama_client import OllamaClient
    from src.infrastructure.tools.registry import ToolRegistry


# Decomposition prompt for LLM
DECOMPOSITION_PROMPT = """You are a strategic planner for territorial economic intelligence.

Given a user's analysis request, decompose it into executable subtasks.

IMPORTANT RULES:
1. For ANY request involving web search, online research, or looking up information:
   - ALWAYS start with "browser_action" as the FIRST subtask with priority 1
   - browser_action provides visual feedback via Agent Live panel
2. Use territorial_data for structured French business database queries (Sirene/INSEE)
3. Use analyze_data for data analysis after collection

Available tools:
{tools}

User request: {query}
Intent: {intent}
Territory: {territory}
Sector: {sector}

Return a JSON object with:
{{
  "subtasks": [
    {{"tool": "tool_name", "params": {{"key": "value"}}, "priority": 1}},
    ...
  ],
  "reasoning": "Brief explanation of task decomposition"
}}

CRITICAL: If the query contains "cherche", "recherche", "trouve", "search", or any web lookup intent,
the FIRST subtask MUST be browser_action.

Order by dependency (browser_action for web search first, then data collection, analysis last).
"""


@dataclass
class PlannedTask:
    """A planned subtask."""
    tool: str
    params: dict[str, Any]
    priority: int
    dependencies: list[str] = field(default_factory=list)
    timeout: int = 60


class StrategicPlanner:
    """
    Decomposes high-level intents into executable subtasks.

    Supports three modes:
    1. LLM-powered: Uses Ollama for intelligent decomposition
    2. Rule-based: Maps intents to predefined tool sequences
    3. Hybrid: LLM with rule-based fallback

    Attributes:
        tool_registry: ToolRegistry for tool discovery and validation
        llm_client: OllamaClient for LLM-powered decomposition
        model: LLM model name for decomposition
        intent_tools: Intent to tool mapping for rule-based mode
    """

    def __init__(
        self,
        tool_registry: Optional['ToolRegistry'] = None,
        llm_client: Optional['OllamaClient'] = None,
        model: str = "qwen3.5:27b",
        episodic_store: Optional['EpisodicStore'] = None,
    ):
        """
        Initialize StrategicPlanner.

        Args:
            tool_registry: Tool registry for validation and discovery
            llm_client: OllamaClient for LLM decomposition
            model: LLM model name (default: qwen3.5:27b for fast planning)
            episodic_store: EpisodicStore for retrieving similar past episodes
        """
        self.tool_registry = tool_registry
        self.llm_client = llm_client
        self.episodic_store = episodic_store
        self.model = model

        # Intent to tool mapping (rule-based baseline)
        # Maps to tools available in unified registry
        # data_hunt FIRST to collect real SIRENE/BODACC/INSEE data
        # browser_action is used for web research with visual feedback in Agent Live
        self.intent_tools = {
            # data_hunt first for real API data, then browser_action for Agent Live
            'analyze': ['data_hunt', 'territorial_data', 'analyze_data', 'browser_action', 'territorial_analyst'],
            'compare': ['data_hunt', 'territorial_data', 'analyze_data', 'browser_action'],
            'prospect': ['data_hunt', 'browser_action', 'territorial_data', 'deep_research'],
            'monitor': ['data_hunt', 'browser_action', 'crawl_web', 'territorial_analyst'],
            'research': ['data_hunt', 'browser_action', 'deep_research', 'crawl_web', 'analyze_data'],
            'search': ['data_hunt', 'browser_action', 'deep_research'],  # Web search intent
        }

        logger.info(f"StrategicPlanner initialized (model={model}, has_llm={llm_client is not None}, has_memory={episodic_store is not None})")

    def _get_episodic_context(
        self,
        query: str,
        territory: str | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        """
        Retrieve similar past episodes for context.

        Uses episodic memory to find successful past analyses that can inform
        the current plan. Returns patterns and tools that worked well.

        Args:
            query: Current user query
            territory: Target territory (department code)
            limit: Maximum episodes to retrieve

        Returns:
            Dict with similar_episodes, successful_patterns, recommended_tools
        """
        if not self.episodic_store:
            return {'similar_episodes': [], 'successful_patterns': [], 'recommended_tools': []}

        try:
            # Search for similar queries
            similar = self.episodic_store.search_text(query, limit=limit)

            # Filter by territory if specified
            if territory:
                similar = [ep for ep in similar if ep.territory == territory or not ep.territory]

            # Extract patterns from successful episodes
            successful_patterns = []
            recommended_tools = set()

            for episode in similar:
                # Only learn from successful episodes (positive feedback or high confidence)
                is_successful = (
                    (episode.feedback_score and episode.feedback_score > 0) or
                    episode.confidence_score >= 0.7
                )

                if is_successful and episode.tools_called:
                    # Record the tool sequence that worked
                    pattern = {
                        'query_type': episode.query_type,
                        'tools': episode.tools_called,
                        'confidence': episode.confidence_score,
                    }
                    successful_patterns.append(pattern)
                    recommended_tools.update(episode.tools_called)

            context = {
                'similar_episodes': len(similar),
                'successful_patterns': successful_patterns[:3],
                'recommended_tools': list(recommended_tools)[:5],
                'territory_match': any(ep.territory == territory for ep in similar),
            }

            if similar:
                logger.debug(
                    f"Found {len(similar)} similar episodes, "
                    f"{len(successful_patterns)} successful patterns"
                )

            return context

        except Exception as e:
            logger.warning(f"Failed to retrieve episodic context: {e}")
            return {'similar_episodes': [], 'successful_patterns': [], 'recommended_tools': []}

    async def create_plan(self, perception: dict[str, Any]) -> dict[str, Any]:
        """
        Create execution plan from perception.

        Uses episodic memory for context, then tries LLM decomposition,
        with rule-based fallback.

        Args:
            perception: Output from TAJINEAgent.perceive()

        Returns:
            Plan with subtasks, strategy, estimated_steps, parallel_groups, episodic_context
        """
        intent = perception.get('intent', 'analyze')
        territory = perception.get('territory')
        sector = perception.get('sector')
        raw_query = perception.get('raw_query', '')

        # 1. Retrieve episodic context for similar past queries
        episodic_context = self._get_episodic_context(raw_query, territory)

        # 2. Try LLM decomposition first (includes episodic hints)
        if self.llm_client is not None:
            try:
                llm_plan = await self._llm_decompose(perception, episodic_context)
                if llm_plan and llm_plan.get('subtasks'):
                    logger.info(f"Using LLM-generated plan with {len(llm_plan['subtasks'])} subtasks")
                    plan = self._normalize_plan(llm_plan, intent, raw_query)
                    plan['episodic_context'] = episodic_context
                    return plan
            except Exception as e:
                logger.warning(f"LLM decomposition failed, using rules: {e}")

        # 3. Fall back to rule-based planning (enhanced with episodic recommendations)
        plan = self._rule_based_plan(intent, territory, sector, raw_query, episodic_context)
        return plan

    async def _llm_decompose(
        self,
        perception: dict[str, Any],
        episodic_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Use LLM to decompose task into subtasks.

        Calls OllamaClient.chat() and parses JSON response.
        Enhanced with episodic memory hints from similar past analyses.

        Args:
            perception: Perception data
            episodic_context: Context from similar past episodes (tools, patterns)

        Returns:
            Plan dict or None if decomposition fails
        """
        if not self.llm_client:
            return None

        # Get available tools list
        tools_desc = self._format_tools_for_prompt()

        # Build episodic hints section
        episodic_hints = ""
        if episodic_context and episodic_context.get('successful_patterns'):
            patterns = episodic_context['successful_patterns']
            recommended = episodic_context.get('recommended_tools', [])
            episodic_hints = f"""

EPISODIC MEMORY HINTS (from {episodic_context.get('similar_episodes', 0)} similar past analyses):
- Recommended tools from past successes: {', '.join(recommended) if recommended else 'none'}
- Successful patterns: {len(patterns)} found
Consider prioritizing these tools as they worked well for similar queries."""

        prompt = DECOMPOSITION_PROMPT.format(
            tools=tools_desc,
            query=perception.get('raw_query', ''),
            intent=perception.get('intent', 'analyze'),
            territory=perception.get('territory', 'unknown'),
            sector=perception.get('sector', 'all')
        ) + episodic_hints

        # Call LLM via OllamaClient
        messages = [
            {"role": "system", "content": "You are a task decomposition assistant. Return only valid JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.llm_client.chat(
                messages=messages,
                model=self.model,
                temperature=0.3,  # Lower temperature for structured output
            )

            # Extract content from response
            content = response.get('content', '')
            if not content:
                logger.warning("Empty LLM response for decomposition")
                return None

            # Parse JSON from response
            plan = self._extract_json_from_response(content)
            if plan:
                logger.debug(f"LLM decomposition successful: {len(plan.get('subtasks', []))} subtasks")
            return plan

        except Exception as e:
            logger.error(f"LLM decomposition error: {e}")
            return None

    def _extract_json_from_response(self, content: str) -> dict[str, Any] | None:
        """
        Extract JSON object from LLM response.

        Handles various response formats:
        - Pure JSON
        - JSON wrapped in markdown code blocks
        - JSON mixed with text

        Args:
            content: Raw LLM response

        Returns:
            Parsed JSON dict or None
        """
        # Try direct JSON parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
            r'```\s*([\s\S]*?)\s*```',       # ``` ... ```
            r'\{[\s\S]*\}',                  # Raw JSON object
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                try:
                    # Clean up the match
                    clean_json = match.strip()
                    if not clean_json.startswith('{'):
                        continue
                    return json.loads(clean_json)
                except json.JSONDecodeError:
                    continue

        logger.warning(f"Could not extract JSON from LLM response: {content[:200]}...")
        return None

    def _rule_based_plan(
        self,
        intent: str,
        territory: str | None,
        sector: str | None,
        raw_query: str,
        episodic_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create plan using rule-based intent mapping.

        Enhanced with episodic memory to prioritize tools that worked
        well in similar past analyses.

        Args:
            intent: Detected intent
            territory: Target territory
            sector: Target sector
            raw_query: Original query
            episodic_context: Context from similar past episodes

        Returns:
            Plan dict with episodic_context included
        """
        # Get base tools for this intent
        tools = list(self.intent_tools.get(intent, ['data_collect']))

        # Enhance with episodic recommendations
        if episodic_context and episodic_context.get('recommended_tools'):
            recommended = episodic_context['recommended_tools']
            # Reorder tools: prioritize those that worked in similar queries
            prioritized = [t for t in recommended if t in tools]
            remaining = [t for t in tools if t not in prioritized]
            # Insert recommended tools at front (but keep data_hunt first if present)
            if 'data_hunt' in remaining:
                remaining.remove('data_hunt')
                tools = ['data_hunt'] + prioritized + remaining
            else:
                tools = prioritized + remaining
            logger.debug(f"Reordered tools based on episodic memory: {tools}")

        # Build subtasks
        subtasks = []
        for i, tool in enumerate(tools):
            subtasks.append({
                'tool': tool,
                'params': {
                    'territory': territory,
                    'sector': sector,
                    'raw_query': raw_query
                },
                'priority': i + 1,
                'timeout': 60,
                'dependencies': []
            })

        logger.info(f"Created rule-based plan with {len(subtasks)} subtasks for intent '{intent}'")

        return {
            'subtasks': subtasks,
            'strategy': f"{intent}_strategy",
            'estimated_steps': len(subtasks),
            'parallel_groups': self._identify_parallel_groups(subtasks),
            'episodic_context': episodic_context or {},
        }

    def _normalize_plan(self, plan: dict[str, Any], intent: str, raw_query: str = "") -> dict[str, Any]:
        """
        Normalize LLM-generated plan to standard format.

        Args:
            plan: Raw plan from LLM
            intent: Detected intent
            raw_query: Original user query for web search detection

        Returns:
            Normalized plan dict
        """
        subtasks = plan.get('subtasks', [])

        # Ensure each subtask has required fields
        normalized = []
        for i, task in enumerate(subtasks):
            normalized.append({
                'tool': task.get('tool', 'unknown'),
                'params': task.get('params', {}),
                'priority': task.get('priority', i + 1),
                'timeout': task.get('timeout', 60),
                'dependencies': task.get('dependencies', [])
            })

        # Post-processing: Inject browser_action if missing for web search queries
        normalized = self._ensure_browser_action(normalized, intent, raw_query)

        return {
            'subtasks': normalized,
            'strategy': f"{intent}_strategy",
            'estimated_steps': len(normalized),
            'parallel_groups': self._identify_parallel_groups(normalized),
            'reasoning': plan.get('reasoning', '')
        }

    def _ensure_browser_action(
        self,
        subtasks: list[dict],
        intent: str,
        raw_query: str
    ) -> list[dict]:
        """
        Ensure browser_action is included for web search queries.

        This is a safety net when LLM doesn't include browser_action despite instructions.

        Args:
            subtasks: List of normalized subtasks
            intent: Detected intent
            raw_query: Original query

        Returns:
            Updated subtasks with browser_action injected if needed
        """
        # Check if browser_action already present
        has_browser = any(t.get('tool') == 'browser_action' for t in subtasks)
        if has_browser:
            return subtasks

        # Keywords that indicate web search is needed
        web_keywords = [
            'cherche', 'recherche', 'trouve', 'search', 'look up',
            'france 2030', 'web', 'internet', 'site', 'en ligne',
            'actualit', 'news', 'information', 'données publiques'
        ]

        query_lower = raw_query.lower()
        needs_browser = any(kw in query_lower for kw in web_keywords)

        # Also inject for certain intents
        if intent in ('search', 'research', 'prospect', 'monitor'):
            needs_browser = True

        if needs_browser:
            # Inject browser_action as first task
            browser_task = {
                'tool': 'browser_action',
                'params': {
                    'query': raw_query,
                    'action': 'search'
                },
                'priority': 0,  # Highest priority
                'timeout': 120,
                'dependencies': []
            }
            logger.info(f"Injected browser_action for web search (query: {raw_query[:50]}...)")
            return [browser_task] + subtasks

        return subtasks

    def _identify_parallel_groups(self, subtasks: list[dict]) -> list[list[int]]:
        """
        Identify groups of subtasks that can run in parallel.

        Tasks with the same priority and no dependencies can run together.

        Args:
            subtasks: List of subtasks

        Returns:
            List of task index groups
        """
        if not subtasks:
            return []

        # Group by priority
        priority_groups: dict[int, list[int]] = {}
        for i, task in enumerate(subtasks):
            priority = task.get('priority', i + 1)
            if priority not in priority_groups:
                priority_groups[priority] = []
            priority_groups[priority].append(i)

        # Return groups in priority order
        return [priority_groups[p] for p in sorted(priority_groups.keys())]

    def _format_tools_for_prompt(self) -> str:
        """Format available tools for LLM prompt.

        Uses ToolRegistry to get tool names and descriptions.
        """
        if self.tool_registry:
            tool_names = self.tool_registry.list_tools()
            lines = []
            for name in tool_names:
                tool = self.tool_registry.get_tool(name)
                if tool:
                    desc = getattr(tool, 'description', 'No description')
                    lines.append(f"- {name}: {desc}")
            if lines:
                return "\n".join(lines)

        # Default tools if no registry
        return """
- browser_action: [PRIORITY FOR WEB SEARCH] Opens browser, searches web, takes screenshots for Agent Live panel. USE FIRST for any web search query.
- territorial_data: Collect enterprise data from French public databases (Sirene INSEE)
- analyze_data: Analyze datasets, generate statistics, create visualizations
- territorial_analyst: Analyze territorial data for market trends and opportunities
- territorial_geo: Geographic distribution analysis of enterprises
- deep_research: Conduct deep research using multiple sources
- crawl_web: Crawl websites and extract structured data
- generate_code: Generate code based on requirements
"""

    def get_available_tools(self) -> list[str]:
        """
        Get list of available tool names.

        Returns:
            List of tool names from registry or defaults
        """
        if self.tool_registry:
            tools = self.tool_registry.list_tools()
            # Handle both ToolRegistry (returns strings) and TerritorialTools (returns objects)
            if tools and isinstance(tools[0], str):
                return tools
            return [t.metadata.name for t in tools]

        # Default available tools matching unified registry
        return [
            'territorial_data', 'territorial_geo', 'territorial_analyst', 'territorial_web',
            'analyze_data', 'deep_research', 'crawl_web', 'browser_action', 'generate_code'
        ]

    def validate_plan(self, plan: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate a plan for executability.

        Checks:
        - Plan has subtasks
        - All tools exist in registry (if available)
        - Subtasks have required fields

        Args:
            plan: Plan to validate

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check for empty plan
        subtasks = plan.get('subtasks', [])
        if not subtasks:
            issues.append("Plan has empty subtask list")
            return False, issues

        # Get available tools
        available_tools = self.get_available_tools() if self.tool_registry else None

        for i, task in enumerate(subtasks):
            # Check required fields
            if 'tool' not in task:
                issues.append(f"Subtask {i} missing 'tool' field")

            if 'params' not in task:
                issues.append(f"Subtask {i} missing 'params' field")

            # Check tool exists
            tool_name = task.get('tool')
            if available_tools and tool_name not in available_tools:
                issues.append(f"Tool '{tool_name}' not found in registry")

        is_valid = len(issues) == 0
        return is_valid, issues

    def estimate_complexity(self, plan: dict[str, Any]) -> dict[str, Any]:
        """
        Estimate plan complexity for resource planning.

        Factors:
        - Number of subtasks
        - Tool timeouts
        - Parallelization potential

        Args:
            plan: Plan to analyze

        Returns:
            Dict with score and factors
        """
        subtasks = plan.get('subtasks', [])

        if not subtasks:
            return {'score': 0, 'factors': {'subtask_count': 0}}

        # Calculate factors
        subtask_count = len(subtasks)
        total_timeout = sum(t.get('timeout', 60) for t in subtasks)
        parallel_groups = plan.get('parallel_groups', [])
        parallelism = len(parallel_groups) if parallel_groups else subtask_count

        # Complexity score (weighted sum)
        score = (
            subtask_count * 10 +  # Each subtask adds 10
            total_timeout / 60 * 5 +  # Each minute of timeout adds 5
            max(0, subtask_count - parallelism) * 3  # Sequential deps add 3 each
        )

        return {
            'score': round(score, 2),
            'factors': {
                'subtask_count': subtask_count,
                'total_timeout_seconds': total_timeout,
                'parallel_groups': parallelism,
                'sequential_deps': max(0, subtask_count - parallelism)
            }
        }
