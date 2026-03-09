"""VM Sandbox Client - Remote code execution via VM Sandbox.

This client sends code to the sandbox service running on a VM
for isolated execution in Docker containers.

Features:
- Synchronous execution with full result
- Streaming execution with real-time output via SSE
- Health check and monitoring
"""

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import httpx
from loguru import logger


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    host: str = os.getenv("VM_SANDBOX_URL", "http://localhost:8100")
    api_key: str = os.getenv("VM_SANDBOX_API_KEY", "changeme")
    default_timeout: int = 30
    max_timeout: int = 120


@dataclass
class SandboxResult:
    """Result from sandbox execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    run_id: str
    error: str | None = None


class VMSandboxClient:
    """Client for VM-400 sandbox service."""

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.host,
                timeout=self.config.max_timeout + 10,
            )
        return self._client

    async def run_python(
        self,
        code: str,
        timeout: int | None = None,
    ) -> SandboxResult:
        """Run Python code in sandbox."""
        return await self._run(code, "python", timeout)

    async def run_bash(
        self,
        code: str,
        timeout: int | None = None,
    ) -> SandboxResult:
        """Run Bash code in sandbox."""
        return await self._run(code, "bash", timeout)

    async def _run(
        self,
        code: str,
        language: str,
        timeout: int | None = None,
    ) -> SandboxResult:
        """Run code in sandbox."""
        client = await self._get_client()
        timeout = timeout or self.config.default_timeout

        try:
            response = await client.post(
                "/run",
                json={
                    "code": code,
                    "language": language,
                    "timeout": timeout,
                },
                headers={"X-API-Key": self.config.api_key},
            )
            response.raise_for_status()
            data = response.json()

            return SandboxResult(
                success=data["success"],
                stdout=data["stdout"],
                stderr=data["stderr"],
                exit_code=data["exit_code"],
                duration_ms=data["duration_ms"],
                run_id=data["run_id"],
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Sandbox HTTP error: {e}")
            return SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=0,
                run_id="error",
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error(f"Sandbox connection error: {e}")
            return SandboxResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                duration_ms=0,
                run_id="error",
                error=f"Connection error: {str(e)}",
            )

    async def health(self) -> dict:
        """Check sandbox health."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.json()
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    async def close(self):
        """Close client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Streaming Execution (Real-time output via SSE)
    # =========================================================================

    async def run_python_stream(
        self,
        code: str,
        on_output: Callable[[str, str], Awaitable[None]],
        timeout: int | None = None,
    ) -> SandboxResult:
        """
        Run Python code with streaming output.

        Args:
            code: Python code to execute
            on_output: Async callback(stream_type, content) called for each output chunk
                       stream_type is 'stdout' or 'stderr'
            timeout: Execution timeout

        Returns:
            Final SandboxResult with complete output
        """
        return await self._run_stream(code, "python", on_output, timeout)

    async def run_bash_stream(
        self,
        code: str,
        on_output: Callable[[str, str], Awaitable[None]],
        timeout: int | None = None,
    ) -> SandboxResult:
        """
        Run Bash code with streaming output.

        Args:
            code: Bash command to execute
            on_output: Async callback(stream_type, content) called for each output chunk
                       stream_type is 'stdout' or 'stderr'
            timeout: Execution timeout

        Returns:
            Final SandboxResult with complete output
        """
        return await self._run_stream(code, "bash", on_output, timeout)

    async def _run_stream(
        self,
        code: str,
        language: str,
        on_output: Callable[[str, str], Awaitable[None]],
        timeout: int | None = None,
    ) -> SandboxResult:
        """
        Run code with streaming output via Server-Sent Events.

        The sandbox service sends SSE events for each output chunk:
        - event: stdout/stderr
        - data: output content

        Final event contains the complete result.
        """
        client = await self._get_client()
        timeout_val = timeout or self.config.default_timeout

        stdout_parts = []
        stderr_parts = []
        run_id = ""
        exit_code = 0
        duration_ms = 0.0

        try:
            async with client.stream(
                "POST",
                "/run/stream",
                json={
                    "code": code,
                    "language": language,
                    "timeout": timeout_val,
                },
                headers={"X-API-Key": self.config.api_key},
                timeout=timeout_val + 10,
            ) as response:
                response.raise_for_status()

                # Parse SSE events
                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()

                        if event_type == "stdout":
                            stdout_parts.append(data)
                            await on_output("stdout", data)
                        elif event_type == "stderr":
                            stderr_parts.append(data)
                            await on_output("stderr", data)
                        elif event_type == "complete":
                            # Parse JSON result
                            import json
                            result_data = json.loads(data)
                            run_id = result_data.get("run_id", "")
                            exit_code = result_data.get("exit_code", 0)
                            duration_ms = result_data.get("duration_ms", 0.0)
                        elif event_type == "error":
                            logger.error(f"Stream error: {data}")
                            return SandboxResult(
                                success=False,
                                stdout="".join(stdout_parts),
                                stderr="".join(stderr_parts),
                                exit_code=-1,
                                duration_ms=0,
                                run_id="stream-error",
                                error=data,
                            )

            return SandboxResult(
                success=exit_code == 0,
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
                exit_code=exit_code,
                duration_ms=duration_ms,
                run_id=run_id,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Sandbox stream HTTP error: {e}")
            return SandboxResult(
                success=False,
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
                exit_code=-1,
                duration_ms=0,
                run_id="error",
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error(f"Sandbox stream connection error: {e}")
            return SandboxResult(
                success=False,
                stdout="".join(stdout_parts),
                stderr="".join(stderr_parts),
                exit_code=-1,
                duration_ms=0,
                run_id="error",
                error=f"Connection error: {str(e)}",
            )

    async def iter_output(
        self,
        code: str,
        language: str,
        timeout: int | None = None,
    ) -> AsyncIterator[tuple[str, str]]:
        """
        Iterate over output chunks as they arrive.

        Yields:
            Tuples of (stream_type, content) where stream_type is 'stdout' or 'stderr'

        Example:
            async for stream_type, content in client.iter_output(code, "python"):
                if stream_type == "stdout":
                    print(content, end="")
        """
        client = await self._get_client()
        timeout_val = timeout or self.config.default_timeout

        try:
            async with client.stream(
                "POST",
                "/run/stream",
                json={
                    "code": code,
                    "language": language,
                    "timeout": timeout_val,
                },
                headers={"X-API-Key": self.config.api_key},
                timeout=timeout_val + 10,
            ) as response:
                response.raise_for_status()

                event_type = ""
                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()

                        if event_type in ("stdout", "stderr"):
                            yield (event_type, data)
                        elif event_type == "complete":
                            return
                        elif event_type == "error":
                            raise RuntimeError(f"Sandbox error: {data}")

        except httpx.RequestError as e:
            raise RuntimeError(f"Connection error: {str(e)}")
