"""DTOs for Code Execution."""

from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionBackend(StrEnum):
    """Execution backend options."""
    E2B_CLOUD = "e2b_cloud"
    OPEN_INTERPRETER = "open_interpreter"
    AUTO = "auto"


class CodeLanguage(StrEnum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    BASH = "bash"


class CodeExecutionRequest(BaseModel):
    """Request to execute code."""

    code: str = Field(..., description="Code to execute")
    language: CodeLanguage = Field(
        default=CodeLanguage.PYTHON,
        description="Programming language"
    )
    backend: ExecutionBackend | None = Field(
        default=None,
        description="Execution backend (None for auto-select)"
    )
    timeout: int | None = Field(
        default=300,
        description="Execution timeout in seconds",
        ge=1,
        le=600
    )
    require_cloud: bool = Field(
        default=False,
        description="Require cloud execution (E2B)"
    )
    require_local: bool = Field(
        default=False,
        description="Require local execution (Open Interpreter)"
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID to reuse sandbox"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "code": "print('Hello, World!')",
            "language": "python",
            "backend": "auto",
            "timeout": 60
        }
    })


class ExecutionResult(BaseModel):
    """Result from code execution."""

    type: str = Field(..., description="Result type (text, html, image, json)")
    content: str | None = Field(default=None, description="Text or JSON content")
    format: str | None = Field(default=None, description="Format for images (png, svg)")
    data: str | None = Field(default=None, description="Base64-encoded data")


class CodeExecutionResponse(BaseModel):
    """Response from code execution."""

    success: bool = Field(..., description="Whether execution was successful")
    output: str = Field(..., description="Standard output from execution")
    error: str | None = Field(default=None, description="Error message if failed")
    stderr: str | None = Field(default=None, description="Standard error output")
    results: list[ExecutionResult] = Field(
        default_factory=list,
        description="Structured results (images, HTML, JSON)"
    )
    execution_time: float = Field(..., description="Execution time in seconds")
    backend: str = Field(..., description="Backend that executed the code")
    sandbox_id: str | None = Field(default=None, description="Sandbox ID (for E2B)")
    return_code: int | None = Field(default=None, description="Process return code")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "output": "Hello, World!\n",
            "error": None,
            "results": [],
            "execution_time": 0.123,
            "backend": "e2b_cloud"
        }
    })


class PackageInstallRequest(BaseModel):
    """Request to install packages."""

    packages: list[str] = Field(..., description="List of packages to install")
    language: CodeLanguage = Field(
        default=CodeLanguage.PYTHON,
        description="Language package manager (python=pip, javascript=npm)"
    )
    backend: ExecutionBackend | None = Field(
        default=None,
        description="Execution backend"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "packages": ["numpy", "pandas", "matplotlib"],
            "language": "python",
            "backend": "e2b_cloud"
        }
    })


class BackendStatusResponse(BaseModel):
    """Status of execution backends."""

    e2b_cloud: dict[str, Any] = Field(..., description="E2B Cloud status")
    open_interpreter: dict[str, Any] = Field(..., description="Open Interpreter status")
    default_backend: str = Field(..., description="Default backend")
    prefer_cloud: bool = Field(..., description="Cloud preference")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "e2b_cloud": {
                "available": True,
                "adapter": "E2BCodeAdapter"
            },
            "open_interpreter": {
                "available": True,
                "adapter": "OpenInterpreterAdapter"
            },
            "default_backend": "auto",
            "prefer_cloud": True
        }
    })


class InteractiveCodeRequest(BaseModel):
    """Request for interactive code generation with LLM."""

    prompt: str = Field(..., description="Natural language prompt describing the task")
    language: CodeLanguage = Field(
        default=CodeLanguage.PYTHON,
        description="Target programming language"
    )
    model: str = Field(
        default="qwen2.5-coder:14b",
        description="LLM model to use for code generation"
    )
    auto_execute: bool = Field(
        default=False,
        description="Automatically execute generated code"
    )
    backend: ExecutionBackend | None = Field(
        default=None,
        description="Execution backend if auto_execute is True"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "prompt": "Create a function to calculate fibonacci numbers",
            "language": "python",
            "model": "qwen2.5-coder:14b",
            "auto_execute": False
        }
    })


class InteractiveCodeResponse(BaseModel):
    """Response from interactive code generation."""

    generated_code: str = Field(..., description="Generated code")
    explanation: str | None = Field(default=None, description="Explanation of the code")
    execution_result: CodeExecutionResponse | None = Field(
        default=None,
        description="Execution result if auto_execute was True"
    )
    model_used: str = Field(..., description="LLM model that generated the code")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "generated_code": "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
            "explanation": "Recursive implementation of fibonacci sequence",
            "execution_result": None,
            "model_used": "qwen2.5-coder:14b"
        }
    })
