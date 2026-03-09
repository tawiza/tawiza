"""Chat Modal Widget.

A floating modal overlay for TAJINE chat functionality.
Features:
- 70% width, 80% height, centered
- Opens with Ctrl+C, closes with Esc
- Message history with timestamps
- Input field with auto-focus
"""

from dataclasses import dataclass
from datetime import datetime

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


@dataclass
class ChatMessage:
    """A single chat message."""

    content: str
    is_user: bool
    timestamp: datetime

    @property
    def formatted_time(self) -> str:
        """Get formatted timestamp."""
        return self.timestamp.strftime("%H:%M")


class MessageBubble(Static):
    """A single message bubble in the chat."""

    DEFAULT_CSS = """
    MessageBubble {
        width: 100%;
        margin: 1 0;
        padding: 1;
    }

    MessageBubble.user {
        text-align: right;
        background: $primary-darken-1;
        margin-left: 10;
    }

    MessageBubble.assistant {
        text-align: left;
        background: $surface-lighten-1;
        margin-right: 10;
    }

    MessageBubble .sender {
        text-style: bold;
        margin-bottom: 1;
    }

    MessageBubble .time {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self, message: ChatMessage, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        if message.is_user:
            self.add_class("user")
        else:
            self.add_class("assistant")

    def compose(self) -> ComposeResult:
        return []

    def on_mount(self) -> None:
        """Render the message."""
        sender = "👤 Vous" if self.message.is_user else "🤖 TAJINE"

        content = (
            f"[bold]{sender}[/] [dim]{self.message.formatted_time}[/]\n"
            f"{self.message.content}"
        )
        self.update(content)


class ChatModal(ModalScreen):
    """Modal screen for TAJINE chat.

    Opens as a centered overlay (70% x 80% of screen).
    Use Ctrl+C to open from any screen, Esc to close.
    """

    DEFAULT_CSS = """
    ChatModal {
        align: center middle;
    }

    ChatModal > Container {
        width: 70%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 0;
    }

    ChatModal .modal-header {
        dock: top;
        height: 3;
        background: $primary;
        color: $surface;
        padding: 0 2;
        content-align: left middle;
    }

    ChatModal .modal-header .title {
        text-style: bold;
    }

    ChatModal .close-button {
        dock: right;
        width: auto;
        height: 3;
        min-width: 5;
        background: transparent;
        border: none;
        color: $surface;
    }

    ChatModal .close-button:hover {
        background: $primary-lighten-1;
    }

    ChatModal .chat-messages {
        height: 1fr;
        padding: 1;
        background: $surface-darken-1;
    }

    ChatModal .chat-input-container {
        dock: bottom;
        height: 3;
        background: $surface;
        border-top: solid $primary;
        padding: 0 1;
    }

    ChatModal .chat-input-container Input {
        width: 1fr;
    }

    ChatModal .chat-input-container Button {
        width: auto;
        min-width: 4;
    }

    ChatModal .empty-state {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Fermer", show=True),
    ]

    class MessageSent(Message):
        """Message when user sends a chat message."""

        def __init__(self, content: str):
            super().__init__()
            self.content = content

    class Closed(Message):
        """Message when modal is closed."""
        pass

    def __init__(self, messages: list[ChatMessage] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._messages: list[ChatMessage] = messages or []

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        with Container():
            # Header
            with Container(classes="modal-header"):
                yield Static("💬 TAJINE Chat", classes="title")
                yield Button("✕", classes="close-button", id="close-btn")

            # Messages area
            with VerticalScroll(classes="chat-messages", id="messages-scroll"):
                if not self._messages:
                    yield Static(
                        "[dim]Démarrez une conversation avec TAJINE...[/]",
                        classes="empty-state",
                        id="empty-state",
                    )
                else:
                    for msg in self._messages:
                        yield MessageBubble(msg)

            # Input area
            with Container(classes="chat-input-container"):
                yield Input(
                    placeholder="Demandez une analyse...",
                    id="chat-input",
                )
                yield Button("📤", id="send-btn")

    def on_mount(self) -> None:
        """Focus input on mount."""
        self.query_one("#chat-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "close-btn":
            self.action_close()
        elif event.button.id == "send-btn":
            self._send_message()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle enter key in input."""
        self._send_message()

    def _send_message(self) -> None:
        """Send the current message."""
        input_widget = self.query_one("#chat-input", Input)
        content = input_widget.value.strip()

        if not content:
            return

        # Add user message
        user_msg = ChatMessage(
            content=content,
            is_user=True,
            timestamp=datetime.now(),
        )
        self._add_message(user_msg)

        # Clear input
        input_widget.value = ""

        # Post message event
        self.post_message(self.MessageSent(content))

        logger.debug(f"Chat message sent: {content[:50]}...")

    def _add_message(self, message: ChatMessage) -> None:
        """Add a message to the chat."""
        self._messages.append(message)

        # Remove empty state if present
        try:
            empty = self.query_one("#empty-state")
            empty.remove()
        except Exception:
            pass

        # Add message bubble
        scroll = self.query_one("#messages-scroll", VerticalScroll)
        bubble = MessageBubble(message)
        scroll.mount(bubble)

        # Scroll to bottom
        scroll.scroll_end(animate=False)

    def add_response(self, content: str) -> None:
        """Add an assistant response to the chat."""
        msg = ChatMessage(
            content=content,
            is_user=False,
            timestamp=datetime.now(),
        )
        self._add_message(msg)

    def action_close(self) -> None:
        """Close the modal."""
        self.post_message(self.Closed())
        self.dismiss()

    def get_messages(self) -> list[ChatMessage]:
        """Get all messages."""
        return self._messages.copy()
