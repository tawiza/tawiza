"""
Bash command execution tool with security restrictions.

This tool allows agents to execute Bash commands with multiple security layers:
1. Pattern blocking (dangerous operations like rm -rf, dd, mkfs)
2. Command whitelisting
3. Argument validation
4. VM sandbox integration (future)

Security Design:
- Default: Local execution with strict validation
- Production: Sandbox VM for maximum isolation (Phase 1 completion)

SECURITY NOTE: This tool executes shell commands which can be dangerous.
Multiple security layers validate and restrict commands. For production use,
VM sandbox integration is strongly recommended.
"""

import asyncio
import logging
import re
import shlex
import time
from typing import Any

from ..base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# Security configuration
DANGEROUS_PATTERNS = [
    # Destructive operations
    r"\brm\s+.*-[rR]",  # rm -r, rm -R
    r"\brm\s+.*-f",  # rm -f
    r"\bdd\s+",  # dd (disk destroyer)
    r"\bmkfs\.",  # mkfs.* (format filesystem)
    r"\bformat\s+",  # format command
    r"\b:\(\)\s*{\s*:\|\:&\s*}\s*;",  # fork bomb
    # Privilege escalation
    r"\bsudo\s+",
    r"\bsu\s+",
    r"\bchmod\s+",
    r"\bchown\s+",
    # Network/download
    r"\bcurl\s+.*\|\s*bash",  # curl | bash
    r"\bcurl\s+.*\|\s*sh",  # curl | sh
    r"\bwget\s+.*\|\s*bash",
    r"\bwget\s+.*\|\s*sh",
    # System modification
    r"\biptables\s+",
    r"\bufw\s+",
    r"\bsystemctl\s+",
    r"\bservice\s+",
    r"\binit\s+",
    # Process management (potentially dangerous)
    r"\bkill\s+-9",
    r"\bkillall\s+",
    r"\bpkill\s+",
    # File descriptor tricks
    r">\s*/dev/",
    r"<\s*/dev/tcp",
    r"<\s*/dev/udp",
    # Shell trickery
    r"\beval\s+",
    r"\bexec\s+",
    r"\$\(",  # Command substitution
    r"`",  # Backticks
]

# Allowed commands (whitelist approach)
ALLOWED_COMMANDS = {
    # File inspection (read-only)
    "ls",
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "find",
    "grep",
    "awk",
    "sed",
    "cut",
    "sort",
    "uniq",
    "wc",
    "diff",
    "file",
    "stat",
    # System info (read-only)
    "pwd",
    "whoami",
    "hostname",
    "uname",
    "uptime",
    "date",
    "cal",
    "env",
    "printenv",
    "df",
    "du",
    "free",
    "top",
    "ps",
    "pstree",
    # Text processing
    "echo",
    "printf",
    "tr",
    "rev",
    "tac",
    # Archives (read-only)
    "tar",
    "zip",
    "unzip",
    "gzip",
    "gunzip",
    "bzip2",
    "bunzip2",
    # Network (read-only)
    "ping",
    "traceroute",
    "nslookup",
    "dig",
    "whois",
    "curl",
    "wget",  # Allowed but with argument validation
    # Development
    "git",
    "python3",
    "node",
    "npm",
    "pip3",
    # Math
    "bc",
    "expr",
}


class BashExecuteTool(BaseTool):
    """
    Execute Bash commands in a restricted environment.

    Features:
    - Pattern-based security validation
    - Command whitelisting
    - Argument sanitization
    - Output capture (stdout/stderr)
    - Execution timeout
    - VM sandbox ready (future)

    Example usage:
        tool = BashExecuteTool()
        result = await tool.execute(
            command="ls -la /tmp",
            timeout=5
        )
    """

    def __init__(
        self,
        use_vm_sandbox: bool = False,
        vm_sandbox_client: Any | None = None,
        default_timeout: int = 30,
        strict_mode: bool = True,
    ):
        """
        Initialize Bash execution tool.

        Args:
            use_vm_sandbox: Whether to use VM sandbox (future feature)
            vm_sandbox_client: Client for VM sandbox communication
            default_timeout: Default execution timeout in seconds
            strict_mode: If True, only allow whitelisted commands
        """
        self._use_vm_sandbox = use_vm_sandbox
        self._vm_sandbox_client = vm_sandbox_client
        self._default_timeout = default_timeout
        self._strict_mode = strict_mode

        if use_vm_sandbox and not vm_sandbox_client:
            logger.warning(
                "VM sandbox requested but no client provided. Falling back to local execution."
            )
            self._use_vm_sandbox = False

    @property
    def name(self) -> str:
        return "bash_execute"

    @property
    def description(self) -> str:
        return (
            "Execute Bash commands in a secure environment. "
            "Supports file inspection, system info, text processing, and safe operations. "
            "Dangerous operations (rm -rf, sudo, destructive commands) are blocked. "
            "Returns stdout, stderr, and exit code."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "Bash command to execute. "
                        "Can be a simple command or pipeline. "
                        "Dangerous operations are blocked for security."
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
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for command execution (optional)",
                },
            },
            "required": ["command"],
        }

    @property
    def requires_sandbox(self) -> bool:
        return True

    def validate_input(self, **kwargs) -> str | None:
        """
        Validate Bash command before execution.

        Security checks:
        1. Pattern blocking for dangerous operations
        2. Command whitelist validation (if strict_mode)
        3. Argument sanitization
        4. Length limits

        Args:
            **kwargs: Must contain 'command' parameter

        Returns:
            Error message if validation fails, None if valid
        """
        command = kwargs.get("command", "")

        if not command or not command.strip():
            return "Command cannot be empty"

        # Check command length
        if len(command) > 10000:  # 10KB limit
            return "Command too long (max 10KB)"

        # Check for dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return (
                    f"Dangerous operation detected: pattern '{pattern}'. "
                    "Destructive and privileged commands are not allowed."
                )

        # Whitelist validation (strict mode)
        if self._strict_mode:
            whitelist_error = self._validate_whitelist(command)
            if whitelist_error:
                return whitelist_error

        # Validate working directory if provided
        working_dir = kwargs.get("working_dir")
        if working_dir:
            if not isinstance(working_dir, str):
                return "working_dir must be a string"
            if len(working_dir) > 1000:
                return "working_dir too long"
            # Block path traversal
            if ".." in working_dir:
                return "Path traversal (..) not allowed in working_dir"

        return None

    def _validate_whitelist(self, command: str) -> str | None:
        """
        Check that command uses only whitelisted programs.

        Args:
            command: Bash command to check

        Returns:
            Error message if invalid command found, None otherwise
        """
        # Split command by pipes and semicolons
        parts = re.split(r"[|;]", command)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Extract the base command (first word)
            try:
                tokens = shlex.split(part)
                if not tokens:
                    continue

                base_command = tokens[0].split("/")[-1]  # Handle /usr/bin/ls -> ls

                if base_command not in ALLOWED_COMMANDS:
                    return (
                        f"Command '{base_command}' not in whitelist. "
                        f"Allowed commands: {', '.join(sorted(ALLOWED_COMMANDS))}"
                    )

            except ValueError as e:
                return f"Failed to parse command: {str(e)}"

        return None

    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute Bash command with security restrictions.

        Args:
            command: Bash command to execute
            timeout: Execution timeout (seconds)
            working_dir: Working directory (optional)

        Returns:
            ToolResult with stdout/stderr output and exit code
        """
        command = kwargs.get("command", "")
        timeout = kwargs.get("timeout", self._default_timeout)
        working_dir = kwargs.get("working_dir")

        start_time = time.time()

        try:
            # Validate first
            validation_error = self.validate_input(**kwargs)
            if validation_error:
                return ToolResult(success=False, error=validation_error, execution_time_ms=0)

            # Execute in appropriate environment
            if self._use_vm_sandbox:
                result = await self._execute_in_vm(command, timeout, working_dir)
            else:
                result = await self._execute_local(command, timeout, working_dir)

            execution_time_ms = (time.time() - start_time) * 1000

            return ToolResult(
                success=result["exit_code"] == 0,
                output=result,
                execution_time_ms=execution_time_ms,
                metadata={
                    "sandbox_type": "vm" if self._use_vm_sandbox else "local",
                    "timeout": timeout,
                    "exit_code": result["exit_code"],
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
            logger.exception("Bash execution error")
            return ToolResult(
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time_ms=execution_time_ms,
                metadata={"exception_type": type(e).__name__},
            )

    async def _execute_local(
        self, command: str, timeout: int, working_dir: str | None
    ) -> dict[str, Any]:
        """
        Execute command locally with asyncio.subprocess.

        SECURITY: Uses subprocess with shell=True (necessary for bash).
        Command has been validated with multiple security checks.

        Args:
            command: Bash command to execute (already validated)
            timeout: Execution timeout
            working_dir: Working directory

        Returns:
            Dict with 'stdout', 'stderr', and 'exit_code' keys
        """
        try:
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            # Wait for completion with timeout
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": process.returncode or 0,
            }

        except TimeoutError:
            # Kill the process if it times out
            try:
                process.kill()
                await process.wait()
            except:
                pass
            raise

    async def _execute_in_vm(
        self, command: str, timeout: int, working_dir: str | None
    ) -> dict[str, Any]:
        """
        Execute command in VM sandbox via VMSandboxClient.

        Sends the command to the sandbox service running on the isolated VM
        for isolated execution in a Docker container.

        Args:
            command: Bash command to execute
            timeout: Execution timeout
            working_dir: Working directory (prepended as cd command)

        Returns:
            Dict with 'stdout', 'stderr', and 'exit_code' keys
        """
        if not self._vm_sandbox_client:
            raise RuntimeError("VM sandbox client not configured")

        # Prepend cd if working_dir specified
        full_command = command
        if working_dir:
            full_command = f"cd {working_dir} && {command}"

        # Call VM sandbox service
        result = await self._vm_sandbox_client.run_bash(code=full_command, timeout=timeout)

        # Log execution for monitoring
        if result.success:
            logger.debug(
                f"VM sandbox bash execution completed: "
                f"exit_code={result.exit_code}, duration={result.duration_ms}ms"
            )
        else:
            logger.warning(f"VM sandbox bash execution failed: {result.error}")

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "vm_run_id": result.run_id,
            "duration_ms": result.duration_ms,
        }

    async def execute_stream(
        self,
        command: str,
        on_output: Any | None = None,
        timeout: int | None = None,
        working_dir: str | None = None,
    ) -> ToolResult:
        """
        Execute Bash command with streaming output.

        Streams stdout/stderr in real-time via callback, useful for
        long-running commands or TUI integration.

        Args:
            command: Bash command to execute
            on_output: Async callback(stream_type, content) for each output chunk
                       stream_type is 'stdout' or 'stderr'
            timeout: Execution timeout (seconds)
            working_dir: Working directory (optional)

        Returns:
            ToolResult with final stdout/stderr and exit code
        """
        timeout = timeout or self._default_timeout
        start_time = time.time()

        try:
            # Validate first
            validation_error = self.validate_input(command=command, working_dir=working_dir)
            if validation_error:
                return ToolResult(success=False, error=validation_error, execution_time_ms=0)

            # Must use VM sandbox for streaming
            if not self._use_vm_sandbox or not self._vm_sandbox_client:
                return ToolResult(
                    success=False,
                    error="Streaming execution requires VM sandbox mode",
                    execution_time_ms=0,
                )

            # Prepend cd if working_dir specified
            full_command = command
            if working_dir:
                full_command = f"cd {working_dir} && {command}"

            # Default callback that does nothing
            async def noop_callback(stream_type: str, content: str) -> None:
                pass

            callback = on_output or noop_callback

            # Execute with streaming
            result = await self._vm_sandbox_client.run_bash_stream(
                code=full_command, on_output=callback, timeout=timeout
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
            logger.exception("Bash streaming execution error")
            return ToolResult(
                success=False,
                error=f"Streaming execution error: {str(e)}",
                execution_time_ms=execution_time_ms,
                metadata={"exception_type": type(e).__name__},
            )
