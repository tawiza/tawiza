"""WebSocket server for TUI communication."""

import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from typing import Any

import psutil
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from loguru import logger

from src.interfaces.api.routers.progress import get_progress_tracker
from src.interfaces.api.websocket.models import (
    ErrorMessage,
    MessageType,
    MetricsMessage,
    PongMessage,
    WSMessage,
    parse_message,
)


class WebSocketManager:
    """Manages WebSocket connections and message routing."""

    def __init__(self):
        # Map session_id -> set of WebSockets
        self._sessions: dict[str, set[WebSocket]] = {}
        # Global connections for system-wide broadcasts (like metrics)
        self._all_connections: set[WebSocket] = set()
        self._handlers: dict[MessageType, list[Callable]] = {}
        self._metrics_task: asyncio.Task | None = None
        self._running = False

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self._all_connections)

    async def connect(self, websocket: WebSocket, session_id: str | None = None) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._all_connections.add(websocket)

        if session_id:
            if session_id not in self._sessions:
                self._sessions[session_id] = set()
            self._sessions[session_id].add(websocket)
            logger.info(
                f"WebSocket connected to session {session_id}. Total: {self.connection_count}"
            )
        else:
            logger.info(f"WebSocket connected (no session). Total: {self.connection_count}")

    def disconnect(self, websocket: WebSocket, session_id: str | None = None) -> None:
        """Remove a WebSocket connection."""
        self._all_connections.discard(websocket)
        if session_id and session_id in self._sessions:
            self._sessions[session_id].discard(websocket)
            if not self._sessions[session_id]:
                del self._sessions[session_id]

        # Also search in all sessions if session_id is not provided
        if not session_id:
            for sid in list(self._sessions.keys()):
                self._sessions[sid].discard(websocket)
                if not self._sessions[sid]:
                    del self._sessions[sid]

        logger.info(f"WebSocket disconnected. Total: {self.connection_count}")

    async def broadcast(self, message: WSMessage, session_id: str | None = None) -> None:
        """Send a message to connected clients.

        If session_id is provided, sends only to clients in that session.
        Otherwise, sends to everyone.
        """
        target_connections = self._all_connections
        if session_id or message.session_id:
            sid = session_id or message.session_id
            target_connections = self._sessions.get(sid, set())

        if not target_connections:
            return

        data = message.model_dump_json()
        disconnected = set()

        # Copy the set to avoid "Set changed size during iteration" errors
        for ws in list(target_connections):
            try:
                await ws.send_text(data)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.add(ws)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws, session_id)

    async def send_to(self, websocket: WebSocket, message: WSMessage) -> bool:
        """Send a message to a specific client."""
        try:
            await websocket.send_text(message.model_dump_json())
            return True
        except Exception as e:
            logger.warning(f"Failed to send message: {e}")
            return False

    def register_handler(
        self, message_type: MessageType, handler: Callable[[WSMessage, WebSocket], Any]
    ) -> None:
        """Register a handler for a specific message type."""
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)
        logger.debug(f"Registered handler for {message_type}")

    async def handle_message(self, websocket: WebSocket, raw_data: str) -> WSMessage | None:
        """Parse and handle an incoming message."""
        try:
            data = json.loads(raw_data)
            message = parse_message(data)

            # Handle ping/pong
            if message.type == MessageType.PING:
                await self.send_to(websocket, PongMessage())
                return message

            # Call registered handlers
            handlers = self._handlers.get(message.type, [])
            for handler in handlers:
                try:
                    result = handler(message, websocket)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Handler error for {message.type}: {e}")
                    await self.send_to(websocket, ErrorMessage(error=str(e), code="HANDLER_ERROR"))

            return message

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            await self.send_to(websocket, ErrorMessage(error="Invalid JSON", code="PARSE_ERROR"))
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await self.send_to(websocket, ErrorMessage(error=str(e), code="UNKNOWN_ERROR"))

        return None

    async def start_metrics_broadcast(self, interval: float = 5.0) -> None:
        """Start periodic metrics broadcasting."""
        self._running = True

        async def broadcast_metrics():
            while self._running:
                if self._all_connections:
                    try:
                        # Get active tasks from progress tracker
                        tracker = get_progress_tracker()
                        active_task_ids = await tracker.get_active_tasks()

                        metrics = MetricsMessage(
                            cpu_percent=psutil.cpu_percent(interval=0),
                            ram_percent=psutil.virtual_memory().percent,
                            gpu_percent=await self._get_gpu_percent(),
                            disk_percent=psutil.disk_usage("/").percent,
                            active_tasks=len(active_task_ids),
                        )
                        await self.broadcast(metrics)
                    except Exception as e:
                        logger.error(f"Metrics broadcast error: {e}")

                await asyncio.sleep(interval)

        self._metrics_task = asyncio.create_task(broadcast_metrics())
        logger.info(f"Started metrics broadcast (interval: {interval}s)")

    async def stop_metrics_broadcast(self) -> None:
        """Stop the metrics broadcast task."""
        self._running = False
        if self._metrics_task:
            self._metrics_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._metrics_task
            self._metrics_task = None
        logger.info("Stopped metrics broadcast")

    async def _get_gpu_percent(self) -> float:
        """Get GPU usage percentage."""
        try:
            import subprocess

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["rocm-smi", "--showuse", "--json"], capture_output=True, text=True, timeout=2
                ),
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if "card0" in data:
                    return float(data["card0"].get("GPU use (%)", 0))
        except Exception:
            pass
        return 0.0


# Global manager instance
_manager: WebSocketManager | None = None


def get_ws_manager() -> WebSocketManager:
    """Get or create the global WebSocket manager."""
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager


# ============================================================================
# FastAPI Integration
# ============================================================================


def setup_websocket_routes(app: FastAPI) -> WebSocketManager:
    """Setup WebSocket routes on a FastAPI app."""
    manager = get_ws_manager()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, session_id: str | None = Query(None)):
        origin = websocket.headers.get("origin")
        logger.info(f"WS connect attempt: origin={origin}, session={session_id}")
        await manager.connect(websocket, session_id)
        try:
            while True:
                data = await websocket.receive_text()
                await manager.handle_message(websocket, data)
        except WebSocketDisconnect:
            manager.disconnect(websocket, session_id)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            manager.disconnect(websocket, session_id)

    @app.on_event("startup")
    async def start_metrics():
        await manager.start_metrics_broadcast(interval=5.0)

    @app.on_event("shutdown")
    async def stop_metrics():
        await manager.stop_metrics_broadcast()

    logger.info("WebSocket routes configured on /ws")
    return manager


# ============================================================================
# Standalone Server (for testing)
# ============================================================================


def create_ws_app() -> FastAPI:
    """Create a standalone FastAPI app with WebSocket support."""
    app = FastAPI(
        title="Tawiza WebSocket Server",
        description="WebSocket server for TUI communication",
        version="1.0.0",
    )

    setup_websocket_routes(app)

    @app.get("/health")
    async def health():
        manager = get_ws_manager()
        return {
            "status": "ok",
            "connections": manager.connection_count,
            "timestamp": datetime.now().isoformat(),
        }

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_ws_app()
    uvicorn.run(app, host="0.0.0.0", port=8765)
