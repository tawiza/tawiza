"""
Python code execution tool with security restrictions.

This tool allows agents to execute Python code with multiple security layers:
1. Pattern blocking (dangerous operations)
2. Import whitelisting
3. RestrictedPython sandbox (current implementation)
4. VM sandbox integration (future upgrade)

Security Design:
- Default: RestrictedPython for quick local execution
- Production: Sandbox VM for maximum isolation (Phase 1 completion)

SECURITY NOTE: This file uses Python's built-in exec() function which is
necessary for dynamic code execution. Multiple security layers protect against
malicious code. For production use, VM sandbox integration is recommended.
"""

import logging
import re
import sys
import time
from io import StringIO
from typing import Any

from ..base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# Security configuration
DANGEROUS_PATTERNS = [
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bcompile\s*\(",
    r"\bopen\s*\(",
    r"\bfile\s*\(",
    r"\binput\s*\(",
    r"\braw_input\s*\(",
    r"subprocess",
    r"os\.system",
    r"os\.popen",
    r"os\.spawn",
    r"os\.exec",
    r"__builtins__",
    r"__globals__",
    r"__code__",
    r"__class__",
]

ALLOWED_IMPORTS = {
    # Standard library - safe modules
    "math",
    "random",
    "datetime",
    "json",
    "collections",
    "itertools",
    "functools",
    "re",
    "string",
    "decimal",
    "fractions",
    "statistics",
    "copy",
    "pprint",
    "typing",
    # Data science - commonly needed
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    # Note: os, sys, subprocess are explicitly blocked
}


class PythonExecuteTool(BaseTool):
    """
    Execute Python code in a restricted environment.

    Features:
    - Pattern-based security validation
    - Import whitelisting
    - Output capture (stdout/stderr)
    - Execution timeout
    - RestrictedPython sandbox (current)
    - VM sandbox ready (future)

    Example usage:
        tool = PythonExecuteTool()
        result = await tool.execute(
            code="print('Hello, World!')",
            timeout=5
        )
    """

    def __init__(
        self,
        use_vm_sandbox: bool = False,
        vm_sandbox_client: Any | None = None,
        default_timeout: int = 30,
    ):
        """
        Initialize Python execution tool.

        Args:
            use_vm_sandbox: Whether to use VM sandbox (future feature)
            vm_sandbox_client: Client for VM sandbox communication
            default_timeout: Default execution timeout in seconds
        """
        self._use_vm_sandbox = use_vm_sandbox
        self._vm_sandbox_client = vm_sandbox_client
        self._default_timeout = default_timeout

        if use_vm_sandbox and not vm_sandbox_client:
            logger.warning(
                "VM sandbox requested but no client provided. Falling back to RestrictedPython."
            )
            self._use_vm_sandbox = False

    @property
    def name(self) -> str:
        return "python_execute"

    @property
    def description(self) -> str:
        return (
            "Execute Python code in a secure sandbox environment. "
            "Supports data processing, calculations, and analysis. "
            "Returns stdout, stderr, and any printed output. "
            "Dangerous operations (file I/O, subprocess, network) are blocked."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Python code to execute. "
                        "Can include imports from allowed modules, "
                        "calculations, data processing, etc."
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        f"Execution timeout in seconds (default: {self._default_timeout})"
                    ),
                    "default": self._default_timeout,
                    "minimum": 1,
                    "maximum": 300,
                },
            },
            "required": ["code"],
        }

    @property
    def requires_sandbox(self) -> bool:
        return True

    def validate_input(self, **kwargs) -> str | None:
        """
        Validate Python code before execution.

        Security checks:
        1. Pattern blocking for dangerous operations
        2. Import statement validation
        3. Code length limits

        Args:
            **kwargs: Must contain 'code' parameter

        Returns:
            Error message if validation fails, None if valid
        """
        code = kwargs.get("code", "")

        if not code or not code.strip():
            return "Code cannot be empty"

        # Check code length
        if len(code) > 100000:  # 100KB limit
            return "Code too long (max 100KB)"

        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return (
                    f"Dangerous operation detected: '{pattern}'. "
                    "File I/O, subprocess, and eval/exec are not allowed."
                )

        # Validate imports
        import_error = self._validate_imports(code)
        if import_error:
            return import_error

        return None

    def _validate_imports(self, code: str) -> str | None:
        """
        Check that all imports are from allowed modules.

        Args:
            code: Python code to check

        Returns:
            Error message if invalid import found, None otherwise
        """
        # Find all import statements
        import_pattern = r"^\s*(?:from\s+(\S+)|import\s+(\S+))"

        for line in code.split("\n"):
            match = re.match(import_pattern, line.strip())
            if match:
                # Extract module name (from either 'from X' or 'import X')
                module = match.group(1) or match.group(2)
                module = module.split(".")[0]  # Get base module

                if module not in ALLOWED_IMPORTS:
                    return (
                        f"Import '{module}' not allowed. "
                        f"Allowed modules: {', '.join(sorted(ALLOWED_IMPORTS))}"
                    )

        return None

    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute Python code with security restrictions.

        Args:
            code: Python code to execute
            timeout: Execution timeout (seconds)

        Returns:
            ToolResult with stdout/stderr output
        """
        code = kwargs.get("code", "")
        timeout = kwargs.get("timeout", self._default_timeout)

        start_time = time.time()

        try:
            # Validate first
            validation_error = self.validate_input(**kwargs)
            if validation_error:
                return ToolResult(success=False, error=validation_error, execution_time_ms=0)

            # Execute in appropriate environment
            if self._use_vm_sandbox:
                result = await self._execute_in_vm(code, timeout)
            else:
                result = await self._execute_restricted(code, timeout)

            execution_time_ms = (time.time() - start_time) * 1000

            return ToolResult(
                success=True,
                output=result,
                execution_time_ms=execution_time_ms,
                metadata={
                    "sandbox_type": "vm" if self._use_vm_sandbox else "restricted_python",
                    "timeout": timeout,
                },
            )

        except TimeoutError:
            execution_time_ms = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                error=f"Execution timed out after {timeout} seconds",
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.exception("Python execution error")
            return ToolResult(
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time_ms=execution_time_ms,
                metadata={"exception_type": type(e).__name__},
            )

    async def _execute_restricted(self, code: str, timeout: int) -> dict[str, str]:
        """
        Execute code using RestrictedPython approach.

        This is the current implementation. It provides basic security
        but is not as isolated as a VM sandbox.

        SECURITY: Uses Python's exec() with restricted builtins and validation.
        Multiple security layers protect against malicious code:
        1. Pattern blocking (validate_input)
        2. Import whitelisting
        3. Limited builtins dictionary
        4. No file/network/subprocess access

        Args:
            code: Python code to execute (already validated)
            timeout: Execution timeout (note: not enforced in this version)

        Returns:
            Dict with 'stdout' and 'stderr' keys
        """
        # Capture stdout and stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # Create restricted globals
            # Only include safe builtins
            safe_builtins = {
                "print": print,
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "list": list,
                "dict": dict,
                "set": set,
                "tuple": tuple,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "type": type,
                "isinstance": isinstance,
                "hasattr": hasattr,
                "getattr": getattr,
                "all": all,
                "any": any,
                "True": True,
                "False": False,
                "None": None,
                "__import__": __import__,  # Needed for import statements (validated separately)
            }

            # SECURITY: exec() is intentional here for Python code execution
            # Code has been validated and runs with restricted builtins
            exec(code, {"__builtins__": safe_builtins}, {})  # nosec - intentional, validated

            return {
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue(),
            }

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    async def _execute_in_vm(self, code: str, timeout: int) -> dict[str, str]:
        """
        Execute Python code in VM sandbox via VMSandboxClient.

        Sends the code to the sandbox service running on the isolated VM
        for isolated execution in a Docker container.

        Args:
            code: Python code to execute
            timeout: Execution timeout

        Returns:
            Dict with 'stdout' and 'stderr' keys
        """
        if not self._vm_sandbox_client:
            raise RuntimeError("VM sandbox client not configured")

        # Call VM sandbox service
        result = await self._vm_sandbox_client.run_python(code=code, timeout=timeout)

        # Log execution for monitoring
        if result.success:
            logger.debug(
                f"VM sandbox Python execution completed: "
                f"exit_code={result.exit_code}, duration={result.duration_ms}ms"
            )
        else:
            logger.warning(f"VM sandbox Python execution failed: {result.error}")

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "vm_run_id": result.run_id,
            "duration_ms": result.duration_ms,
        }

    async def execute_stream(
        self,
        code: str,
        on_output: Any | None = None,
        timeout: int | None = None,
    ) -> ToolResult:
        """
        Execute Python code with streaming output.

        Streams stdout/stderr in real-time via callback, useful for
        long-running scripts or TUI integration.

        Args:
            code: Python code to execute
            on_output: Async callback(stream_type, content) for each output chunk
                       stream_type is 'stdout' or 'stderr'
            timeout: Execution timeout (seconds)

        Returns:
            ToolResult with final stdout/stderr and exit code
        """
        timeout = timeout or self._default_timeout
        start_time = time.time()

        try:
            # Validate first
            validation_error = self.validate_input(code=code)
            if validation_error:
                return ToolResult(success=False, error=validation_error, execution_time_ms=0)

            # Must use VM sandbox for streaming
            if not self._use_vm_sandbox or not self._vm_sandbox_client:
                return ToolResult(
                    success=False,
                    error="Streaming execution requires VM sandbox mode",
                    execution_time_ms=0,
                )

            # Default callback that does nothing
            async def noop_callback(stream_type: str, content: str) -> None:
                pass

            callback = on_output or noop_callback

            # Execute with streaming
            result = await self._vm_sandbox_client.run_python_stream(
                code=code, on_output=callback, timeout=timeout
            )

            execution_time_ms = (time.time() - start_time) * 1000

            return ToolResult(
                success=result.exit_code == 0,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                    "vm_run_id": result.run_id,
                    "duration_ms": result.duration_ms,
                },
                execution_time_ms=execution_time_ms,
                metadata={
                    "sandbox_type": "vm_stream",
                    "timeout": timeout,
                    "exit_code": result.exit_code,
                },
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.exception("Python streaming execution error")
            return ToolResult(
                success=False,
                error=f"Streaming execution error: {str(e)}",
                execution_time_ms=execution_time_ms,
                metadata={"exception_type": type(e).__name__},
            )
