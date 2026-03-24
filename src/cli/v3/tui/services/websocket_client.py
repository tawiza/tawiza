"""WebSocket client for TUI communication with the agent server."""

import asyncio
import contextlib
import json
from collections.abc import Callable
from enum import Enum
from typing import Any

from loguru import logger

try:
    import websockets
    from websockets.client import WebSocketClientProtocol

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    WebSocketClientProtocol = None


class ConnectionState(Enum):
    """WebSocket connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class WSClient:
    """WebSocket client for TUI-Server communication."""

    def __init__(
        self,
        url: str = "ws://localhost:8765/ws",
        reconnect_interval: float = 5.0,
        max_reconnect_attempts: int = 10,
    ):
        self.url = url
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts

        self._ws: WebSocketClientProtocol | None = None
        self._state = ConnectionState.DISCONNECTED
        self._handlers: dict[str, list[Callable]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._reconnect_attempts = 0
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Callbacks for state changes
        self._on_connect: Callable | None = None
        self._on_disconnect: Callable | None = None
        self._on_error: Callable | None = None

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Whether currently connected."""
        return self._state == ConnectionState.CONNECTED

    def on_connect(self, callback: Callable) -> None:
        """Set callback for connection established."""
        self._on_connect = callback

    def on_disconnect(self, callback: Callable) -> None:
        """Set callback for disconnection."""
        self._on_disconnect = callback

    def on_error(self, callback: Callable) -> None:
        """Set callback for errors."""
        self._on_error = callback

    def on_message(self, message_type: str, handler: Callable) -> None:
        """Register a handler for a specific message type."""
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)

    def on_any_message(self, handler: Callable) -> None:
        """Register a handler for all messages."""
        self.on_message("*", handler)

    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        if not HAS_WEBSOCKETS:
            logger.error("websockets package not installed")
            self._state = ConnectionState.ERROR
            return False

        self._state = ConnectionState.CONNECTING
        self._running = True

        try:
            self._ws = await websockets.connect(self.url, ping_interval=30, ping_timeout=10)
            self._state = ConnectionState.CONNECTED
            self._reconnect_attempts = 0

            logger.info(f"Connected to {self.url}")

            if self._on_connect:
                await self._call_handler(self._on_connect)

            # Start receive loop
            self._tasks.append(asyncio.create_task(self._receive_loop()))
            # Start send loop
            self._tasks.append(asyncio.create_task(self._send_loop()))

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._state = ConnectionState.ERROR

            if self._on_error:
                await self._call_handler(self._on_error, str(e))

            return False

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        self._running = False
        self._state = ConnectionState.DISCONNECTED

        # Cancel tasks
        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

        # Close WebSocket
        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

        logger.info("Disconnected from WebSocket server")

        if self._on_disconnect:
            await self._call_handler(self._on_disconnect)

    async def send(self, message: dict[str, Any]) -> bool:
        """Queue a message to be sent."""
        if not self.is_connected:
            logger.warning("Cannot send: not connected")
            return False

        await self._message_queue.put(message)
        return True

    async def send_immediate(self, message: dict[str, Any]) -> bool:
        """Send a message immediately (bypass queue)."""
        if not self.is_connected or not self._ws:
            return False

        try:
            await self._ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return False

    async def _receive_loop(self) -> None:
        """Continuously receive messages from the server."""
        while self._running and self._ws:
            try:
                raw_data = await self._ws.recv()
                await self._handle_message(raw_data)

            except websockets.ConnectionClosed:
                logger.warning("Connection closed by server")
                await self._handle_disconnect()
                break

            except Exception as e:
                logger.error(f"Receive error: {e}")
                if self._on_error:
                    await self._call_handler(self._on_error, str(e))

    async def _send_loop(self) -> None:
        """Continuously send queued messages."""
        while self._running and self._ws:
            try:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                await self._ws.send(json.dumps(message))

            except TimeoutError:
                continue

            except websockets.ConnectionClosed:
                break

            except Exception as e:
                logger.error(f"Send error: {e}")

    async def _handle_message(self, raw_data: str) -> None:
        """Parse and dispatch a received message."""
        try:
            data = json.loads(raw_data)
            message_type = data.get("type", "unknown")

            # Call type-specific handlers
            handlers = self._handlers.get(message_type, [])
            for handler in handlers:
                await self._call_handler(handler, data)

            # Call catch-all handlers
            all_handlers = self._handlers.get("*", [])
            for handler in all_handlers:
                await self._call_handler(handler, data)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")

    async def _handle_disconnect(self) -> None:
        """Handle disconnection and attempt reconnect."""
        self._state = ConnectionState.DISCONNECTED

        if self._on_disconnect:
            await self._call_handler(self._on_disconnect)

        if self._running:
            await self._reconnect()

    async def _reconnect(self) -> None:
        """Attempt to reconnect to the server."""
        while self._running and self._reconnect_attempts < self.max_reconnect_attempts:
            self._state = ConnectionState.RECONNECTING
            self._reconnect_attempts += 1

            logger.info(
                f"Reconnecting ({self._reconnect_attempts}/{self.max_reconnect_attempts})..."
            )

            await asyncio.sleep(self.reconnect_interval)

            if await self.connect():
                return

        logger.error("Max reconnection attempts reached")
        self._state = ConnectionState.ERROR

    async def _call_handler(self, handler: Callable, *args, **kwargs) -> None:
        """Safely call a handler (sync or async)."""
        try:
            result = handler(*args, **kwargs)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Handler error: {e}")


# ============================================================================
# Convenience functions for common operations
# ============================================================================


class TUIWebSocketClient(WSClient):
    """Extended client with TUI-specific methods."""

    async def create_task(self, agent: str, prompt: str, context: dict | None = None) -> bool:
        """Create a new task."""
        return await self.send(
            {"type": "task.create", "agent": agent, "prompt": prompt, "context": context or {}}
        )

    async def pause_task(self, task_id: str) -> bool:
        """Pause a running task."""
        return await self.send({"type": "task.pause", "task_id": task_id})

    async def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        return await self.send({"type": "task.resume", "task_id": task_id})

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        return await self.send({"type": "task.cancel", "task_id": task_id})

    async def send_correction(self, task_id: str, message: str) -> bool:
        """Send a correction to a running task."""
        return await self.send({"type": "task.correct", "task_id": task_id, "message": message})

    async def send_chat(
        self, message: str, agent: str = "general", conversation_id: str | None = None
    ) -> bool:
        """Send a chat message."""
        return await self.send(
            {
                "type": "chat.message",
                "agent": agent,
                "message": message,
                "conversation_id": conversation_id,
            }
        )

    async def ping(self) -> bool:
        """Send a ping to check connection."""
        return await self.send({"type": "ping"})


# Global client instance
_client: TUIWebSocketClient | None = None

# Default WebSocket URL - uses API port 8000
DEFAULT_WS_URL = "ws://localhost:8000/ws"


def get_ws_client(url: str = DEFAULT_WS_URL) -> TUIWebSocketClient:
    """Get or create the global WebSocket client."""
    global _client
    if _client is None:
        _client = TUIWebSocketClient(url=url)
    return _client


async def connect_to_server(url: str = DEFAULT_WS_URL) -> bool:
    """Connect to the WebSocket server."""
    client = get_ws_client(url)
    return await client.connect()


async def disconnect_from_server() -> None:
    """Disconnect from the WebSocket server."""
    global _client
    if _client:
        await _client.disconnect()
        _client = None
