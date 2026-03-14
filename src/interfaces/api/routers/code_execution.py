"""API Router for Code Execution."""

import os

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from src.application.dtos.code_execution_dtos import (
    BackendStatusResponse,
    CodeExecutionRequest,
    CodeExecutionResponse,
    ExecutionBackend,
    ExecutionResult,
    InteractiveCodeRequest,
    InteractiveCodeResponse,
    PackageInstallRequest,
)
from src.infrastructure.code_interpreter.execution_router import (
    ExecutionRouter,
)
from src.infrastructure.config.settings import get_settings
from src.interfaces.api.websocket.models import TerminalOutputMessage

router = APIRouter(
    prefix="/api/v1/code-execution",
    tags=["Code Execution"],
)

# Global execution router instance
_execution_router: ExecutionRouter | None = None


def get_execution_router() -> ExecutionRouter:
    """Get or create execution router instance with WebSocket support."""
    global _execution_router
    if _execution_router is None:
        settings = get_settings()

        # Callback for live terminal output
        async def terminal_callback(content: str, stream: str = "stdout"):
            try:
                from src.interfaces.api.websocket.models import TerminalOutputMessage
                from src.interfaces.api.websocket.server import get_ws_manager

                ws_manager = get_ws_manager()
                # Broadcast to all for now, as task_id isn't always known at this level
                # In production, we'd use session_id from context
                message = TerminalOutputMessage(task_id="live-exec", content=content, stream=stream)
                await ws_manager.broadcast(message)
            except Exception as e:
                logger.debug(f"Terminal callback failed: {e}")

        _execution_router = ExecutionRouter(
            e2b_api_key=settings.code_execution.e2b_api_key,
            default_backend=ExecutionBackend.AUTO,
            prefer_cloud=settings.code_execution.prefer_cloud,
            output_callback=terminal_callback,
        )
    return _execution_router


@router.post("/execute", response_model=CodeExecutionResponse)
async def execute_code(
    request: CodeExecutionRequest,
    router: ExecutionRouter = Depends(get_execution_router),
) -> CodeExecutionResponse:
    """
    Execute code in a secure sandbox.

    This endpoint executes arbitrary code in an isolated environment using
    either E2B Cloud sandboxes or local Open Interpreter execution.

    The router automatically selects the best backend based on availability,
    or you can explicitly specify the backend to use.

    Args:
        request: Code execution request with code, language, and options

    Returns:
        Execution result with output, errors, and execution metadata

    Raises:
        HTTPException: If execution fails or no backend is available
    """
    try:
        logger.info(f"Executing {request.language} code (backend={request.backend})")

        # Execute code
        result = await router.execute_code(
            code=request.code,
            language=request.language,
            backend=request.backend,
            timeout=request.timeout,
            require_cloud=request.require_cloud,
            require_local=request.require_local,
            session_id=request.session_id,
        )

        # Convert results to DTOs
        execution_results = [
            ExecutionResult(
                type=r.get("type", "text"),
                content=r.get("content"),
                format=r.get("format"),
                data=r.get("data"),
            )
            for r in result.get("results", [])
        ]

        return CodeExecutionResponse(
            success=result["success"],
            output=result["output"],
            error=result.get("error"),
            stderr=result.get("stderr"),
            results=execution_results,
            execution_time=result["execution_time"],
            backend=result["backend"],
            sandbox_id=result.get("sandbox_id"),
            return_code=result.get("return_code"),
        )

    except RuntimeError as e:
        logger.error(f"Code execution failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during code execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code execution error: {str(e)}",
        )


@router.post("/execute/python", response_model=CodeExecutionResponse)
async def execute_python(
    code: str,
    backend: ExecutionBackend | None = None,
    timeout: int = 300,
    router: ExecutionRouter = Depends(get_execution_router),
) -> CodeExecutionResponse:
    """
    Execute Python code.

    Convenience endpoint for Python code execution.

    Args:
        code: Python code to execute
        backend: Execution backend (None for auto-select)
        timeout: Execution timeout in seconds

    Returns:
        Execution result
    """
    request = CodeExecutionRequest(
        code=code,
        language="python",
        backend=backend,
        timeout=timeout,
    )
    return await execute_code(request, router)


@router.post("/execute/javascript", response_model=CodeExecutionResponse)
async def execute_javascript(
    code: str,
    backend: ExecutionBackend | None = None,
    timeout: int = 300,
    router: ExecutionRouter = Depends(get_execution_router),
) -> CodeExecutionResponse:
    """
    Execute JavaScript code.

    Convenience endpoint for JavaScript code execution.

    Args:
        code: JavaScript code to execute
        backend: Execution backend (None for auto-select)
        timeout: Execution timeout in seconds

    Returns:
        Execution result
    """
    request = CodeExecutionRequest(
        code=code,
        language="javascript",
        backend=backend,
        timeout=timeout,
    )
    return await execute_code(request, router)


@router.post("/execute/bash", response_model=CodeExecutionResponse)
async def execute_bash(
    code: str,
    backend: ExecutionBackend | None = None,
    timeout: int = 300,
    router: ExecutionRouter = Depends(get_execution_router),
) -> CodeExecutionResponse:
    """
    Execute Bash script.

    Convenience endpoint for Bash script execution.
    Only available with Open Interpreter backend.

    Args:
        code: Bash script to execute
        backend: Execution backend (must support bash)
        timeout: Execution timeout in seconds

    Returns:
        Execution result
    """
    request = CodeExecutionRequest(
        code=code,
        language="bash",
        backend=backend,
        timeout=timeout,
    )
    return await execute_code(request, router)


@router.post("/install", response_model=CodeExecutionResponse)
async def install_packages(
    request: PackageInstallRequest,
    router: ExecutionRouter = Depends(get_execution_router),
) -> CodeExecutionResponse:
    """
    Install packages in execution environment.

    For Python: uses pip
    For JavaScript: uses npm

    Args:
        request: Package installation request

    Returns:
        Installation result
    """
    try:
        logger.info(f"Installing {request.language} packages: {request.packages}")

        # Build installation code
        if request.language == "python":
            install_code = f"!pip install {' '.join(request.packages)}"
            language = "python"
        elif request.language == "javascript":
            install_code = f"!npm install {' '.join(request.packages)}"
            language = "javascript"
        else:
            raise ValueError(f"Unsupported language: {request.language}")

        # Execute installation
        result = await router.execute_code(
            code=install_code,
            language=language,
            backend=request.backend,
            timeout=600,  # Longer timeout for package installation
        )

        execution_results = [
            ExecutionResult(
                type=r.get("type", "text"),
                content=r.get("content"),
                format=r.get("format"),
                data=r.get("data"),
            )
            for r in result.get("results", [])
        ]

        return CodeExecutionResponse(
            success=result["success"],
            output=result["output"],
            error=result.get("error"),
            stderr=result.get("stderr"),
            results=execution_results,
            execution_time=result["execution_time"],
            backend=result["backend"],
            sandbox_id=result.get("sandbox_id"),
        )

    except Exception as e:
        logger.error(f"Package installation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Package installation error: {str(e)}",
        )


@router.get("/status", response_model=BackendStatusResponse)
async def get_backend_status(
    router: ExecutionRouter = Depends(get_execution_router),
) -> BackendStatusResponse:
    """
    Get status of execution backends.

    Returns information about available execution backends,
    their configuration, and current status.

    Returns:
        Backend status information
    """
    try:
        status_data = router.get_backend_status()
        return BackendStatusResponse(**status_data)
    except Exception as e:
        logger.error(f"Failed to get backend status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status check error: {str(e)}",
        )


@router.post("/interactive", response_model=InteractiveCodeResponse)
async def interactive_code_generation(
    request: InteractiveCodeRequest,
    router: ExecutionRouter = Depends(get_execution_router),
) -> InteractiveCodeResponse:
    """
    Generate code from natural language prompt using LLM.

    This endpoint uses an LLM (via Ollama) to generate code based on
    a natural language description. Optionally, it can also execute
    the generated code.

    Args:
        request: Interactive code generation request

    Returns:
        Generated code and optional execution result

    Note:
        This is a basic implementation. For production use, consider
        integrating with Open Interpreter's conversational features.
    """
    try:
        logger.info(f"Generating {request.language} code from prompt: {request.prompt}")

        # Use Ollama for code generation
        from src.infrastructure.llm.ollama_client import OllamaClient

        settings = get_settings()
        client = OllamaClient(
            base_url=settings.ollama.base_url,
            model=request.model,
        )

        # Check Ollama availability
        if not await client.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama service not available. Please ensure Ollama is running.",
            )

        # System prompt for code generation
        system_prompt = f"""You are an expert {request.language.value} programmer.
Generate clean, well-documented, production-ready code based on the user's request.
Return ONLY the code without any markdown formatting or explanation.
The code should be complete and ready to execute."""

        # Generate code
        generated_code = await client.generate(
            prompt=request.prompt,
            model=request.model,
            system=system_prompt,
            temperature=0.2,  # Low temperature for deterministic code
        )

        # Clean up code (remove markdown if present)
        code = generated_code.strip()
        if code.startswith("```"):
            lines = code.split("\n")
            # Remove first line (```python) and last line (```)
            code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Generate explanation
        explanation_prompt = f"Briefly explain what this code does in 1-2 sentences:\n\n{code}"
        explanation = await client.generate(
            prompt=explanation_prompt,
            model=request.model,
            temperature=0.3,
            max_tokens=150,
        )

        await client.close()

        # Optionally execute the generated code
        execution_result = None
        if request.auto_execute:
            exec_result = await router.execute_code(
                code=code,
                language=request.language,
                backend=request.backend,
                timeout=30,
            )
            execution_result = CodeExecutionResponse(
                success=exec_result.success,
                output=exec_result.output,
                error=exec_result.error,
                execution_time=exec_result.execution_time,
                backend=exec_result.backend,
            )

        return InteractiveCodeResponse(
            generated_code=code,
            explanation=explanation.strip(),
            execution_result=execution_result,
            model_used=request.model,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Interactive code generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation error: {str(e)}",
        )
