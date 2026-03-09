"""WebSocket message models for TUI-Server communication."""

import uuid
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Enums
# ============================================================================

class MessageType(StrEnum):
    """Types of WebSocket messages."""
    # Task messages (TUI → Server)
    TASK_CREATE = "task.create"
    TASK_PAUSE = "task.pause"
    TASK_RESUME = "task.resume"
    TASK_CANCEL = "task.cancel"
    TASK_CORRECT = "task.correct"

    # Task messages (Server → TUI)
    TASK_CREATED = "task.created"
    TASK_PROGRESS = "task.progress"
    TASK_THINKING = "task.thinking"
    TASK_TOOL_CALL = "task.tool_call"
    TASK_TOOL_RESULT = "task.tool_result"
    TASK_COMPLETED = "task.completed"
    TASK_ERROR = "task.error"
    TASK_PAUSED = "task.paused"
    TASK_RESUMED = "task.resumed"
    TASK_CANCELLED = "task.cancelled"

    # TAJINE-specific messages (Server → TUI)
    TAJINE_PERCEIVE = "tajine.perceive"
    TAJINE_PLAN = "tajine.plan"
    TAJINE_DELEGATE = "tajine.delegate"
    TAJINE_SYNTHESIZE = "tajine.synthesize"
    TAJINE_LEARN = "tajine.learn"
    TAJINE_PROGRESS = "tajine.progress"
    TAJINE_THINKING = "tajine.thinking"
    TAJINE_ANALYSIS_COMPLETE = "tajine.analysis_complete"

    # Chat messages
    CHAT_MESSAGE = "chat.message"
    CHAT_RESPONSE = "chat.response"
    CHAT_STREAM = "chat.stream"
    CHAT_STREAM_END = "chat.stream_end"

    # Browser automation messages
    BROWSER_SCREENSHOT = "browser.screenshot"
    BROWSER_ACTION = "browser.action"
    BROWSER_STATUS = "browser.status"

    # Code execution messages
    CODE_TERMINAL = "code.terminal"

    # System messages
    METRICS_UPDATE = "metrics.update"
    AGENTS_STATUS = "agents.status"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class TaskStatus(StrEnum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(StrEnum):
    """Available agent types."""
    BROWSER = "browser"
    DATA = "data"
    CODER = "coder"
    GENERAL = "general"
    MANUS = "manus"


# ============================================================================
# Base Message
# ============================================================================

class WSMessage(BaseModel):
    """Base WebSocket message."""
    model_config = ConfigDict(use_enum_values=True)

    type: MessageType
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: str | None = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str | None = None


# ============================================================================
# Task Messages (TUI → Server)
# ============================================================================

class TaskCreateMessage(WSMessage):
    """Request to create a new task."""
    type: MessageType = MessageType.TASK_CREATE
    agent: AgentType
    prompt: str
    context: dict[str, Any] | None = None
    priority: int = Field(default=5, ge=1, le=10)


class TaskControlMessage(WSMessage):
    """Base for task control messages."""
    task_id: str


class TaskPauseMessage(TaskControlMessage):
    """Request to pause a task."""
    type: MessageType = MessageType.TASK_PAUSE


class TaskResumeMessage(TaskControlMessage):
    """Request to resume a task."""
    type: MessageType = MessageType.TASK_RESUME


class TaskCancelMessage(TaskControlMessage):
    """Request to cancel a task."""
    type: MessageType = MessageType.TASK_CANCEL


class TaskCorrectMessage(TaskControlMessage):
    """Send a correction/guidance to a running task."""
    type: MessageType = MessageType.TASK_CORRECT
    message: str


# ============================================================================
# Task Messages (Server → TUI)
# ============================================================================

class TaskCreatedMessage(WSMessage):
    """Task was created successfully."""
    type: MessageType = MessageType.TASK_CREATED
    task_id: str
    agent: AgentType
    prompt: str
    status: TaskStatus = TaskStatus.PENDING


class TaskProgressMessage(WSMessage):
    """Task progress update."""
    type: MessageType = MessageType.TASK_PROGRESS
    task_id: str
    step: int
    total_steps: int
    message: str
    percent: float = 0.0


class TaskThinkingMessage(WSMessage):
    """Agent is thinking/reasoning."""
    type: MessageType = MessageType.TASK_THINKING
    task_id: str
    content: str


class TaskToolCallMessage(WSMessage):
    """Agent is calling a tool."""
    type: MessageType = MessageType.TASK_TOOL_CALL
    task_id: str
    tool: str
    args: dict[str, Any]


class TaskToolResultMessage(WSMessage):
    """Tool returned a result."""
    type: MessageType = MessageType.TASK_TOOL_RESULT
    task_id: str
    tool: str
    result: Any
    success: bool = True


class TaskCompletedMessage(WSMessage):
    """Task completed successfully."""
    type: MessageType = MessageType.TASK_COMPLETED
    task_id: str
    result: Any
    duration_seconds: float


class TaskErrorMessage(WSMessage):
    """Task encountered an error."""
    type: MessageType = MessageType.TASK_ERROR
    task_id: str
    error: str
    traceback: str | None = None


class TaskStatusChangedMessage(WSMessage):
    """Task status changed (paused/resumed/cancelled)."""
    task_id: str
    status: TaskStatus
    message: str | None = None


# ============================================================================
# TAJINE Messages (Server → TUI)
# ============================================================================

class TAJINEPhaseMessage(WSMessage):
    """TAJINE PPDSL cycle phase update."""
    task_id: str
    phase: str  # perceive, plan, delegate, synthesize, learn
    status: str  # start, complete
    progress: int = 0  # 0-100
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class TAJINEPerceiveMessage(TAJINEPhaseMessage):
    """TAJINE perceive phase update."""
    type: MessageType = MessageType.TAJINE_PERCEIVE
    phase: str = "perceive"


class TAJINEPlanMessage(TAJINEPhaseMessage):
    """TAJINE plan phase update."""
    type: MessageType = MessageType.TAJINE_PLAN
    phase: str = "plan"
    subtasks: list[dict[str, Any]] = Field(default_factory=list)


class TAJINEDelegateMessage(TAJINEPhaseMessage):
    """TAJINE delegate phase update."""
    type: MessageType = MessageType.TAJINE_DELEGATE
    phase: str = "delegate"
    tool: str | None = None
    subtask_index: int = 0
    total_subtasks: int = 0


class TAJINESynthesizeMessage(TAJINEPhaseMessage):
    """TAJINE synthesize phase update."""
    type: MessageType = MessageType.TAJINE_SYNTHESIZE
    phase: str = "synthesize"
    level: int = 0  # Current aggregation level


class TAJINELearnMessage(TAJINEPhaseMessage):
    """TAJINE learn phase update."""
    type: MessageType = MessageType.TAJINE_LEARN
    phase: str = "learn"
    trust_delta: float = 0.0


class TAJINEProgressMessage(WSMessage):
    """TAJINE general progress update."""
    type: MessageType = MessageType.TAJINE_PROGRESS
    task_id: str
    phase: str
    progress: int
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class TAJINEThinkingMessage(WSMessage):
    """TAJINE thinking/reasoning update."""
    type: MessageType = MessageType.TAJINE_THINKING
    task_id: str
    content: str


class TAJINEAnalysisCompleteMessage(WSMessage):
    """TAJINE analysis complete - broadcast to sync other tabs."""
    type: MessageType = MessageType.TAJINE_ANALYSIS_COMPLETE
    task_id: str
    department: str | None = None
    cognitive_level: str = "analytical"
    fast_mode: bool = False
    confidence: float = 0.0
    # Chart data for visualizations
    radar_data: list[dict[str, Any]] = Field(default_factory=list)
    treemap_data: list[dict[str, Any]] = Field(default_factory=list)
    heatmap_data: dict[str, Any] = Field(default_factory=dict)
    sankey_data: dict[str, Any] = Field(default_factory=dict)
    insights: list[str] = Field(default_factory=list)


class TerminalOutputMessage(WSMessage):
    """Real-time terminal output from code execution."""
    type: MessageType = MessageType.CODE_TERMINAL
    task_id: str
    content: str
    stream: str = "stdout"  # stdout or stderr


# ============================================================================
# Chat Messages
# ============================================================================

class ChatMessage(WSMessage):
    """Chat message from user."""
    type: MessageType = MessageType.CHAT_MESSAGE
    agent: AgentType = AgentType.GENERAL
    message: str
    conversation_id: str | None = None


class ChatResponseMessage(WSMessage):
    """Complete chat response from agent."""
    type: MessageType = MessageType.CHAT_RESPONSE
    content: str
    agent: AgentType
    conversation_id: str


class ChatStreamMessage(WSMessage):
    """Streaming chat response chunk."""
    type: MessageType = MessageType.CHAT_STREAM
    content: str
    conversation_id: str
    done: bool = False


# ============================================================================
# System Messages
# ============================================================================

class MetricsMessage(WSMessage):
    """System metrics update."""
    type: MessageType = MessageType.METRICS_UPDATE
    cpu_percent: float
    ram_percent: float
    gpu_percent: float
    disk_percent: float
    active_tasks: int = 0


class AgentsStatusMessage(WSMessage):
    """Status of all registered agents."""
    type: MessageType = MessageType.AGENTS_STATUS
    agents: dict[str, dict[str, Any]]


class ErrorMessage(WSMessage):
    """Error message."""
    type: MessageType = MessageType.ERROR
    error: str
    code: str | None = None


class PingMessage(WSMessage):
    """Ping for keepalive."""
    type: MessageType = MessageType.PING


class PongMessage(WSMessage):
    """Pong response."""
    type: MessageType = MessageType.PONG


# ============================================================================
# Browser Automation Messages
# ============================================================================

class BrowserType(StrEnum):
    """Browser type for stealth automation."""
    NODRIVER = "nodriver"      # Chrome-based, CDP direct
    CAMOUFOX = "camoufox"      # Firefox-based, C++ hooks
    PLAYWRIGHT = "playwright"  # Standard Playwright
    BROWSER_USE = "browser_use"  # browser-use library


class BrowserScreenshotMessage(WSMessage):
    """Browser screenshot update for Agent Live panel."""
    type: MessageType = MessageType.BROWSER_SCREENSHOT
    task_id: str
    action: str  # Action that triggered the screenshot
    screenshot_b64: str  # Base64 encoded PNG
    url: str | None = None
    viewport_width: int = 1280
    viewport_height: int = 720
    browser_type: BrowserType = BrowserType.PLAYWRIGHT
    browser_info: dict[str, Any] = Field(default_factory=dict)  # e.g., fingerprint config


class BrowserActionMessage(WSMessage):
    """Browser action request/notification."""
    type: MessageType = MessageType.BROWSER_ACTION
    task_id: str
    action: str  # navigate, click, type, scroll, etc.
    selector: str | None = None
    value: str | None = None
    success: bool = True
    error: str | None = None
    duration_ms: int = 0


class BrowserStatusMessage(WSMessage):
    """Browser agent status update."""
    type: MessageType = MessageType.BROWSER_STATUS
    task_id: str
    is_running: bool
    current_url: str | None = None
    page_title: str | None = None
    browser_type: BrowserType = BrowserType.PLAYWRIGHT
    stealth_mode: bool = False  # True if using nodriver/camoufox


# ============================================================================
# Message Parsing
# ============================================================================

def parse_message(data: dict[str, Any]) -> WSMessage:
    """Parse a raw dict into the appropriate message type."""
    msg_type = data.get("type")

    type_mapping = {
        # Task messages
        MessageType.TASK_CREATE: TaskCreateMessage,
        MessageType.TASK_PAUSE: TaskPauseMessage,
        MessageType.TASK_RESUME: TaskResumeMessage,
        MessageType.TASK_CANCEL: TaskCancelMessage,
        MessageType.TASK_CORRECT: TaskCorrectMessage,
        MessageType.TASK_CREATED: TaskCreatedMessage,
        MessageType.TASK_PROGRESS: TaskProgressMessage,
        MessageType.TASK_THINKING: TaskThinkingMessage,
        MessageType.TASK_TOOL_CALL: TaskToolCallMessage,
        MessageType.TASK_TOOL_RESULT: TaskToolResultMessage,
        MessageType.TASK_COMPLETED: TaskCompletedMessage,
        MessageType.TASK_ERROR: TaskErrorMessage,
        # TAJINE messages
        MessageType.TAJINE_PERCEIVE: TAJINEPerceiveMessage,
        MessageType.TAJINE_PLAN: TAJINEPlanMessage,
        MessageType.TAJINE_DELEGATE: TAJINEDelegateMessage,
        MessageType.TAJINE_SYNTHESIZE: TAJINESynthesizeMessage,
        MessageType.TAJINE_LEARN: TAJINELearnMessage,
        MessageType.TAJINE_PROGRESS: TAJINEProgressMessage,
        MessageType.TAJINE_THINKING: TAJINEThinkingMessage,
        MessageType.TAJINE_ANALYSIS_COMPLETE: TAJINEAnalysisCompleteMessage,
        # Chat messages
        MessageType.CHAT_MESSAGE: ChatMessage,
        MessageType.CHAT_RESPONSE: ChatResponseMessage,
        MessageType.CHAT_STREAM: ChatStreamMessage,
        # Browser messages
        MessageType.BROWSER_SCREENSHOT: BrowserScreenshotMessage,
        MessageType.BROWSER_ACTION: BrowserActionMessage,
        MessageType.BROWSER_STATUS: BrowserStatusMessage,
        # Code messages
        MessageType.CODE_TERMINAL: TerminalOutputMessage,
        # System messages
        MessageType.METRICS_UPDATE: MetricsMessage,
        MessageType.AGENTS_STATUS: AgentsStatusMessage,
        MessageType.ERROR: ErrorMessage,
        MessageType.PING: PingMessage,
        MessageType.PONG: PongMessage,
    }

    message_class = type_mapping.get(msg_type, WSMessage)
    return message_class(**data)
