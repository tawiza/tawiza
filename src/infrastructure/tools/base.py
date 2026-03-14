"""
Base classes for the tool system.

This module defines:
- ToolResult: Container for tool execution results
- BaseTool: Abstract base class that all tools must inherit from
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ToolResult:
    """
    Standardized container for tool execution results.

    Attributes:
        success: Whether the tool executed successfully
        output: The main output/result from the tool
        error: Error message if execution failed
        metadata: Additional metadata about the execution
        execution_time_ms: Time taken to execute (milliseconds)
        timestamp: When the execution occurred
    """

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
        }

    @property
    def is_error(self) -> bool:
        """Check if result represents an error."""
        return not self.success or self.error is not None


class BaseTool(ABC):
    """
    Abstract base class for all tools in the Tawiza system.

    All tools must:
    1. Implement execute() method for actual execution
    2. Implement to_openai_schema() for OpenAI function calling compatibility
    3. Define name, description, and parameters

    Tools can optionally:
    - Implement validate_input() for input validation
    - Override requires_sandbox for security classification
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for this tool.

        Should be lowercase with underscores (e.g., 'python_execute').
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of what this tool does.

        Used in LLM prompts to help the model decide when to use the tool.
        """
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """
        JSON Schema defining the tool's parameters.

        Must follow JSON Schema specification for OpenAI compatibility.
        Example:
        {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                }
            },
            "required": ["code"]
        }
        """
        pass

    @property
    def requires_sandbox(self) -> bool:
        """
        Whether this tool requires sandboxed execution.

        Default: False
        Override to True for tools that execute untrusted code.
        """
        return False

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Parameters as defined in parameters_schema

        Returns:
            ToolResult containing execution outcome

        Raises:
            Should NOT raise exceptions - wrap errors in ToolResult
        """
        pass

    def validate_input(self, **kwargs) -> str | None:
        """
        Validate input parameters before execution.

        Args:
            **kwargs: Parameters to validate

        Returns:
            Error message if validation fails, None if valid

        Default implementation: No validation (always valid)
        Override to add custom validation logic.
        """
        return None

    def to_openai_schema(self) -> dict[str, Any]:
        """
        Convert tool to OpenAI function calling schema.

        Returns:
            Schema dict compatible with OpenAI's tools parameter

        Format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "Tool description",
                "parameters": {...}
            }
        }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
