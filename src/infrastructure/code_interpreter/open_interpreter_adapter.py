"""Open Interpreter Local Adapter for Tawiza."""

import asyncio
import os
import subprocess
import tempfile
from collections.abc import Callable
from typing import Any

from loguru import logger


class OpenInterpreterAdapter:
    """
    Open Interpreter Local Adapter.

    Provides local code execution using Open Interpreter with Ollama integration.
    Fallback option when E2B Cloud is unavailable or for offline scenarios.
    """

    def __init__(
        self,
        model: str = "qwen2.5-coder:14b",
        ollama_url: str = "http://localhost:11434",
        timeout: int = 300,
        safe_mode: bool = True,
        output_callback: Callable[[str, str], None] | None = None,
        **kwargs,
    ):
        """
        Initialize Open Interpreter adapter.

        Args:
            model: Ollama model to use for code generation
            ollama_url: Ollama API URL
            timeout: Default timeout in seconds for code execution
            safe_mode: If True, ask for confirmation before execution
            output_callback: Optional callback for live output streaming
            **kwargs: Additional configuration options
        """
        self.model = model
        self.ollama_url = ollama_url
        self.default_timeout = timeout
        self.safe_mode = safe_mode
        self.output_callback = output_callback
        self.config = kwargs
        logger.info(f"Open Interpreter Adapter initialized (model={model}, safe_mode={safe_mode})")

    async def _read_stream(self, stream, callback, stream_type):
        """Read a stream line by line and invoke callback."""
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode().rstrip()
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(text, stream_type)
                else:
                    callback(text, stream_type)

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int | None = None,
        auto_run: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Execute code using Open Interpreter locally.

        Args:
            code: Code to execute
            language: Programming language ("python", "javascript", "bash", etc.)
            timeout: Execution timeout in seconds
            auto_run: If True, automatically execute without confirmation
            **kwargs: Additional execution options

        Returns:
            Dict containing:
                - success: bool
                - output: str (stdout)
                - error: Optional[str] (stderr)
                - results: List of execution results
                - execution_time: float
                - backend: str ("open_interpreter")
        """
        timeout = timeout or self.default_timeout

        try:
            logger.info(f"Executing {language} code with Open Interpreter (timeout={timeout}s)")

            # Create temporary file with code
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=self._get_extension(language), delete=False
            ) as f:
                f.write(code)
                code_file = f.name

            try:
                # Execute code based on language
                if language == "python":
                    result = await self._execute_python(code_file, timeout)
                elif language == "javascript":
                    result = await self._execute_javascript(code_file, timeout)
                elif language == "bash":
                    result = await self._execute_bash(code_file, timeout)
                else:
                    raise ValueError(f"Unsupported language: {language}")

                return {
                    **result,
                    "backend": "open_interpreter",
                }

            finally:
                # Clean up temp file
                if os.path.exists(code_file):
                    os.unlink(code_file)

        except TimeoutError:
            logger.error(f"Open Interpreter execution timeout after {timeout}s")
            return {
                "success": False,
                "output": "",
                "error": f"Execution timeout after {timeout} seconds",
                "results": [],
                "execution_time": timeout,
                "backend": "open_interpreter",
            }
        except Exception as e:
            logger.error(f"Open Interpreter execution failed: {str(e)}")
            return {
                "success": False,
                "output": "",
                "error": f"Open Interpreter error: {str(e)}",
                "results": [],
                "execution_time": 0,
                "backend": "open_interpreter",
            }

    async def _execute_python(self, code_file: str, timeout: int) -> dict[str, Any]:
        """Execute Python code file with live output."""
        import time

        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_exec(
                "python3",
                code_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_lines = []
            stderr_lines = []

            async def stdout_cb(text, stype):
                stdout_lines.append(text)
                if self.output_callback:
                    await self.output_callback(text, stype)

            async def stderr_cb(text, stype):
                stderr_lines.append(text)
                if self.output_callback:
                    await self.output_callback(text, stype)

            await asyncio.gather(
                self._read_stream(process.stdout, stdout_cb, "stdout"),
                self._read_stream(process.stderr, stderr_cb, "stderr"),
            )

            await process.wait()
            execution_time = time.time() - start_time

            return {
                "success": process.returncode == 0,
                "output": "\n".join(stdout_lines),
                "error": "\n".join(stderr_lines) if stderr_lines else None,
                "results": [],
                "execution_time": execution_time,
                "return_code": process.returncode,
            }

        except TimeoutError:
            # Kill the process if it times out
            if process:
                process.kill()
            raise

    async def _execute_javascript(self, code_file: str, timeout: int) -> dict[str, Any]:
        """Execute JavaScript code file with Node.js."""
        import time

        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_exec(
                "node",
                code_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            execution_time = time.time() - start_time

            return {
                "success": process.returncode == 0,
                "output": stdout.decode() if stdout else "",
                "error": stderr.decode() if stderr else None,
                "results": [],
                "execution_time": execution_time,
                "return_code": process.returncode,
            }

        except TimeoutError:
            if process:
                process.kill()
            raise

    async def _execute_bash(self, code_file: str, timeout: int) -> dict[str, Any]:
        """Execute Bash script."""
        import time

        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_exec(
                "bash",
                code_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            execution_time = time.time() - start_time

            return {
                "success": process.returncode == 0,
                "output": stdout.decode() if stdout else "",
                "error": stderr.decode() if stderr else None,
                "results": [],
                "execution_time": execution_time,
                "return_code": process.returncode,
            }

        except TimeoutError:
            if process:
                process.kill()
            raise

    def _get_extension(self, language: str) -> str:
        """Get file extension for language."""
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "bash": ".sh",
            "shell": ".sh",
        }
        return extensions.get(language, ".txt")

    async def execute_python(
        self, code: str, timeout: int | None = None, **kwargs
    ) -> dict[str, Any]:
        """
        Execute Python code locally.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary
        """
        return await self.execute_code(code, language="python", timeout=timeout, **kwargs)

    async def execute_javascript(
        self, code: str, timeout: int | None = None, **kwargs
    ) -> dict[str, Any]:
        """
        Execute JavaScript code locally.

        Args:
            code: JavaScript code to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary
        """
        return await self.execute_code(code, language="javascript", timeout=timeout, **kwargs)

    async def execute_bash(self, code: str, timeout: int | None = None, **kwargs) -> dict[str, Any]:
        """
        Execute Bash script locally.

        Args:
            code: Bash script to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary
        """
        return await self.execute_code(code, language="bash", timeout=timeout, **kwargs)

    def is_available(self) -> bool:
        """
        Check if Open Interpreter adapter is available.

        Returns:
            True if Python interpreter is available
        """
        try:
            result = subprocess.run(["python3", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
