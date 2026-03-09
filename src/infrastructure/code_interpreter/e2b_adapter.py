"""E2B Cloud Sandbox Adapter for Tawiza."""

from typing import Any

from e2b_code_interpreter import Sandbox
from loguru import logger


class E2BCodeAdapter:
    """
    E2B Cloud Sandbox Adapter.

    Provides secure code execution using E2B's cloud-based sandboxes.
    Supports Python and JavaScript execution with isolated environments.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 300,
        **kwargs
    ):
        """
        Initialize E2B adapter.

        Args:
            api_key: E2B API key (if None, will use E2B_API_KEY env var)
            timeout: Default timeout in seconds for code execution
            **kwargs: Additional configuration options
        """
        self.api_key = api_key
        self.default_timeout = timeout
        self.config = kwargs
        logger.info("E2B Code Adapter initialized")

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int | None = None,
        session_id: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Execute code in E2B cloud sandbox.

        Args:
            code: Code to execute
            language: Programming language ("python" or "javascript")
            timeout: Execution timeout in seconds
            session_id: Optional session ID to reuse sandbox
            **kwargs: Additional execution options

        Returns:
            Dict containing:
                - success: bool
                - output: str (stdout)
                - error: Optional[str] (stderr)
                - results: List of execution results
                - execution_time: float
                - backend: str ("e2b_cloud")
        """
        timeout = timeout or self.default_timeout

        try:
            logger.info(f"Executing {language} code in E2B sandbox (timeout={timeout}s)")

            # Create sandbox session
            async with Sandbox(api_key=self.api_key) as sandbox:
                logger.debug(f"E2B sandbox created: {sandbox.id}")

                # Execute code
                execution = await sandbox.notebook.exec_cell(
                    code,
                    timeout=timeout,
                )

                # Process results
                output_lines = []
                error_lines = []
                results = []

                for result in execution.results:
                    if result.text:
                        output_lines.append(result.text)
                    if result.html:
                        results.append({"type": "html", "content": result.html})
                    if result.png:
                        results.append({"type": "image", "format": "png", "data": result.png})
                    if result.svg:
                        results.append({"type": "image", "format": "svg", "data": result.svg})
                    if result.json:
                        results.append({"type": "json", "content": result.json})

                # Collect logs
                for log in execution.logs.stdout:
                    output_lines.append(log)
                for log in execution.logs.stderr:
                    error_lines.append(log)

                success = execution.error is None

                response = {
                    "success": success,
                    "output": "\n".join(output_lines),
                    "error": execution.error.value if execution.error else None,
                    "results": results,
                    "execution_time": execution.execution_time_ms / 1000.0 if execution.execution_time_ms else 0,
                    "backend": "e2b_cloud",
                    "sandbox_id": sandbox.id,
                }

                if error_lines:
                    response["stderr"] = "\n".join(error_lines)

                logger.info(f"E2B execution completed: success={success}")
                return response

        except TimeoutError:
            logger.error(f"E2B execution timeout after {timeout}s")
            return {
                "success": False,
                "output": "",
                "error": f"Execution timeout after {timeout} seconds",
                "results": [],
                "execution_time": timeout,
                "backend": "e2b_cloud",
            }
        except Exception as e:
            logger.error(f"E2B execution failed: {str(e)}")
            return {
                "success": False,
                "output": "",
                "error": f"E2B execution error: {str(e)}",
                "results": [],
                "execution_time": 0,
                "backend": "e2b_cloud",
            }

    async def execute_python(
        self,
        code: str,
        timeout: int | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Execute Python code in E2B sandbox.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary
        """
        return await self.execute_code(code, language="python", timeout=timeout, **kwargs)

    async def execute_javascript(
        self,
        code: str,
        timeout: int | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Execute JavaScript code in E2B sandbox.

        Args:
            code: JavaScript code to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary
        """
        return await self.execute_code(code, language="javascript", timeout=timeout, **kwargs)

    async def install_packages(
        self,
        packages: list[str],
        language: str = "python",
        **kwargs
    ) -> dict[str, Any]:
        """
        Install packages in E2B sandbox.

        Args:
            packages: List of package names to install
            language: Language ("python" or "javascript")
            **kwargs: Additional options

        Returns:
            Installation result dictionary
        """
        if language == "python":
            install_code = f"!pip install {' '.join(packages)}"
        elif language == "javascript":
            install_code = f"!npm install {' '.join(packages)}"
        else:
            raise ValueError(f"Unsupported language: {language}")

        logger.info(f"Installing {language} packages in E2B: {packages}")
        return await self.execute_code(install_code, language=language, **kwargs)

    def is_available(self) -> bool:
        """
        Check if E2B adapter is available and properly configured.

        Returns:
            True if E2B API key is configured
        """
        import os
        return self.api_key is not None or os.getenv("E2B_API_KEY") is not None
