"""Tests for WebSocket message models."""

from datetime import datetime

import pytest

from src.interfaces.api.websocket.models import (
    AgentsStatusMessage,
    AgentType,
    BrowserActionMessage,
    BrowserScreenshotMessage,
    BrowserStatusMessage,
    BrowserType,
    ChatMessage,
    ChatResponseMessage,
    ChatStreamMessage,
    ErrorMessage,
    MessageType,
    MetricsMessage,
    PingMessage,
    PongMessage,
    TAJINEAnalysisCompleteMessage,
    TAJINEDelegateMessage,
    TAJINELearnMessage,
    TAJINEPerceiveMessage,
    TAJINEPlanMessage,
    TAJINEProgressMessage,
    TAJINESynthesizeMessage,
    TAJINEThinkingMessage,
    TaskCancelMessage,
    TaskCompletedMessage,
    TaskCorrectMessage,
    TaskCreatedMessage,
    TaskCreateMessage,
    TaskErrorMessage,
    TaskPauseMessage,
    TaskProgressMessage,
    TaskResumeMessage,
    TaskStatus,
    TaskStatusChangedMessage,
    TaskThinkingMessage,
    TaskToolCallMessage,
    TaskToolResultMessage,
    TerminalOutputMessage,
    WSMessage,
    parse_message,
)


class TestEnums:
    """Test message type enums."""

    def test_message_types_exist(self):
        assert MessageType.TASK_CREATE == "task.create"
        assert MessageType.CHAT_MESSAGE == "chat.message"
        assert MessageType.PING == "ping"
        assert MessageType.PONG == "pong"
        assert MessageType.ERROR == "error"
        assert MessageType.TAJINE_PERCEIVE == "tajine.perceive"

    def test_task_status(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"

    def test_agent_types(self):
        assert AgentType.BROWSER == "browser"
        assert AgentType.MANUS == "manus"

    def test_browser_types(self):
        assert BrowserType.NODRIVER == "nodriver"
        assert BrowserType.CAMOUFOX == "camoufox"


class TestWSMessage:
    """Test base message."""

    def test_base_message(self):
        msg = WSMessage(type=MessageType.PING)
        assert msg.type == "ping"
        assert msg.timestamp is not None
        assert msg.request_id is not None
        assert msg.session_id is None


class TestTaskMessages:
    """Test task-related messages."""

    def test_task_create(self):
        msg = TaskCreateMessage(
            agent=AgentType.BROWSER,
            prompt="Search for X",
        )
        assert msg.type == "task.create"
        assert msg.priority == 5

    def test_task_create_with_priority(self):
        msg = TaskCreateMessage(
            agent=AgentType.DATA,
            prompt="Analyze",
            priority=9,
            context={"dept": "75"},
        )
        assert msg.priority == 9
        assert msg.context == {"dept": "75"}

    def test_task_pause(self):
        msg = TaskPauseMessage(task_id="t1")
        assert msg.type == "task.pause"

    def test_task_resume(self):
        msg = TaskResumeMessage(task_id="t1")
        assert msg.type == "task.resume"

    def test_task_cancel(self):
        msg = TaskCancelMessage(task_id="t1")
        assert msg.type == "task.cancel"

    def test_task_correct(self):
        msg = TaskCorrectMessage(task_id="t1", message="Try another approach")
        assert msg.message == "Try another approach"

    def test_task_created(self):
        msg = TaskCreatedMessage(
            task_id="t1",
            agent=AgentType.GENERAL,
            prompt="Hello",
        )
        assert msg.status == "pending"

    def test_task_progress(self):
        msg = TaskProgressMessage(
            task_id="t1",
            step=3,
            total_steps=10,
            message="Processing...",
            percent=30.0,
        )
        assert msg.percent == 30.0

    def test_task_thinking(self):
        msg = TaskThinkingMessage(task_id="t1", content="Analyzing data...")
        assert msg.content == "Analyzing data..."

    def test_task_tool_call(self):
        msg = TaskToolCallMessage(
            task_id="t1",
            tool="search_sirene",
            args={"siret": "12345"},
        )
        assert msg.tool == "search_sirene"

    def test_task_tool_result(self):
        msg = TaskToolResultMessage(
            task_id="t1",
            tool="search_sirene",
            result={"name": "Corp"},
        )
        assert msg.success is True

    def test_task_completed(self):
        msg = TaskCompletedMessage(
            task_id="t1",
            result={"report": "done"},
            duration_seconds=5.2,
        )
        assert msg.duration_seconds == 5.2

    def test_task_error(self):
        msg = TaskErrorMessage(task_id="t1", error="API timeout")
        assert msg.traceback is None

    def test_task_status_changed(self):
        msg = TaskStatusChangedMessage(
            type=MessageType.TASK_PAUSED,
            task_id="t1",
            status=TaskStatus.PAUSED,
        )
        assert msg.status == "paused"


class TestTAJINEMessages:
    """Test TAJINE-specific messages."""

    def test_perceive(self):
        msg = TAJINEPerceiveMessage(task_id="t1", status="start", message="Perceiving...")
        assert msg.phase == "perceive"
        assert msg.type == "tajine.perceive"

    def test_plan(self):
        msg = TAJINEPlanMessage(
            task_id="t1",
            status="complete",
            subtasks=[{"id": 1, "desc": "fetch data"}],
        )
        assert msg.phase == "plan"
        assert len(msg.subtasks) == 1

    def test_delegate(self):
        msg = TAJINEDelegateMessage(
            task_id="t1",
            status="start",
            tool="sirene_search",
            subtask_index=0,
            total_subtasks=3,
        )
        assert msg.total_subtasks == 3

    def test_synthesize(self):
        msg = TAJINESynthesizeMessage(task_id="t1", status="start", level=2)
        assert msg.level == 2

    def test_learn(self):
        msg = TAJINELearnMessage(task_id="t1", status="complete", trust_delta=0.05)
        assert msg.trust_delta == 0.05

    def test_progress(self):
        msg = TAJINEProgressMessage(
            task_id="t1",
            phase="perceive",
            progress=50,
            message="Halfway",
        )
        assert msg.progress == 50

    def test_thinking(self):
        msg = TAJINEThinkingMessage(task_id="t1", content="Reasoning about correlations...")
        assert "correlations" in msg.content

    def test_analysis_complete(self):
        msg = TAJINEAnalysisCompleteMessage(
            task_id="t1",
            department="75",
            cognitive_level="causal",
            confidence=0.85,
            insights=["High unemployment correlation with real estate"],
        )
        assert msg.department == "75"
        assert len(msg.insights) == 1
        assert msg.fast_mode is False


class TestChatMessages:
    """Test chat messages."""

    def test_chat_message(self):
        msg = ChatMessage(message="Analyze department 75")
        assert msg.agent == "general"

    def test_chat_response(self):
        msg = ChatResponseMessage(
            content="Here's the analysis...",
            agent=AgentType.DATA,
            conversation_id="conv1",
        )
        assert msg.conversation_id == "conv1"

    def test_chat_stream(self):
        msg = ChatStreamMessage(content="chunk", conversation_id="conv1")
        assert msg.done is False


class TestSystemMessages:
    """Test system messages."""

    def test_metrics(self):
        msg = MetricsMessage(
            cpu_percent=45.0,
            ram_percent=62.0,
            gpu_percent=0.0,
            disk_percent=42.0,
            active_tasks=3,
        )
        assert msg.active_tasks == 3

    def test_agents_status(self):
        msg = AgentsStatusMessage(agents={"browser": {"status": "idle"}})
        assert "browser" in msg.agents

    def test_error(self):
        msg = ErrorMessage(error="Something went wrong", code="INTERNAL_ERROR")
        assert msg.code == "INTERNAL_ERROR"

    def test_ping_pong(self):
        ping = PingMessage()
        pong = PongMessage()
        assert ping.type == "ping"
        assert pong.type == "pong"


class TestBrowserMessages:
    """Test browser automation messages."""

    def test_screenshot(self):
        msg = BrowserScreenshotMessage(
            task_id="t1",
            action="navigate",
            screenshot_b64="base64data",
            url="https://example.com",
        )
        assert msg.viewport_width == 1280
        assert msg.browser_type == "playwright"

    def test_action(self):
        msg = BrowserActionMessage(
            task_id="t1",
            action="click",
            selector="#button",
            duration_ms=150,
        )
        assert msg.success is True

    def test_status(self):
        msg = BrowserStatusMessage(
            task_id="t1",
            is_running=True,
            current_url="https://example.com",
            page_title="Example",
        )
        assert msg.stealth_mode is False


class TestTerminalOutput:
    """Test terminal output message."""

    def test_stdout(self):
        msg = TerminalOutputMessage(
            task_id="t1",
            content="Hello world\n",
        )
        assert msg.stream == "stdout"

    def test_stderr(self):
        msg = TerminalOutputMessage(
            task_id="t1",
            content="Error!",
            stream="stderr",
        )
        assert msg.stream == "stderr"


class TestParseMessage:
    """Test message parsing."""

    def test_parse_ping(self):
        msg = parse_message({"type": "ping"})
        assert isinstance(msg, PingMessage)

    def test_parse_pong(self):
        msg = parse_message({"type": "pong"})
        assert isinstance(msg, PongMessage)

    def test_parse_error(self):
        msg = parse_message({"type": "error", "error": "boom"})
        assert isinstance(msg, ErrorMessage)
        assert msg.error == "boom"

    def test_parse_task_create(self):
        msg = parse_message(
            {
                "type": "task.create",
                "agent": "browser",
                "prompt": "Search",
            }
        )
        assert isinstance(msg, TaskCreateMessage)

    def test_parse_chat_message(self):
        msg = parse_message(
            {
                "type": "chat.message",
                "message": "Hello",
            }
        )
        assert isinstance(msg, ChatMessage)

    def test_parse_unknown_type_raises(self):
        """Unknown types raise validation error since MessageType is a strict enum."""
        with pytest.raises(Exception):
            parse_message({"type": "unknown.type"})

    def test_parse_tajine_perceive(self):
        msg = parse_message(
            {
                "type": "tajine.perceive",
                "task_id": "t1",
                "status": "start",
            }
        )
        assert isinstance(msg, TAJINEPerceiveMessage)

    def test_parse_browser_screenshot(self):
        msg = parse_message(
            {
                "type": "browser.screenshot",
                "task_id": "t1",
                "action": "navigate",
                "screenshot_b64": "data",
            }
        )
        assert isinstance(msg, BrowserScreenshotMessage)
