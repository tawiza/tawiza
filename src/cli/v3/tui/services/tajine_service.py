"""TAJINE Cognitive Engine service for TUI.

Provides async interface between TUI and CognitiveEngine with:
- Real-time processing updates
- Caching of results
- Event emission for UI updates
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from src.cli.v3.tui.services.error_telemetry import (
    get_error_telemetry,
)


class ProcessingState(Enum):
    """State of cognitive processing."""

    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ProcessingEvent:
    """Event emitted during cognitive processing."""

    level: str
    state: ProcessingState
    confidence: float = 0.0
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AnalysisRequest:
    """Request for TAJINE analysis."""

    query: str
    territory: str | None = None
    sector: str | None = None
    data: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete result from TAJINE analysis."""

    request: AnalysisRequest
    cognitive_output: dict[str, Any]
    summary: str
    recommendations: list[str]
    confidence: float
    processing_time: float
    timestamp: datetime = field(default_factory=datetime.now)


class TAJINEService:
    """Service for interacting with TAJINE CognitiveEngine.

    Provides:
    - Async processing with progress callbacks
    - Result caching
    - Event-driven updates for TUI
    """

    def __init__(self, use_agent: bool = True):
        """Initialize TAJINEService.

        Args:
            use_agent: If True, use TAJINEAgent with full PPDSL cycle.
                      If False, use CognitiveEngine directly.
        """
        self._state = ProcessingState.IDLE
        self._current_result: AnalysisResult | None = None
        self._cache: dict[str, AnalysisResult] = {}
        self._event_listeners: list[Callable[[ProcessingEvent], None]] = []
        self._engine = None
        self._agent = None
        self._use_agent = use_agent

    @property
    def state(self) -> ProcessingState:
        """Get current processing state."""
        return self._state

    @property
    def last_result(self) -> AnalysisResult | None:
        """Get the last analysis result."""
        return self._current_result

    def add_event_listener(self, listener: Callable[[ProcessingEvent], None]) -> None:
        """Add a listener for processing events."""
        self._event_listeners.append(listener)

    def remove_event_listener(self, listener: Callable[[ProcessingEvent], None]) -> None:
        """Remove an event listener."""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    def _emit_event(self, event: ProcessingEvent) -> None:
        """Emit an event to all listeners."""
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Event listener error: {e}")

    async def _get_engine(self):
        """Lazy-load the CognitiveEngine."""
        if self._engine is None:
            try:
                from src.infrastructure.agents.tajine.cognitive import CognitiveEngine

                self._engine = CognitiveEngine()
            except ImportError as e:
                logger.error(f"Failed to import CognitiveEngine: {e}")
                raise
        return self._engine

    async def _get_agent(self):
        """Lazy-load TAJINEAgent with full PPDSL cycle."""
        if self._agent is None:
            try:
                from src.infrastructure.agents.tajine import TAJINEAgent

                self._agent = TAJINEAgent(
                    name="tajine_tui",
                    local_model="qwen3.5:27b",
                    powerful_model="qwen3-coder:30b",
                )
                await self._agent.initialize()

                # Connect agent events to our listeners
                def on_agent_event(callback):
                    event = ProcessingEvent(
                        level=callback.phase or "unknown",
                        state=ProcessingState.PROCESSING,
                        confidence=0.0,
                        message=callback.message or "",
                        data=callback.data or {},
                    )
                    self._emit_event(event)

                self._agent.on(on_agent_event)
                logger.info("TAJINEAgent initialized for TUI")
            except Exception as e:
                logger.warning(f"TAJINEAgent unavailable: {e}, falling back to CognitiveEngine")
                self._use_agent = False
        return self._agent

    async def analyze(self, request: AnalysisRequest, use_cache: bool = True) -> AnalysisResult:
        """Run TAJINE analysis on the request.

        Args:
            request: Analysis request with query and optional filters
            use_cache: Whether to use cached results

        Returns:
            AnalysisResult with full cognitive output
        """
        # Check cache
        cache_key = f"{request.query}:{request.territory}:{request.sector}"
        if use_cache and cache_key in self._cache:
            logger.info(f"Using cached result for: {cache_key}")
            return self._cache[cache_key]

        self._state = ProcessingState.PROCESSING
        start_time = datetime.now()

        try:
            # Use TAJINEAgent if configured and available
            if self._use_agent:
                return await self._analyze_with_agent(request, cache_key, start_time)

            # Fallback to direct CognitiveEngine
            engine = await self._get_engine()

            # Build tool results from request
            tool_results = self._build_tool_results(request)

            # Emit start events for each level
            levels = ["discovery", "causal", "scenario", "strategy", "theoretical"]
            for level in levels:
                self._emit_event(
                    ProcessingEvent(
                        level=level,
                        state=ProcessingState.PROCESSING,
                        message=f"Processing {level}...",
                    )
                )

                # Process with engine
                # Note: In real implementation, we'd hook into engine's level processing
                await asyncio.sleep(0.1)  # Simulate processing time

            # Run the full pipeline
            cognitive_output = await engine.process(tool_results)

            # Emit completion events
            for level in levels:
                level_data = cognitive_output.get("cognitive_levels", {}).get(level, {})
                confidence = (
                    level_data.get("confidence", 0.5) if isinstance(level_data, dict) else 0.5
                )

                self._emit_event(
                    ProcessingEvent(
                        level=level,
                        state=ProcessingState.COMPLETED,
                        confidence=confidence,
                        data=level_data if isinstance(level_data, dict) else {},
                    )
                )

            # Build result
            processing_time = (datetime.now() - start_time).total_seconds()
            result = AnalysisResult(
                request=request,
                cognitive_output=cognitive_output,
                summary=self._generate_summary(cognitive_output),
                recommendations=self._extract_recommendations(cognitive_output),
                confidence=cognitive_output.get("confidence", 0.5),
                processing_time=processing_time,
            )

            # Cache result
            self._cache[cache_key] = result
            self._current_result = result
            self._state = ProcessingState.COMPLETED

            return result

        except asyncio.CancelledError:
            # Handle async cancellation explicitly to prevent stuck state
            logger.warning("Analysis cancelled by user or timeout")
            self._state = ProcessingState.IDLE
            self._emit_event(
                ProcessingEvent(
                    level="cancelled", state=ProcessingState.IDLE, message="Analysis cancelled"
                )
            )
            raise

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            self._state = ProcessingState.ERROR
            self._emit_event(
                ProcessingEvent(level="error", state=ProcessingState.ERROR, message=str(e))
            )
            # Track with error telemetry
            get_error_telemetry().track_backend_error(
                service="TAJINEService",
                message=f"Analysis failed: {e}",
                exception=e,
                context={
                    "query": request.query,
                    "territory": request.territory,
                    "sector": request.sector,
                },
            )
            raise

    async def _analyze_with_agent(
        self, request: AnalysisRequest, cache_key: str, start_time: datetime
    ) -> AnalysisResult:
        """Run analysis using TAJINEAgent with full PPDSL cycle.

        Args:
            request: Analysis request
            cache_key: Cache key for storing result
            start_time: When processing started

        Returns:
            AnalysisResult from TAJINEAgent execution
        """
        agent = await self._get_agent()
        if agent is None:
            # Fallback to CognitiveEngine
            self._use_agent = False
            return await self.analyze(request, use_cache=False)

        # Build prompt from request
        prompt = request.query
        if request.territory:
            prompt += f" pour le territoire {request.territory}"
        if request.sector:
            prompt += f" dans le secteur {request.sector}"

        # Execute full PPDSL cycle
        task_config = {"prompt": prompt}
        result = await agent.execute_task(task_config)

        # Extract cognitive output from agent result
        cognitive_output = {
            "cognitive_levels": result.get("cognitive_levels", {}),
            "confidence": result.get("confidence", 0.5),
            "analysis": result.get("result", {}),
        }

        # Emit completion events for each level
        for level, data in cognitive_output.get("cognitive_levels", {}).items():
            confidence = data.get("confidence", 0.5) if isinstance(data, dict) else 0.5
            self._emit_event(
                ProcessingEvent(
                    level=level,
                    state=ProcessingState.COMPLETED,
                    confidence=confidence,
                    data=data if isinstance(data, dict) else {},
                )
            )

        # Build result
        processing_time = (datetime.now() - start_time).total_seconds()
        analysis_result = AnalysisResult(
            request=request,
            cognitive_output=cognitive_output,
            summary=self._generate_summary(cognitive_output),
            recommendations=self._extract_recommendations(cognitive_output),
            confidence=cognitive_output.get("confidence", 0.5),
            processing_time=processing_time,
        )

        # Cache and return
        self._cache[cache_key] = analysis_result
        self._current_result = analysis_result
        self._state = ProcessingState.COMPLETED

        return analysis_result

    def _build_tool_results(self, request: AnalysisRequest) -> list[dict[str, Any]]:
        """Build tool results from request data."""
        results = []

        # Add provided data
        if request.data:
            for item in request.data:
                results.append(
                    {"tool": item.get("tool", "data_collect"), "result": item.get("result", item)}
                )

        # Add default data if none provided
        if not results:
            # Generate mock data based on request
            results.append(
                {
                    "tool": "data_collect",
                    "result": {
                        "query": request.query,
                        "territory": request.territory or "France",
                        "sector": request.sector or "all",
                        "companies": 100,
                        "growth": 0.15,
                    },
                }
            )

        return results

    def _generate_summary(self, output: dict[str, Any]) -> str:
        """Generate human-readable summary from cognitive output."""
        levels = output.get("cognitive_levels", {})
        confidence = output.get("confidence", 0.5)

        # Extract key information from each level
        discovery = levels.get("discovery", {})
        causal = levels.get("causal", {})
        scenario = levels.get("scenario", {})
        strategy = levels.get("strategy", {})

        signals = discovery.get("signals", [])
        causes = causal.get("causes", [])
        median = scenario.get("median", {})
        recommendations = strategy.get("recommendations", [])

        # Build summary
        summary_parts = []

        if signals:
            signal_count = len(signals)
            summary_parts.append(f"Découverte: {signal_count} signaux identifiés")

        if causes:
            top_cause = causes[0].get("factor", "inconnu") if causes else "aucun"
            summary_parts.append(f"Cause principale: {top_cause}")

        if median:
            growth = median.get("growth_rate", 0)
            summary_parts.append(f"Croissance médiane projetée: {growth:.1%}")

        if recommendations:
            rec_count = len(recommendations)
            summary_parts.append(f"{rec_count} recommandations stratégiques")

        summary_parts.append(f"Confiance globale: {confidence:.0%}")

        return " | ".join(summary_parts)

    def _extract_recommendations(self, output: dict[str, Any]) -> list[str]:
        """Extract recommendations from cognitive output."""
        levels = output.get("cognitive_levels", {})
        strategy = levels.get("strategy", {})
        recommendations = strategy.get("recommendations", [])

        result = []
        for rec in recommendations:
            if isinstance(rec, dict):
                action = rec.get("action", str(rec))
                priority = rec.get("priority", "medium")
                result.append(f"[{priority.upper()}] {action}")
            else:
                result.append(str(rec))

        return result

    def clear_cache(self) -> None:
        """Clear the result cache."""
        self._cache.clear()

    def get_cached_results(self) -> list[AnalysisResult]:
        """Get all cached results."""
        return list(self._cache.values())


class TAJINEChatService:
    """Chat interface for TAJINE agent.

    Provides conversational interaction with the cognitive engine.
    """

    def __init__(self, tajine_service: TAJINEService | None = None):
        self._service = tajine_service or TAJINEService()
        self._history: list[dict[str, str]] = []

    @property
    def history(self) -> list[dict[str, str]]:
        """Get chat history."""
        return self._history.copy()

    async def send_message(self, message: str) -> str:
        """Send a message and get a response.

        Args:
            message: User message

        Returns:
            Agent response
        """
        self._history.append({"role": "user", "content": message})

        # Parse message for intent
        request = self._parse_message(message)

        try:
            # Run analysis
            result = await self._service.analyze(request)

            # Format response
            response = self._format_response(result)
            self._history.append({"role": "assistant", "content": response})

            return response

        except Exception as e:
            error_msg = f"Erreur lors de l'analyse: {str(e)}"
            self._history.append({"role": "assistant", "content": error_msg})
            return error_msg

    def _parse_message(self, message: str) -> AnalysisRequest:
        """Parse user message into analysis request."""
        message_lower = message.lower()

        # Extract territory
        territory = None
        territories = [
            "paris",
            "lyon",
            "marseille",
            "toulouse",
            "bordeaux",
            "lille",
            "nantes",
            "strasbourg",
            "casablanca",
            "rabat",
            "france",
            "maroc",
        ]
        for t in territories:
            if t in message_lower:
                territory = t.capitalize()
                break

        # Extract sector
        sector = None
        sectors = [
            "tech",
            "technologie",
            "santé",
            "finance",
            "commerce",
            "industrie",
            "service",
            "tourisme",
            "agriculture",
        ]
        for s in sectors:
            if s in message_lower:
                sector = s.capitalize()
                break

        return AnalysisRequest(query=message, territory=territory, sector=sector)

    def _format_response(self, result: AnalysisResult) -> str:
        """Format analysis result as chat response with rich formatting."""
        # Header with confidence color
        conf_color = (
            "green" if result.confidence >= 0.7 else "yellow" if result.confidence >= 0.4 else "red"
        )
        lines = [
            "[bold cyan]━━━ 📊 Analyse TAJINE ━━━[/]",
            f"[{conf_color}]Confiance: {result.confidence:.0%}[/]",
            "",
        ]

        # Cognitive levels summary
        levels = result.cognitive_output.get("cognitive_levels", {})
        if levels:
            lines.append("[bold]🧠 Niveaux Cognitifs:[/]")

            level_icons = {
                "discovery": "🔍",
                "causal": "🔗",
                "scenario": "📊",
                "strategy": "🎯",
                "theoretical": "🧬",
            }
            for level_key in ["discovery", "causal", "scenario", "strategy", "theoretical"]:
                level_data = levels.get(level_key, {})
                if isinstance(level_data, dict):
                    conf = level_data.get("confidence", 0)
                    icon = level_icons.get(level_key, "○")
                    bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
                    lines.append(
                        f"  {icon} {level_key.capitalize()}: [{conf_color}]{bar}[/] {conf:.0%}"
                    )

            lines.append("")

        # Scenario insights if available
        scenario = levels.get("scenario", {})
        if isinstance(scenario, dict) and scenario.get("median"):
            median = scenario.get("median", {})
            lines.append("[bold]📈 Projection:[/]")
            lines.append(f"  Croissance médiane: [cyan]{median.get('growth_rate', 0):.1%}[/]")

            if scenario.get("optimistic"):
                opt = scenario["optimistic"].get("growth_rate", 0)
                lines.append(f"  [green]Optimiste: {opt:.1%}[/]")

            if scenario.get("pessimistic"):
                pess = scenario["pessimistic"].get("growth_rate", 0)
                lines.append(f"  [red]Pessimiste: {pess:.1%}[/]")

            lines.append("")

        # Main summary
        if result.summary:
            lines.append("[bold]📝 Résumé:[/]")
            lines.append(f"  {result.summary}")
            lines.append("")

        # Recommendations with priority coloring
        if result.recommendations:
            lines.append("[bold]📋 Recommandations:[/]")
            for i, rec in enumerate(result.recommendations[:5], 1):
                if "[HIGH]" in rec:
                    lines.append(f"  [red]{i}. {rec}[/]")
                elif "[MEDIUM]" in rec:
                    lines.append(f"  [yellow]{i}. {rec}[/]")
                else:
                    lines.append(f"  [dim]{i}. {rec}[/]")
            lines.append("")

        # Footer
        lines.append(f"[dim]⏱️ Traitement: {result.processing_time:.2f}s[/]")
        lines.append("[bold cyan]━━━━━━━━━━━━━━━━━━━━━[/]")

        return "\n".join(lines)

    def clear_history(self) -> None:
        """Clear chat history."""
        self._history.clear()
