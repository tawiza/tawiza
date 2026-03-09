"""WebSocket API for TUI communication."""

from src.interfaces.api.websocket.handlers import (
    BrowserHandler,
    TAJINEHandler,
    get_browser_handler,
    get_tajine_handler,
    setup_handlers,
)
from src.interfaces.api.websocket.models import (
    BrowserActionMessage,
    # Browser messages
    BrowserScreenshotMessage,
    BrowserStatusMessage,
    ChatMessage,
    MessageType,
    MetricsMessage,
    TAJINEDelegateMessage,
    TAJINELearnMessage,
    # TAJINE messages
    TAJINEPerceiveMessage,
    TAJINEPlanMessage,
    TAJINEProgressMessage,
    TAJINESynthesizeMessage,
    TAJINEThinkingMessage,
    TaskCompletedMessage,
    TaskCreateMessage,
    TaskProgressMessage,
    WSMessage,
)
from src.interfaces.api.websocket.server import WebSocketManager, get_ws_manager

__all__ = [
    # Core
    "WSMessage",
    "MessageType",
    "WebSocketManager",
    "get_ws_manager",
    "setup_handlers",
    # Task messages
    "TaskCreateMessage",
    "TaskProgressMessage",
    "TaskCompletedMessage",
    "ChatMessage",
    "MetricsMessage",
    # TAJINE
    "TAJINEHandler",
    "get_tajine_handler",
    "TAJINEPerceiveMessage",
    "TAJINEPlanMessage",
    "TAJINEDelegateMessage",
    "TAJINESynthesizeMessage",
    "TAJINELearnMessage",
    "TAJINEProgressMessage",
    "TAJINEThinkingMessage",
    # Browser
    "BrowserHandler",
    "get_browser_handler",
    "BrowserScreenshotMessage",
    "BrowserActionMessage",
    "BrowserStatusMessage",
]
