"""Agent API routes."""

import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from src.infrastructure.agents.openmanus import OpenManusAdapter
from src.infrastructure.agents.skyvern import SkyvernAdapter
from src.interfaces.api.v1.agents.schemas import (
    AgentTaskCreate,
    AgentTaskList,
    AgentTaskResponse,
    AgentTaskResult,
    AgentType,
    TaskStatus,
)

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])

# Agent instances (singleton pattern)
_agents = {}


def get_agent(agent_type: AgentType):
    """Get or create agent instance."""
    if agent_type not in _agents:
        if agent_type == AgentType.OPENMANUS:
            _agents[agent_type] = OpenManusAdapter()
        elif agent_type == AgentType.SKYVERN:
            _agents[agent_type] = SkyvernAdapter()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown agent type: {agent_type}")

    return _agents[agent_type]


@router.post("/tasks", response_model=AgentTaskResponse, status_code=202)
async def create_task(
    task: AgentTaskCreate,
    background_tasks: BackgroundTasks
):
    """Create and execute agent task.

    This endpoint creates a task and executes it in the background.
    Use the task_id to check status and get results.

    **Example:**
    ```json
    {
        "agent_type": "openmanus",
        "url": "https://example.com",
        "action": "extract",
        "data": {
            "target": "main content"
        }
    }
    ```
    """
    logger.info(f"Creating task for {task.agent_type}: {task.action}")

    try:
        agent = get_agent(task.agent_type)

        # Convert task to dict
        task_config = {
            "url": str(task.url),
            "action": task.action.value,
            "selectors": task.selectors,
            "data": task.data,
            "options": task.options
        }

        # Create task (this generates task_id)
        task_id = agent._create_task(task_config)

        # Execute in background
        background_tasks.add_task(
            agent.execute_task,
            task_config
        )

        # Get initial status
        status = await agent.get_task_status(task_id)

        return AgentTaskResponse(
            task_id=status["task_id"],
            agent_type=task.agent_type,
            status=TaskStatus(status["status"]),
            progress=status["progress"],
            current_step=status["current_step"],
            created_at=status["created_at"],
            updated_at=status["updated_at"]
        )

    except Exception as e:
        logger.error(f"Failed to create task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}", response_model=AgentTaskResponse)
async def get_task_status(
    task_id: str,
    agent_type: AgentType = Query(default=AgentType.OPENMANUS)
):
    """Get task status.

    Returns current status and progress of a task.
    """
    try:
        agent = get_agent(agent_type)
        status = await agent.get_task_status(task_id)

        return AgentTaskResponse(
            task_id=status["task_id"],
            agent_type=agent_type,
            status=TaskStatus(status["status"]),
            progress=status["progress"],
            current_step=status["current_step"],
            created_at=status["created_at"],
            updated_at=status["updated_at"]
        )

    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/tasks/{task_id}/result", response_model=AgentTaskResult)
async def get_task_result(
    task_id: str,
    agent_type: AgentType = Query(default=AgentType.OPENMANUS)
):
    """Get task result.

    Returns complete result including extracted data and screenshots.
    Only available for completed tasks.
    """
    try:
        agent = get_agent(agent_type)
        result = await agent.get_task_result(task_id)

        return AgentTaskResult(**result)

    except Exception as e:
        logger.error(f"Failed to get task result: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    agent_type: AgentType = Query(default=AgentType.OPENMANUS)
):
    """Cancel running task."""
    try:
        agent = get_agent(agent_type)
        success = await agent.cancel_task(task_id)

        return {
            "task_id": task_id,
            "cancelled": success,
            "message": f"Task {task_id} cancelled successfully"
        }

    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks", response_model=AgentTaskList)
async def list_tasks(
    agent_type: AgentType = Query(default=AgentType.OPENMANUS),
    status: TaskStatus | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0)
):
    """List agent tasks with pagination."""
    try:
        agent = get_agent(agent_type)
        tasks = await agent.list_tasks(
            status=status,
            limit=limit,
            offset=offset
        )

        task_responses = [
            AgentTaskResponse(
                task_id=t["task_id"],
                agent_type=agent_type,
                status=TaskStatus(t["status"]),
                progress=t["progress"],
                current_step=None,
                created_at=t["created_at"],
                updated_at=t["updated_at"]
            )
            for t in tasks
        ]

        return AgentTaskList(
            tasks=task_responses,
            total=len(task_responses),
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/stream")
async def stream_task_progress(
    task_id: str,
    agent_type: AgentType = Query(default=AgentType.OPENMANUS)
):
    """Stream task progress via Server-Sent Events.

    Connect to this endpoint to receive real-time progress updates.

    Example (JavaScript):
    ```javascript
    const eventSource = new EventSource('/api/v1/agents/tasks/task-123/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Progress:', data.progress, '%');
    };
    ```
    """
    try:
        agent = get_agent(agent_type)

        async def event_stream():
            """Generate SSE events."""
            async for progress in agent.stream_progress(task_id):
                import json
                yield f"data: {json.dumps(progress)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Failed to stream progress: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/health")
async def health_check():
    """Agent service health check."""
    return {
        "status": "healthy",
        "agents": {
            "openmanus": "available",
            "skyvern": "available",
            "manus": "available",
            "s3": "available",
        }
    }


# ============================================================================
# New v2 Agent Endpoints - Manus, S3, Tools
# ============================================================================

from typing import Any

from pydantic import BaseModel, Field

# Tool Registry singleton
_tool_registry = None

def get_tool_registry():
    """Get or create tool registry."""
    global _tool_registry
    if _tool_registry is None:
        from src.infrastructure.tools import create_unified_registry
        _tool_registry = create_unified_registry()
    return _tool_registry


# --- Pydantic models for new endpoints ---

class ManusTaskRequest(BaseModel):
    """Request for ManusAgent execution."""
    prompt: str = Field(..., description="Task description")
    context: dict[str, Any] | None = Field(default=None)
    model: str = Field(default="qwen3-coder:30b")
    max_iterations: int = Field(default=10, ge=1, le=50)


class S3TaskRequest(BaseModel):
    """Request for S3Agent (browser/desktop) execution."""
    prompt: str = Field(..., description="Task description")
    mode: str | None = Field(default=None, description="Force: browser or desktop")
    context: dict[str, Any] | None = Field(default=None)
    max_iterations: int = Field(default=15, ge=1, le=50)


class ToolCallRequest(BaseModel):
    """Request to call a tool directly."""
    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolInfo(BaseModel):
    """Tool information."""
    name: str
    description: str
    category: str
    parameters_schema: dict[str, Any]


# --- Tool Registry endpoints ---

@router.get("/tools", response_model=list[ToolInfo])
async def list_tools(category: str | None = None):
    """List available tools in the registry."""
    registry = get_tool_registry()
    tool_names = registry.list_tools(category=category)

    tools = []
    for name in tool_names:
        tool = registry._tools.get(name)
        if tool:
            tools.append(ToolInfo(
                name=tool.name,
                description=tool.description,
                category=registry._categories.get(name, "default"),
                parameters_schema=tool.parameters_schema,
            ))
    return tools


@router.get("/tools/categories")
async def list_tool_categories():
    """List tool categories."""
    registry = get_tool_registry()
    return {"categories": registry.get_categories()}


@router.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, request: ToolCallRequest):
    """Execute a tool directly."""
    registry = get_tool_registry()

    tool = registry._tools.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

    try:
        result = await tool.execute(**request.parameters)
        return {
            "task_id": f"tool-{tool_name}",
            "status": "completed" if result.success else "failed",
            "result": result.output if result.success else None,
            "error": result.error if not result.success else None,
            "execution_time_ms": result.execution_time_ms,
        }
    except Exception as e:
        logger.exception(f"Tool execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ManusAgent endpoints ---

@router.post("/manus/execute")
async def execute_manus_task(request: ManusTaskRequest, background_tasks: BackgroundTasks):
    """Execute task using ManusAgent (think-execute reasoning loop)."""
    try:
        from src.infrastructure.agents.manus import create_manus_agent

        agent = await create_manus_agent(
            model=request.model,
            ollama_host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

        result = await agent.execute_task({
            "prompt": request.prompt,
            "context": request.context,
            "max_iterations": request.max_iterations,
        })

        return {
            "task_id": result.get("task_id", "manus-task"),
            "status": result.get("status", "completed"),
            "result": result.get("result"),
            "error": result.get("error"),
            "iterations": result.get("iterations", 0),
        }

    except Exception as e:
        logger.exception(f"ManusAgent execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- S3Agent endpoints ---

@router.post("/s3/execute")
async def execute_s3_task(request: S3TaskRequest):
    """Execute task using S3Agent (hybrid browser/desktop automation)."""
    try:
        from src.infrastructure.agents.s3 import create_s3_agent

        agent = await create_s3_agent(max_iterations=request.max_iterations)

        task_config = {
            "prompt": request.prompt,
            "context": request.context,
        }
        if request.mode:
            task_config["mode"] = request.mode

        result = await agent.execute_task(task_config)

        return {
            "task_id": result.get("task_id", "s3-task"),
            "status": result.get("status", "completed"),
            "result": result.get("result"),
            "mode": result.get("mode"),
            "error": result.get("error"),
        }

    except Exception as e:
        logger.exception(f"S3Agent execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/s3/screenshot")
async def s3_screenshot():
    """Capture screenshot from VM-400 desktop."""
    try:
        from src.infrastructure.agents.s3 import DesktopClient

        client = DesktopClient(host=os.getenv("VNC_HOST", "localhost"), port=int(os.getenv("VNC_PORT", "5900")))
        await client.connect()
        result = await client.screenshot()

        return result

    except Exception as e:
        logger.exception(f"Screenshot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/s3/click")
async def s3_click(x: int, y: int):
    """Click at coordinates on VM-400 desktop."""
    try:
        from src.infrastructure.agents.s3 import DesktopClient

        client = DesktopClient(host=os.getenv("VNC_HOST", "localhost"), port=int(os.getenv("VNC_PORT", "5900")))
        await client.connect()
        return await client.click(x, y)

    except Exception as e:
        logger.exception(f"Click failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/s3/type")
async def s3_type_text(text: str):
    """Type text on VM-400 desktop."""
    try:
        from src.infrastructure.agents.s3 import DesktopClient

        client = DesktopClient(host=os.getenv("VNC_HOST", "localhost"), port=int(os.getenv("VNC_PORT", "5900")))
        await client.connect()
        return await client.type_text(text)

    except Exception as e:
        logger.exception(f"Type failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/s3/launch")
async def s3_launch_app(command: str):
    """Launch application on VM-400 desktop."""
    try:
        from src.infrastructure.agents.s3 import DesktopClient

        client = DesktopClient(host=os.getenv("VNC_HOST", "localhost"), port=int(os.getenv("VNC_PORT", "5900")))
        await client.connect()
        return await client.launch_application(command)

    except Exception as e:
        logger.exception(f"Launch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
