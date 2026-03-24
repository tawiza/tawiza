"""Chat Screen - Direct conversation with agents."""

import os
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Input, Select, Static


@dataclass
class ChatMessage:
    """A chat message."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    agent: str = "general"


class MessageBubble(Static):
    """A chat message bubble."""

    DEFAULT_CSS = """
    MessageBubble {
        width: 100%;
        padding: 1;
        margin: 0 0 1 0;
    }

    MessageBubble.user {
        background: $primary;
        color: $surface;
        text-align: right;
        margin-left: 10;
    }

    MessageBubble.assistant {
        background: $surface-lighten-1;
        border-left: thick $accent;
        margin-right: 10;
    }

    MessageBubble .timestamp {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self, message: ChatMessage, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.add_class(message.role)

    def render(self) -> str:
        """Render the message bubble."""
        time_str = self.message.timestamp.strftime("%H:%M")

        if self.message.role == "user":
            return f"{self.message.content}\n[dim]{time_str}[/]"
        else:
            agent_label = f"[bold cyan]{self.message.agent}[/]"
            return f"{agent_label} [dim]{time_str}[/]\n{self.message.content}"


class ChatHistory(ScrollableContainer):
    """Scrollable chat history."""

    DEFAULT_CSS = """
    ChatHistory {
        height: 1fr;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages: list[ChatMessage] = []

    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the history."""
        self._messages.append(message)
        bubble = MessageBubble(message)
        self.mount(bubble)
        self.scroll_end(animate=True)

    def clear_messages(self) -> None:
        """Clear all messages."""
        self._messages.clear()
        self.remove_children()


class StreamingMessage(Static):
    """A message that updates as content streams in."""

    DEFAULT_CSS = """
    StreamingMessage {
        width: 100%;
        padding: 1;
        margin: 0 0 1 0;
        background: $surface-lighten-1;
        border-left: thick $accent;
        margin-right: 10;
    }

    StreamingMessage .cursor {
        color: $accent;
    }
    """

    content = reactive("")

    def __init__(self, agent: str = "general", **kwargs):
        super().__init__(**kwargs)
        self.agent = agent
        self._start_time = datetime.now()

    def render(self) -> str:
        """Render with blinking cursor."""
        time_str = self._start_time.strftime("%H:%M")
        agent_label = f"[bold cyan]{self.agent}[/]"

        if self.content:
            return f"{agent_label} [dim]{time_str}[/]\n{self.content}[blink]▌[/]"
        else:
            return f"{agent_label} [dim]{time_str}[/]\n[dim]Thinking...[/] [blink]▌[/]"

    def append_content(self, text: str) -> None:
        """Append content to the message."""
        self.content += text

    def finalize(self) -> ChatMessage:
        """Finalize the streaming message."""
        return ChatMessage(
            role="assistant", content=self.content, timestamp=self._start_time, agent=self.agent
        )


class ChatScreen(Container):
    """Chat content (Container for ContentSwitcher)."""

    BINDINGS = [
        Binding("ctrl+t", "focus_input", "^T:Type", show=True, priority=True),
        Binding("ctrl+l", "clear_chat", "^L:Clear", show=True),
        Binding("ctrl+n", "new_chat", "^N:New", show=True),
        Binding("ctrl+a", "cycle_agent", "^A:Agent", show=True),
    ]

    DEFAULT_CSS = """
    ChatScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #chat-header {
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary;
        background: $surface-darken-1;
    }

    #agent-selector {
        width: 30;
        height: 3;
    }

    #chat-area {
        height: 1fr;
        padding: 1;
    }

    #input-area {
        dock: bottom;
        height: 4;
        border-top: solid $primary;
        background: $surface-darken-1;
        padding: 0 1;
    }

    #input-area Static {
        height: 1;
        color: $accent;
    }

    #input-area Input {
        height: 3;
    }
    """

    current_agent = reactive("general")

    # All available agents from AgentOrchestrator
    AGENTS = [
        ("general", "General Assistant"),
        ("manus", "Manus Agent (Reasoning)"),
        ("browser", "Browser Automation"),
        ("coder", "Code Generator"),
        ("research", "Deep Research"),
        ("data", "Data Analyst"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._conversation_id: str | None = None
        self._streaming_message: StreamingMessage | None = None
        self._ws_connected = False

    def compose(self) -> ComposeResult:
        """Create the chat layout."""
        # Header with agent selector
        with Horizontal(id="chat-header"):
            yield Static("[bold cyan]CHAT[/] - Direct conversation with agents")
            yield Select(
                [(label, value) for value, label in self.AGENTS],
                value="general",
                id="agent-selector",
            )

        # Chat history
        yield ChatHistory(id="chat-area")

        # Input area
        with Vertical(id="input-area"):
            yield Static("[bold]MESSAGE[/] - Enter to send, Ctrl+T to focus")
            yield Input(placeholder="Type your message...", id="chat-input")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._add_welcome_message()
        # Use run_worker to properly schedule the async coroutine
        self.run_worker(self._try_connect_ws())

    def _add_welcome_message(self) -> None:
        """Add welcome message."""
        chat = self.query_one("#chat-area", ChatHistory)
        chat.add_message(
            ChatMessage(
                role="assistant",
                content="Hello! I'm ready to help. Select an agent above and start chatting.",
                agent="system",
            )
        )

    async def _try_connect_ws(self) -> None:
        """Try to connect to WebSocket server."""
        try:
            from src.cli.v3.tui.services.websocket_client import get_ws_client

            client = get_ws_client()

            # Register handlers for chat events
            client.on_message("chat.stream", self._on_chat_stream)
            client.on_message("chat.response", self._on_chat_response)

            # Also handle task events (for manus agent which uses tasks)
            client.on_message("task.thinking", self._on_task_thinking)
            client.on_message("task.progress", self._on_task_progress)
            client.on_message("task.completed", self._on_task_completed)
            client.on_message("task.error", self._on_task_error)

            if await client.connect():
                self._ws_connected = True
                self.app.notify("[green]Connected to Tawiza API[/]", timeout=3)
                logger.info("WebSocket connected to API")
            else:
                self.app.notify("[yellow]Offline mode - using Ollama directly[/]", timeout=3)

        except Exception as e:
            logger.warning(f"WebSocket not available: {e}")
            self.app.notify("[yellow]Offline mode - using Ollama directly[/]", timeout=3)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle agent selection change."""
        if event.select.id == "agent-selector":
            self.current_agent = event.value
            self.app.notify(f"Agent: {event.value}", timeout=1)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission."""
        if event.input.id == "chat-input":
            message = event.value.strip()
            if message:
                event.input.value = ""
                self._send_message(message)

    def _send_message(self, content: str) -> None:
        """Send a message to the agent."""
        chat = self.query_one("#chat-area", ChatHistory)

        # Add user message
        user_msg = ChatMessage(role="user", content=content)
        chat.add_message(user_msg)

        if self._ws_connected:
            # Send via WebSocket
            self.run_worker(self._send_ws_message(content))
        else:
            # Offline mode - use Ollama directly
            self._demo_response(content)

    async def _send_ws_message(self, content: str) -> None:
        """Send message via WebSocket."""
        try:
            from src.cli.v3.tui.services.websocket_client import get_ws_client

            client = get_ws_client()
            await client.send_chat(
                message=content, agent=self.current_agent, conversation_id=self._conversation_id
            )

            # Show streaming indicator
            chat = self.query_one("#chat-area", ChatHistory)
            self._streaming_message = StreamingMessage(agent=self.current_agent)
            chat.mount(self._streaming_message)
            chat.scroll_end()

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            self._demo_response(content)

    def _demo_response(self, user_message: str) -> None:
        """Generate response using Ollama directly."""
        # Use run_worker to call async Ollama
        self.run_worker(self._call_ollama(user_message))

    async def _call_ollama(self, user_message: str) -> None:
        """Call Ollama API directly for chat response."""
        import httpx

        chat = self.query_one("#chat-area", ChatHistory)

        # Show streaming indicator
        self._streaming_message = StreamingMessage(agent=self.current_agent)
        chat.mount(self._streaming_message)
        chat.scroll_end()

        try:
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

            # Get available models and pick a chat model (not embedding)
            async with httpx.AsyncClient(timeout=5.0) as client:
                models_resp = await client.get(f"{ollama_url}/api/tags")
                models = models_resp.json().get("models", [])

                # Filter out embedding models and pick a good chat model
                chat_models = [
                    m["name"]
                    for m in models
                    if "embed" not in m["name"].lower() and "nomic" not in m["name"].lower()
                ]

                # Prefer qwen3 or llama models
                preferred = ["qwen3.5:27b", "qwen3-coder", "llama", "mistral"]
                model = "qwen3.5:27b"  # default
                for pref in preferred:
                    for m in chat_models:
                        if pref in m.lower():
                            model = m
                            break
                    else:
                        continue
                    break

            # System prompts per agent
            system_prompts = {
                "general": "You are a helpful assistant. Be concise and clear.",
                "browser": "You are a browser automation agent. Describe web actions clearly.",
                "data": "You are a data analyst. Provide insights and analysis.",
                "coder": "You are a coding assistant. Write clean, well-documented code.",
            }

            system = system_prompts.get(self.current_agent, system_prompts["general"])

            # Stream response from Ollama
            async with (
                httpx.AsyncClient(timeout=120.0) as client,
                client.stream(
                    "POST",
                    f"{ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user_message},
                        ],
                        "stream": True,
                    },
                ) as response,
            ):
                async for line in response.aiter_lines():
                    if line:
                        import json

                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content and self._streaming_message:
                                self._streaming_message.append_content(content)
                                chat.scroll_end()
                        except json.JSONDecodeError:
                            pass

            # Finalize
            if self._streaming_message:
                final_msg = self._streaming_message.finalize()
                self._streaming_message.remove()
                chat.add_message(final_msg)
                self._streaming_message = None

        except Exception as e:
            logger.error(f"Ollama error: {e}")

            if self._streaming_message:
                self._streaming_message.remove()
                self._streaming_message = None

            chat.add_message(
                ChatMessage(
                    role="assistant", content=f"Error connecting to Ollama: {e}", agent="system"
                )
            )

    async def _on_chat_stream(self, data: dict) -> None:
        """Handle streaming chat response."""
        content = data.get("content", "")

        if self._streaming_message:
            self._streaming_message.append_content(content)

            chat = self.query_one("#chat-area", ChatHistory)
            chat.scroll_end()

    async def _on_chat_response(self, data: dict) -> None:
        """Handle complete chat response."""
        if self._streaming_message:
            # Finalize streaming message
            final_msg = self._streaming_message.finalize()

            chat = self.query_one("#chat-area", ChatHistory)

            # Remove streaming widget and add final message
            self._streaming_message.remove()
            chat.add_message(final_msg)

            self._streaming_message = None
            self._conversation_id = data.get("conversation_id")

    async def _on_task_thinking(self, data: dict) -> None:
        """Handle task thinking event (used by Manus agent)."""
        content = data.get("content", "")
        if content and self._streaming_message:
            self._streaming_message.append_content(content)
            chat = self.query_one("#chat-area", ChatHistory)
            chat.scroll_end()

    async def _on_task_progress(self, data: dict) -> None:
        """Handle task progress event."""
        message = data.get("message", "")
        step = data.get("step", 0)
        total = data.get("total_steps", 1)
        if message:
            logger.debug(f"Task progress: {step}/{total} - {message}")

    async def _on_task_completed(self, data: dict) -> None:
        """Handle task completed event."""
        if self._streaming_message:
            final_msg = self._streaming_message.finalize()
            chat = self.query_one("#chat-area", ChatHistory)
            self._streaming_message.remove()
            chat.add_message(final_msg)
            self._streaming_message = None

        duration = data.get("duration_seconds", 0)
        self.app.notify(f"[green]Task completed in {duration:.1f}s[/]", timeout=2)

    async def _on_task_error(self, data: dict) -> None:
        """Handle task error event."""
        error = data.get("error", "Unknown error")

        if self._streaming_message:
            self._streaming_message.remove()
            self._streaming_message = None

        chat = self.query_one("#chat-area", ChatHistory)
        chat.add_message(ChatMessage(role="assistant", content=f"Error: {error}", agent="system"))
        self.app.notify(f"[red]Error: {error}[/]", timeout=5)

    def action_focus_input(self) -> None:
        """Focus the input field."""
        self.query_one("#chat-input", Input).focus()

    def action_clear_chat(self) -> None:
        """Clear chat history."""
        chat = self.query_one("#chat-area", ChatHistory)
        chat.clear_messages()
        self._add_welcome_message()
        self.app.notify("Chat cleared", timeout=1)

    def action_new_chat(self) -> None:
        """Start a new conversation."""
        self._conversation_id = None
        self.action_clear_chat()
        self.app.notify("New conversation", timeout=1)

    def action_cycle_agent(self) -> None:
        """Cycle through available agents."""
        agent_values = [a[0] for a in self.AGENTS]
        current_idx = agent_values.index(self.current_agent)
        next_idx = (current_idx + 1) % len(agent_values)
        self.current_agent = agent_values[next_idx]

        # Update selector
        selector = self.query_one("#agent-selector", Select)
        selector.value = self.current_agent

        self.app.notify(f"Agent: {self.current_agent}", timeout=1)
