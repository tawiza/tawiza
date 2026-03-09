"""Tests for TAJINE event emitter system."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agents.tajine.events import (
    EventEmitter,
    TAJINECallback,
    TAJINEEvent,
    create_cli_handler,
    create_progress_bar_handler,
)


class TestTAJINEEvent:
    """Test TAJINEEvent enum."""

    def test_lifecycle_events_exist(self):
        """Test lifecycle events are defined."""
        assert TAJINEEvent.TASK_STARTED.value == "tajine.task.started"
        assert TAJINEEvent.TASK_COMPLETED.value == "tajine.task.completed"
        assert TAJINEEvent.TASK_FAILED.value == "tajine.task.failed"

    def test_ppdsl_cycle_events_exist(self):
        """Test PPDSL cycle events are defined."""
        assert TAJINEEvent.PERCEIVE_START.value == "tajine.perceive.start"
        assert TAJINEEvent.PERCEIVE_COMPLETE.value == "tajine.perceive.complete"
        assert TAJINEEvent.PLAN_START.value == "tajine.plan.start"
        assert TAJINEEvent.PLAN_COMPLETE.value == "tajine.plan.complete"
        assert TAJINEEvent.DELEGATE_START.value == "tajine.delegate.start"
        assert TAJINEEvent.DELEGATE_TOOL.value == "tajine.delegate.tool"
        assert TAJINEEvent.DELEGATE_COMPLETE.value == "tajine.delegate.complete"
        assert TAJINEEvent.SYNTHESIZE_START.value == "tajine.synthesize.start"
        assert TAJINEEvent.SYNTHESIZE_LEVEL.value == "tajine.synthesize.level"
        assert TAJINEEvent.SYNTHESIZE_COMPLETE.value == "tajine.synthesize.complete"
        assert TAJINEEvent.LEARN_START.value == "tajine.learn.start"
        assert TAJINEEvent.LEARN_COMPLETE.value == "tajine.learn.complete"

    def test_progress_events_exist(self):
        """Test progress events are defined."""
        assert TAJINEEvent.PROGRESS.value == "tajine.progress"
        assert TAJINEEvent.THINKING.value == "tajine.thinking"


class TestTAJINECallback:
    """Test TAJINECallback dataclass."""

    def test_default_values(self):
        """Test callback has sensible defaults."""
        cb = TAJINECallback(event=TAJINEEvent.PROGRESS)

        assert cb.event == TAJINEEvent.PROGRESS
        assert isinstance(cb.timestamp, datetime)
        assert cb.task_id == ""
        assert cb.phase == ""
        assert cb.progress == 0
        assert cb.message == ""
        assert cb.data == {}
        assert cb.error is None

    def test_full_initialization(self):
        """Test callback with all fields."""
        cb = TAJINECallback(
            event=TAJINEEvent.DELEGATE_TOOL,
            task_id="tajine-abc123",
            phase="delegate",
            progress=50,
            message="Executing data_collect",
            data={"tool": "data_collect", "params": {"territory": "34"}},
        )

        assert cb.task_id == "tajine-abc123"
        assert cb.phase == "delegate"
        assert cb.progress == 50
        assert cb.data["tool"] == "data_collect"

    def test_to_dict(self):
        """Test callback serialization."""
        cb = TAJINECallback(
            event=TAJINEEvent.TASK_COMPLETED,
            task_id="test-123",
            phase="learn",
            progress=100,
            message="Done",
            data={"confidence": 0.85},
        )

        d = cb.to_dict()

        assert d["type"] == "tajine.task.completed"
        assert d["task_id"] == "test-123"
        assert d["phase"] == "learn"
        assert d["progress"] == 100
        assert d["message"] == "Done"
        assert d["data"]["confidence"] == 0.85
        assert "timestamp" in d

    def test_to_dict_with_error(self):
        """Test callback serialization with error."""
        cb = TAJINECallback(
            event=TAJINEEvent.TASK_FAILED,
            error="Connection timeout",
        )

        d = cb.to_dict()

        assert d["type"] == "tajine.task.failed"
        assert d["error"] == "Connection timeout"


def mock_handler(name="test_handler"):
    """Create a MagicMock with __name__ attribute for event handlers."""
    handler = MagicMock()
    handler.__name__ = name
    return handler


class TestEventEmitter:
    """Test EventEmitter class."""

    def test_initialization(self):
        """Test emitter initializes with empty handlers."""
        emitter = EventEmitter()

        assert emitter._handlers == []
        assert emitter._ws_handlers == []

    def test_on_event_registers_handler(self):
        """Test on_event adds handler."""
        emitter = EventEmitter()
        handler = mock_handler("my_handler")

        emitter.on_event(handler)

        assert handler in emitter._handlers

    def test_on_event_prevents_duplicates(self):
        """Test handler is not added twice."""
        emitter = EventEmitter()
        handler = mock_handler("my_handler")

        emitter.on_event(handler)
        emitter.on_event(handler)

        assert len(emitter._handlers) == 1

    def test_off_event_removes_handler(self):
        """Test off_event removes handler."""
        emitter = EventEmitter()
        handler = mock_handler("my_handler")

        emitter.on_event(handler)
        emitter.off_event(handler)

        assert handler not in emitter._handlers

    def test_off_event_noop_for_missing_handler(self):
        """Test off_event does nothing for unregistered handler."""
        emitter = EventEmitter()
        handler = mock_handler("my_handler")

        # Should not raise
        emitter.off_event(handler)

        assert emitter._handlers == []

    def test_emit_calls_all_handlers(self):
        """Test emit calls all registered handlers."""
        emitter = EventEmitter()
        handler1 = mock_handler("handler1")
        handler2 = mock_handler("handler2")

        emitter.on_event(handler1)
        emitter.on_event(handler2)

        cb = TAJINECallback(event=TAJINEEvent.PROGRESS, message="Test")
        emitter.emit(cb)

        handler1.assert_called_once_with(cb)
        handler2.assert_called_once_with(cb)

    def test_emit_handles_handler_errors(self):
        """Test emit continues after handler error."""
        emitter = EventEmitter()
        handler1 = mock_handler("handler1")
        handler1.side_effect = Exception("Handler error")
        handler2 = mock_handler("handler2")

        emitter.on_event(handler1)
        emitter.on_event(handler2)

        cb = TAJINECallback(event=TAJINEEvent.PROGRESS)
        emitter.emit(cb)  # Should not raise

        handler2.assert_called_once_with(cb)

    def test_on_ws_registers_websocket_handler(self):
        """Test on_ws adds WebSocket handler."""
        emitter = EventEmitter()
        ws_handler = AsyncMock()

        emitter.on_ws(ws_handler)

        assert ws_handler in emitter._ws_handlers

    @pytest.mark.asyncio
    async def test_emit_async_calls_both_handler_types(self):
        """Test emit_async calls sync and async handlers."""
        emitter = EventEmitter()
        sync_handler = mock_handler("sync_handler")
        ws_handler = AsyncMock()

        emitter.on_event(sync_handler)
        emitter.on_ws(ws_handler)

        cb = TAJINECallback(event=TAJINEEvent.PROGRESS)
        await emitter.emit_async(cb)

        sync_handler.assert_called_once_with(cb)
        ws_handler.assert_called_once()
        # WS handler receives dict
        call_args = ws_handler.call_args[0][0]
        assert call_args["type"] == "tajine.progress"

    @pytest.mark.asyncio
    async def test_emit_async_handles_ws_errors(self):
        """Test emit_async continues after WS handler error."""
        emitter = EventEmitter()
        ws_handler1 = AsyncMock(side_effect=Exception("WS error"))
        ws_handler2 = AsyncMock()

        emitter.on_ws(ws_handler1)
        emitter.on_ws(ws_handler2)

        cb = TAJINECallback(event=TAJINEEvent.PROGRESS)
        await emitter.emit_async(cb)  # Should not raise

        ws_handler2.assert_called_once()

    def test_emit_progress_convenience_method(self):
        """Test emit_progress helper."""
        emitter = EventEmitter()
        handler = mock_handler("progress_handler")
        emitter.on_event(handler)

        emitter.emit_progress(
            task_id="test-123",
            phase="delegate",
            progress=75,
            message="Processing",
            data={"tool": "test_tool"},
        )

        handler.assert_called_once()
        cb = handler.call_args[0][0]
        assert cb.event == TAJINEEvent.PROGRESS
        assert cb.task_id == "test-123"
        assert cb.phase == "delegate"
        assert cb.progress == 75
        assert cb.data["tool"] == "test_tool"

    def test_emit_thinking_convenience_method(self):
        """Test emit_thinking helper."""
        emitter = EventEmitter()
        handler = mock_handler("thinking_handler")
        emitter.on_event(handler)

        emitter.emit_thinking("test-123", "Analyzing data patterns")

        handler.assert_called_once()
        cb = handler.call_args[0][0]
        assert cb.event == TAJINEEvent.THINKING
        assert cb.task_id == "test-123"
        assert cb.message == "Analyzing data patterns"


class TestCLIHandler:
    """Test create_cli_handler factory."""

    def test_creates_handler(self):
        """Test factory returns callable handler."""
        console = MagicMock()
        handler = create_cli_handler(console)

        assert callable(handler)

    def test_handler_prints_progress(self):
        """Test handler prints progress events."""
        console = MagicMock()
        handler = create_cli_handler(console)

        cb = TAJINECallback(
            event=TAJINEEvent.PROGRESS,
            phase="delegate",
            progress=50,
            message="Working...",
        )
        handler(cb)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "delegate" in call_args
        assert "50%" in call_args

    def test_handler_prints_thinking(self):
        """Test handler prints thinking events."""
        console = MagicMock()
        handler = create_cli_handler(console)

        cb = TAJINECallback(
            event=TAJINEEvent.THINKING,
            message="Analyzing query structure for intent extraction...",
        )
        handler(cb)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "💭" in call_args

    def test_handler_prints_completion(self):
        """Test handler prints completion events."""
        console = MagicMock()
        handler = create_cli_handler(console)

        cb = TAJINECallback(
            event=TAJINEEvent.TASK_COMPLETED,
            message="Analysis complete",
        )
        handler(cb)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "✅" in call_args

    def test_handler_prints_failure(self):
        """Test handler prints failure events."""
        console = MagicMock()
        handler = create_cli_handler(console)

        cb = TAJINECallback(
            event=TAJINEEvent.TASK_FAILED,
            error="Connection failed",
        )
        handler(cb)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "❌" in call_args

    def test_handler_prints_tool_execution(self):
        """Test handler prints tool execution events."""
        console = MagicMock()
        handler = create_cli_handler(console)

        cb = TAJINECallback(
            event=TAJINEEvent.DELEGATE_TOOL,
            data={"tool": "data_collect"},
        )
        handler(cb)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert "🔧" in call_args
        assert "data_collect" in call_args


class TestProgressBarHandler:
    """Test create_progress_bar_handler factory."""

    def test_creates_handler(self):
        """Test factory returns callable handler."""
        console = MagicMock()
        task = MagicMock()
        handler = create_progress_bar_handler(console, task)

        assert callable(handler)

    def test_handler_updates_progress(self):
        """Test handler updates progress bar."""
        console = MagicMock()
        task = MagicMock()
        handler = create_progress_bar_handler(console, task)

        cb = TAJINECallback(
            event=TAJINEEvent.PROGRESS,
            phase="synthesize",
            progress=80,
            message="Aggregating results",
        )
        handler(cb)

        task.update.assert_called_once()
        call_kwargs = task.update.call_args[1]
        assert call_kwargs["completed"] == 80
        assert "synthesize" in call_kwargs["description"]


class TestTAJINEAgentEventIntegration:
    """Test TAJINEAgent event emission."""

    @pytest.mark.asyncio
    async def test_agent_inherits_event_emitter(self):
        """Test TAJINEAgent has EventEmitter methods."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        assert hasattr(agent, "on_event")
        assert hasattr(agent, "off_event")
        assert hasattr(agent, "emit")
        assert hasattr(agent, "emit_async")
        assert hasattr(agent, "on_ws")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.ollama
    async def test_agent_emits_events_during_execution(self):
        """Test agent emits events during execute_task.

        Note: This is an integration test - requires running Ollama.
        Skipped in unit test runs.
        """
        pytest.skip("Integration test: requires Ollama LLM (use pytest -m integration)")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.ollama
    async def test_agent_emits_tool_events(self):
        """Test agent emits tool execution events.

        Note: This is an integration test - requires running Ollama.
        Skipped in unit test runs.
        """
        pytest.skip("Integration test: requires Ollama LLM (use pytest -m integration)")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.ollama
    async def test_agent_emits_progress_with_correct_phases(self):
        """Test agent progress events have correct phase info.

        Note: This is an integration test - requires running Ollama.
        Skipped in unit test runs.
        """
        pytest.skip("Integration test: requires Ollama LLM (use pytest -m integration)")

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.ollama
    async def test_agent_emits_thinking_events(self):
        """Test agent emits thinking events.

        Note: This is an integration test - requires running Ollama.
        Skipped in unit test runs.
        """
        pytest.skip("Integration test: requires Ollama LLM (use pytest -m integration)")
