"""WebSocket message handlers with AgentOrchestrator integration.

This module connects the WebSocket server to the AgentOrchestrator,
translating TaskEvents to WebSocket messages for real-time TUI updates.
"""

import asyncio
from typing import Any

from fastapi import WebSocket
from loguru import logger

from src.application.services.agent_orchestrator import (
    TaskEvent,
    TaskEventType,
    get_agent_orchestrator,
)
from src.interfaces.api.websocket.models import (
    AgentsStatusMessage,
    BrowserActionMessage,
    # Browser messages
    BrowserScreenshotMessage,
    BrowserStatusMessage,
    ChatMessage,
    ChatResponseMessage,
    ChatStreamMessage,
    MessageType,
    TAJINEDelegateMessage,
    TAJINELearnMessage,
    # TAJINE messages
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
    TaskThinkingMessage,
    TerminalOutputMessage,
    WSMessage,
)
from src.interfaces.api.websocket.server import WebSocketManager, get_ws_manager


class TaskHandler:
    """Handles task-related WebSocket messages via AgentOrchestrator."""

    def __init__(self, manager: WebSocketManager):
        self.manager = manager
        self._tasks: dict[str, dict[str, Any]] = {}
        self._task_futures: dict[str, asyncio.Task] = {}
        self._orchestrator = get_agent_orchestrator()
        self._register_handlers()

    def _register_handlers(self):
        """Register all task handlers."""
        self.manager.register_handler(
            MessageType.TASK_CREATE,
            self.handle_create
        )
        self.manager.register_handler(
            MessageType.TASK_PAUSE,
            self.handle_pause
        )
        self.manager.register_handler(
            MessageType.TASK_RESUME,
            self.handle_resume
        )
        self.manager.register_handler(
            MessageType.TASK_CANCEL,
            self.handle_cancel
        )
        self.manager.register_handler(
            MessageType.TASK_CORRECT,
            self.handle_correct
        )

    async def handle_create(
        self,
        message: TaskCreateMessage,
        websocket: WebSocket
    ) -> None:
        """Handle task creation request."""
        import uuid
        task_id = str(uuid.uuid4())[:8]

        logger.info(f"Creating task {task_id}: {message.prompt[:50]}...")

        # Store task info
        self._tasks[task_id] = {
            "id": task_id,
            "agent": message.agent,
            "prompt": message.prompt,
            "status": TaskStatus.PENDING,
            "websocket": websocket,
            "context": getattr(message, 'context', {}) or {},
            "result": None,
        }

        # Send confirmation
        await self.manager.send_to(
            websocket,
            TaskCreatedMessage(
                task_id=task_id,
                agent=message.agent,
                prompt=message.prompt,
                status=TaskStatus.PENDING
            )
        )

        # Start task execution via AgentOrchestrator
        future = asyncio.create_task(self._execute_task(task_id))
        self._task_futures[task_id] = future

    async def _execute_task(self, task_id: str) -> None:
        """Execute a task using AgentOrchestrator."""
        task = self._tasks.get(task_id)
        if not task:
            return

        task["status"] = TaskStatus.RUNNING
        agent_type = task["agent"]
        prompt = task["prompt"]
        context = task.get("context", {})

        try:
            # Execute via AgentOrchestrator and handle events
            async for event in self._orchestrator.execute_task(
                task_id=task_id,
                agent_type=agent_type,
                prompt=prompt,
                context=context,
            ):
                await self._handle_task_event(task_id, event)

        except asyncio.CancelledError:
            task["status"] = TaskStatus.CANCELLED
            logger.info(f"Task {task_id} cancelled")
            await self.manager.broadcast(
                TaskErrorMessage(task_id=task_id, error="Task cancelled")
            )
        except Exception as e:
            task["status"] = TaskStatus.FAILED
            logger.error(f"Task {task_id} failed: {e}")
            await self.manager.broadcast(
                TaskErrorMessage(task_id=task_id, error=str(e))
            )
        finally:
            # Clean up future reference
            self._task_futures.pop(task_id, None)

    async def _handle_task_event(self, task_id: str, event: TaskEvent) -> None:
        """Convert TaskEvent to WebSocket message and broadcast."""
        task = self._tasks.get(task_id)
        if not task:
            return

        event_type = event.type

        if event_type == TaskEventType.STARTED:
            task["status"] = TaskStatus.RUNNING
            await self.manager.broadcast(
                TaskThinkingMessage(
                    task_id=task_id,
                    content=f"Starting {event.data.get('agent', 'agent')}..."
                )
            )

        elif event_type == TaskEventType.THINKING:
            await self.manager.broadcast(
                TaskThinkingMessage(
                    task_id=task_id,
                    content=event.data.get("content", "")
                )
            )

        elif event_type == TaskEventType.PROGRESS:
            step = event.data.get("step", 0)
            total = event.data.get("total_steps", 1)
            message = event.data.get("message", "")
            await self.manager.broadcast(
                TaskProgressMessage(
                    task_id=task_id,
                    step=step,
                    total_steps=total,
                    message=message,
                    percent=(step / total) * 100 if total > 0 else 0
                )
            )

        elif event_type == TaskEventType.STREAMING:
            # For streaming, we can either use ChatStreamMessage or TaskThinkingMessage
            content = event.data.get("content", "")
            if content:
                await self.manager.broadcast(
                    TaskThinkingMessage(
                        task_id=task_id,
                        content=content
                    )
                )

        elif event_type == TaskEventType.TERMINAL_OUTPUT:
            await self.manager.broadcast(
                TerminalOutputMessage(
                    task_id=task_id,
                    content=event.data.get("content", ""),
                    stream=event.data.get("stream", "stdout"),
                    session_id=task.get("session_id")
                ),
                session_id=task.get("session_id")
            )

        elif event_type == TaskEventType.TOOL_CALL:
            tool_name = event.data.get("tool_name", "unknown")
            await self.manager.broadcast(
                TaskThinkingMessage(
                    task_id=task_id,
                    content=f"Using tool: {tool_name}"
                )
            )

        elif event_type == TaskEventType.TOOL_RESULT:
            result = event.data.get("result", "")
            await self.manager.broadcast(
                TaskThinkingMessage(
                    task_id=task_id,
                    content=f"Tool result: {str(result)[:200]}"
                )
            )

        elif event_type == TaskEventType.COMPLETED:
            task["status"] = TaskStatus.COMPLETED
            duration = event.data.get("duration_seconds", 0)
            result = task.get("result", "Task completed successfully")

            # Get the full response from thinking events if available
            await self.manager.broadcast(
                TaskCompletedMessage(
                    task_id=task_id,
                    result=result if isinstance(result, str) else str(result),
                    duration_seconds=duration
                )
            )

        elif event_type == TaskEventType.ERROR:
            task["status"] = TaskStatus.FAILED
            error = event.data.get("error", "Unknown error")
            await self.manager.broadcast(
                TaskErrorMessage(task_id=task_id, error=error)
            )

    async def handle_pause(
        self,
        message: TaskPauseMessage,
        websocket: WebSocket
    ) -> None:
        """Handle task pause request."""
        task = self._tasks.get(message.task_id)
        if task:
            task["status"] = TaskStatus.PAUSED
            logger.info(f"Task {message.task_id} paused")
            # Note: actual pause requires task to check status periodically

    async def handle_resume(
        self,
        message: TaskResumeMessage,
        websocket: WebSocket
    ) -> None:
        """Handle task resume request."""
        task = self._tasks.get(message.task_id)
        if task:
            task["status"] = TaskStatus.RUNNING
            logger.info(f"Task {message.task_id} resumed")

    async def handle_cancel(
        self,
        message: TaskCancelMessage,
        websocket: WebSocket
    ) -> None:
        """Handle task cancel request."""
        task = self._tasks.get(message.task_id)
        if task:
            task["status"] = TaskStatus.CANCELLED
            # Cancel the running future if exists
            future = self._task_futures.get(message.task_id)
            if future and not future.done():
                future.cancel()
            logger.info(f"Task {message.task_id} cancelled")

    async def handle_correct(
        self,
        message: TaskCorrectMessage,
        websocket: WebSocket
    ) -> None:
        """Handle task correction/guidance."""
        task = self._tasks.get(message.task_id)
        if task:
            logger.info(f"Correction for {message.task_id}: {message.message}")
            # Store correction in task context for agent to use
            task["context"]["user_correction"] = message.message
            await self.manager.broadcast(
                TaskThinkingMessage(
                    task_id=message.task_id,
                    content=f"User correction received: {message.message}"
                )
            )


class ChatHandler:
    """Handles chat-related WebSocket messages via AgentOrchestrator."""

    def __init__(self, manager: WebSocketManager):
        self.manager = manager
        self._conversations: dict[str, list] = {}
        self._orchestrator = get_agent_orchestrator()
        self._register_handlers()

    def _register_handlers(self):
        """Register chat handlers."""
        self.manager.register_handler(
            MessageType.CHAT_MESSAGE,
            self.handle_message
        )

    async def handle_message(
        self,
        message: ChatMessage,
        websocket: WebSocket
    ) -> None:
        """Handle incoming chat message using AgentOrchestrator streaming."""
        import uuid

        conversation_id = message.conversation_id or str(uuid.uuid4())[:8]
        logger.info(f"Chat message in {conversation_id}: {message.message[:50]}...")

        # Get or create conversation history
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

        # Add user message to history
        self._conversations[conversation_id].append({
            "role": "user",
            "content": message.message
        })

        full_response = ""
        task_id = f"chat-{conversation_id}-{uuid.uuid4().hex[:4]}"

        try:
            # Execute via AgentOrchestrator
            async for event in self._orchestrator.execute_task(
                task_id=task_id,
                agent_type=message.agent,
                prompt=message.message,
                context={
                    "conversation_history": self._conversations[conversation_id][-10:],
                    "conversation_id": conversation_id,
                }
            ):
                # Handle streaming and thinking events
                if event.type == TaskEventType.STREAMING:
                    content = event.data.get("content", "")
                    if content:
                        full_response = event.data.get("full_content", full_response + content)
                        await self.manager.send_to(
                            websocket,
                            ChatStreamMessage(
                                content=content,
                                conversation_id=conversation_id,
                                done=False
                            )
                        )

                elif event.type == TaskEventType.THINKING:
                    content = event.data.get("content", "")
                    if content and not full_response:
                        full_response = content

                elif event.type == TaskEventType.COMPLETED:
                    # Send done signal
                    await self.manager.send_to(
                        websocket,
                        ChatStreamMessage(
                            content="",
                            conversation_id=conversation_id,
                            done=True
                        )
                    )

                elif event.type == TaskEventType.ERROR:
                    full_response = f"Error: {event.data.get('error', 'Unknown error')}"

            # Store assistant response
            if full_response:
                self._conversations[conversation_id].append({
                    "role": "assistant",
                    "content": full_response
                })

            # Send complete response
            await self.manager.send_to(
                websocket,
                ChatResponseMessage(
                    content=full_response,
                    agent=message.agent,
                    conversation_id=conversation_id
                )
            )

        except Exception as e:
            logger.error(f"Chat error: {e}")
            await self.manager.send_to(
                websocket,
                ChatResponseMessage(
                    content=f"Error: {str(e)}",
                    agent="system",
                    conversation_id=conversation_id
                )
            )


class AgentStatusHandler:
    """Handles agent status queries."""

    def __init__(self, manager: WebSocketManager):
        self.manager = manager
        self._orchestrator = get_agent_orchestrator()
        self._register_handlers()

    def _register_handlers(self):
        """Register status handlers."""
        self.manager.register_handler(
            MessageType.AGENTS_STATUS,
            self.handle_status_request
        )

    async def handle_status_request(
        self,
        message: WSMessage,
        websocket: WebSocket
    ) -> None:
        """Handle agent status request."""
        agents = self._orchestrator.list_tui_agents()
        await self.manager.send_to(
            websocket,
            AgentsStatusMessage(agents=agents)
        )


class TAJINEHandler:
    """
    Bridges TAJINE EventEmitter to WebSocket.

    Translates TAJINECallback events to WebSocket messages for
    real-time PPDSL cycle visualization in the TUI.
    """

    # Map TAJINE event types to WebSocket message classes
    EVENT_MAP = {
        'tajine.perceive.start': ('perceive', 'start'),
        'tajine.perceive.complete': ('perceive', 'complete'),
        'tajine.plan.start': ('plan', 'start'),
        'tajine.plan.complete': ('plan', 'complete'),
        'tajine.delegate.start': ('delegate', 'start'),
        'tajine.delegate.tool': ('delegate', 'tool'),
        'tajine.delegate.complete': ('delegate', 'complete'),
        'tajine.synthesize.start': ('synthesize', 'start'),
        'tajine.synthesize.level': ('synthesize', 'level'),
        'tajine.synthesize.complete': ('synthesize', 'complete'),
        'tajine.learn.start': ('learn', 'start'),
        'tajine.learn.complete': ('learn', 'complete'),
        'tajine.progress': ('progress', 'update'),
        'tajine.thinking': ('thinking', 'update'),
    }

    def __init__(self, manager: WebSocketManager):
        self.manager = manager
        self._agents: dict[str, Any] = {}  # task_id -> TAJINEAgent
        logger.info("TAJINEHandler initialized")

    def register_agent(self, task_id: str, agent: Any) -> None:
        """
        Register a TAJINE agent for WebSocket streaming.

        Args:
            task_id: Unique task identifier
            agent: TAJINEAgent instance with EventEmitter
        """
        self._agents[task_id] = agent

        # Register WebSocket handler on the agent's EventEmitter
        async def ws_handler(event_data: dict[str, Any]):
            await self._handle_tajine_event(task_id, event_data)

        agent.on_ws(ws_handler)
        logger.info(f"Registered TAJINE agent for task {task_id}")

    def unregister_agent(self, task_id: str) -> None:
        """Unregister a TAJINE agent."""
        self._agents.pop(task_id, None)

    async def _handle_tajine_event(
        self,
        task_id: str,
        event_data: dict[str, Any]
    ) -> None:
        """Convert TAJINE event to WebSocket message and broadcast."""
        event_type = event_data.get('type', '')
        session_id = event_data.get('session_id')
        phase = event_data.get('phase', '')
        progress = event_data.get('progress', 0)
        message = event_data.get('message', '')
        data = event_data.get('data', {})

        # ... (skip for readability, no changes in message creation)

        # Create appropriate message based on phase
        if phase == 'perceive':
            ws_message = TAJINEPerceiveMessage(
                task_id=task_id,
                session_id=session_id,
                status='complete' if 'complete' in event_type else 'start',
                progress=progress,
                message=message,
                data=data
            )
        elif phase == 'plan':
            ws_message = TAJINEPlanMessage(
                task_id=task_id,
                session_id=session_id,
                status='complete' if 'complete' in event_type else 'start',
                progress=progress,
                message=message,
                data=data,
                subtasks=data.get('subtasks', [])
            )
        elif phase == 'delegate':
            ws_message = TAJINEDelegateMessage(
                task_id=task_id,
                session_id=session_id,
                status='complete' if 'complete' in event_type else 'start',
                progress=progress,
                message=message,
                data=data,
                tool=data.get('tool'),
                subtask_index=data.get('subtask_index', 0),
                total_subtasks=data.get('total_subtasks', 0)
            )
        elif phase == 'synthesize':
            ws_message = TAJINESynthesizeMessage(
                task_id=task_id,
                session_id=session_id,
                status='complete' if 'complete' in event_type else 'start',
                progress=progress,
                message=message,
                data=data,
                level=data.get('level', 0)
            )
        elif phase == 'learn':
            ws_message = TAJINELearnMessage(
                task_id=task_id,
                session_id=session_id,
                status='complete' if 'complete' in event_type else 'start',
                progress=progress,
                message=message,
                data=data,
                trust_delta=data.get('trust_delta', 0.0)
            )
        elif 'thinking' in event_type:
            ws_message = TAJINEThinkingMessage(
                task_id=task_id,
                session_id=session_id,
                content=message
            )
        else:
            # Generic progress message
            ws_message = TAJINEProgressMessage(
                task_id=task_id,
                session_id=session_id,
                phase=phase,
                progress=progress,
                message=message,
                data=data
            )

        # Broadcast to session-specific connected clients
        await self.manager.broadcast(ws_message, session_id=session_id)


class BrowserHandler:
    """
    Handles browser automation WebSocket messages.

    Bridges UnifiedBrowserAgent to WebSocket for real-time
    screenshot streaming to the Agent Live panel.
    """

    def __init__(self, manager: WebSocketManager):
        self.manager = manager
        self._browser_agents: dict[str, Any] = {}  # task_id -> UnifiedBrowserAgent
        logger.info("BrowserHandler initialized")

    def create_screenshot_callback(self, task_id: str, session_id: str | None = None):
        """
        Create a callback for streaming screenshots to WebSocket.

        Returns a sync function that can be passed to UnifiedBrowserAgent.
        """
        def callback(action: str, screenshot_b64: str, url: str | None = None):
            # Schedule async broadcast in the event loop
            logger.debug(f"Screenshot callback: task={task_id}, action={action}, url={url}")
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._broadcast_screenshot(task_id, action, screenshot_b64, url, session_id))
            except RuntimeError:
                # No running event loop, try with asyncio.run
                logger.warning("No event loop for screenshot broadcast, using asyncio.run")
                asyncio.run(self._broadcast_screenshot(task_id, action, screenshot_b64, url, session_id))

        return callback

    async def _broadcast_screenshot(
        self,
        task_id: str,
        action: str,
        screenshot_b64: str,
        url: str | None = None,
        session_id: str | None = None
    ) -> None:
        """Broadcast screenshot to session-specific connected clients."""
        agent = self._browser_agents.get(task_id)
        current_url = url or (agent.current_url if agent else None)

        await self.manager.broadcast(
            BrowserScreenshotMessage(
                task_id=task_id,
                session_id=session_id,
                action=action,
                screenshot_b64=screenshot_b64,
                url=current_url,
            ),
            session_id=session_id
        )

    async def broadcast_action(
        self,
        task_id: str,
        action: str,
        selector: str | None = None,
        value: str | None = None,
        success: bool = True,
        error: str | None = None,
        duration_ms: int = 0
    ) -> None:
        """Broadcast browser action to all connected clients."""
        await self.manager.broadcast(
            BrowserActionMessage(
                task_id=task_id,
                action=action,
                selector=selector,
                value=value,
                success=success,
                error=error,
                duration_ms=duration_ms
            )
        )

    async def broadcast_status(
        self,
        task_id: str,
        is_running: bool,
        current_url: str | None = None,
        page_title: str | None = None
    ) -> None:
        """Broadcast browser status to all connected clients."""
        await self.manager.broadcast(
            BrowserStatusMessage(
                task_id=task_id,
                is_running=is_running,
                current_url=current_url,
                page_title=page_title
            )
        )

    def register_agent(self, task_id: str, agent: Any) -> None:
        """Register a browser agent for WebSocket streaming."""
        self._browser_agents[task_id] = agent
        logger.info(f"Registered browser agent for task {task_id}")

    def unregister_agent(self, task_id: str) -> None:
        """Unregister a browser agent."""
        self._browser_agents.pop(task_id, None)
        logger.info(f"Unregistered browser agent for task {task_id}")

    def get_agent(self, task_id: str) -> Any | None:
        """Get registered browser agent."""
        return self._browser_agents.get(task_id)


# Global handlers
_tajine_handler: TAJINEHandler | None = None
_browser_handler: BrowserHandler | None = None


def get_tajine_handler() -> TAJINEHandler:
    """Get or create the global TAJINE handler."""
    global _tajine_handler
    if _tajine_handler is None:
        _tajine_handler = TAJINEHandler(get_ws_manager())
    return _tajine_handler


def get_browser_handler() -> BrowserHandler:
    """Get or create the global browser handler."""
    global _browser_handler
    if _browser_handler is None:
        _browser_handler = BrowserHandler(get_ws_manager())
    return _browser_handler


def setup_handlers(manager: WebSocketManager | None = None) -> None:
    """Setup all message handlers."""
    global _tajine_handler, _browser_handler

    if manager is None:
        manager = get_ws_manager()

    TaskHandler(manager)
    ChatHandler(manager)
    AgentStatusHandler(manager)
    _tajine_handler = TAJINEHandler(manager)
    _browser_handler = BrowserHandler(manager)

    logger.info("WebSocket handlers configured with AgentOrchestrator, TAJINE, and Browser")
