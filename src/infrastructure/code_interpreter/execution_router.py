"""Smart Execution Router for Code Interpreter."""

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from loguru import logger

from .e2b_adapter import E2BCodeAdapter
from .open_interpreter_adapter import OpenInterpreterAdapter


class ExecutionBackend(StrEnum):
    """Execution backend options."""

    E2B_CLOUD = "e2b_cloud"
    OPEN_INTERPRETER = "open_interpreter"
    AUTO = "auto"


class ExecutionRouter:
    """
    Smart Router for Code Execution.

    Automatically selects the best execution backend based on:
    - Backend availability
    - Network connectivity
    - Execution requirements
    - User preferences
    """

    def __init__(
        self,
        e2b_api_key: str | None = None,
        default_backend: ExecutionBackend = ExecutionBackend.AUTO,
        prefer_cloud: bool = True,
        output_callback: Callable[[str, str], None] | None = None,
        **kwargs,
    ):
        """
        Initialize Execution Router.

        Args:
            e2b_api_key: E2B API key for cloud execution
            default_backend: Default backend to use (AUTO, E2B_CLOUD, OPEN_INTERPRETER)
            prefer_cloud: If True and both available, prefer E2B Cloud
            output_callback: Optional async callback for live terminal output
            **kwargs: Additional configuration options
        """
        self.e2b_adapter = E2BCodeAdapter(api_key=e2b_api_key, **kwargs)
        self.open_interpreter_adapter = OpenInterpreterAdapter(
            output_callback=output_callback, **kwargs
        )
        self.default_backend = default_backend
        self.prefer_cloud = prefer_cloud
        self.output_callback = output_callback

        logger.info(
            f"Execution Router initialized (default={default_backend}, prefer_cloud={prefer_cloud})"
        )

        # Log backend availability
        e2b_available = self.e2b_adapter.is_available()
        oi_available = self.open_interpreter_adapter.is_available()
        logger.info(f"E2B Cloud available: {e2b_available}")
        logger.info(f"Open Interpreter available: {oi_available}")

    def select_backend(
        self,
        backend: ExecutionBackend | None = None,
        require_cloud: bool = False,
        require_local: bool = False,
    ) -> ExecutionBackend:
        """
        Select the best execution backend.

        Args:
            backend: Explicitly requested backend (overrides auto-selection)
            require_cloud: If True, only allow cloud execution
            require_local: If True, only allow local execution

        Returns:
            Selected ExecutionBackend

        Raises:
            RuntimeError: If no suitable backend is available
        """
        # Explicit backend request
        if backend and backend != ExecutionBackend.AUTO:
            logger.debug(f"Explicit backend requested: {backend}")
            return backend

        # Check availability
        e2b_available = self.e2b_adapter.is_available()
        oi_available = self.open_interpreter_adapter.is_available()

        # Handle constraints
        if require_cloud and require_local:
            raise ValueError("Cannot require both cloud and local execution")

        if require_cloud:
            if e2b_available:
                logger.debug("Cloud required and E2B available")
                return ExecutionBackend.E2B_CLOUD
            else:
                raise RuntimeError("Cloud execution required but E2B is not available")

        if require_local:
            if oi_available:
                logger.debug("Local required and Open Interpreter available")
                return ExecutionBackend.OPEN_INTERPRETER
            else:
                raise RuntimeError("Local execution required but Open Interpreter is not available")

        # Auto-selection based on availability and preference
        if e2b_available and oi_available:
            # Both available - use preference
            selected = (
                ExecutionBackend.E2B_CLOUD
                if self.prefer_cloud
                else ExecutionBackend.OPEN_INTERPRETER
            )
            logger.debug(f"Both backends available, selected: {selected}")
            return selected

        elif e2b_available:
            logger.debug("Only E2B Cloud available")
            return ExecutionBackend.E2B_CLOUD

        elif oi_available:
            logger.debug("Only Open Interpreter available")
            return ExecutionBackend.OPEN_INTERPRETER

        else:
            raise RuntimeError("No execution backend available")

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        backend: ExecutionBackend | None = None,
        timeout: int | None = None,
        require_cloud: bool = False,
        require_local: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Execute code using the selected backend.

        Args:
            code: Code to execute
            language: Programming language
            backend: Explicitly requested backend (None for auto-select)
            timeout: Execution timeout in seconds
            require_cloud: If True, only use cloud execution
            require_local: If True, only use local execution
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary with:
                - success: bool
                - output: str
                - error: Optional[str]
                - results: List
                - execution_time: float
                - backend: str (actual backend used)

        Raises:
            RuntimeError: If no suitable backend is available
        """
        # Select backend
        selected_backend = self.select_backend(
            backend=backend,
            require_cloud=require_cloud,
            require_local=require_local,
        )

        logger.info(f"Executing {language} code with backend: {selected_backend}")

        # Execute with selected backend
        if selected_backend == ExecutionBackend.E2B_CLOUD:
            try:
                return await self.e2b_adapter.execute_code(
                    code=code, language=language, timeout=timeout, **kwargs
                )
            except Exception as e:
                logger.error(f"E2B execution failed: {e}")
                # Fallback to local if available and not required cloud
                if not require_cloud and self.open_interpreter_adapter.is_available():
                    logger.info("Falling back to Open Interpreter")
                    return await self.open_interpreter_adapter.execute_code(
                        code=code, language=language, timeout=timeout, **kwargs
                    )
                raise

        elif selected_backend == ExecutionBackend.OPEN_INTERPRETER:
            return await self.open_interpreter_adapter.execute_code(
                code=code, language=language, timeout=timeout, **kwargs
            )

        else:
            raise RuntimeError(f"Unsupported backend: {selected_backend}")

    async def execute_python(
        self, code: str, backend: ExecutionBackend | None = None, **kwargs
    ) -> dict[str, Any]:
        """
        Execute Python code.

        Args:
            code: Python code to execute
            backend: Execution backend (None for auto-select)
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary
        """
        return await self.execute_code(code, language="python", backend=backend, **kwargs)

    async def execute_javascript(
        self, code: str, backend: ExecutionBackend | None = None, **kwargs
    ) -> dict[str, Any]:
        """
        Execute JavaScript code.

        Args:
            code: JavaScript code to execute
            backend: Execution backend (None for auto-select)
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary
        """
        return await self.execute_code(code, language="javascript", backend=backend, **kwargs)

    async def execute_bash(
        self, code: str, backend: ExecutionBackend | None = None, **kwargs
    ) -> dict[str, Any]:
        """
        Execute Bash script.

        Args:
            code: Bash script to execute
            backend: Execution backend (None for auto-select)
            **kwargs: Additional execution options

        Returns:
            Execution result dictionary
        """
        return await self.execute_code(code, language="bash", backend=backend, **kwargs)

    def get_backend_status(self) -> dict[str, Any]:
        """
        Get status of all execution backends.

        Returns:
            Dict with backend availability and configuration
        """
        return {
            "e2b_cloud": {
                "available": self.e2b_adapter.is_available(),
                "adapter": "E2BCodeAdapter",
            },
            "open_interpreter": {
                "available": self.open_interpreter_adapter.is_available(),
                "adapter": "OpenInterpreterAdapter",
            },
            "default_backend": self.default_backend,
            "prefer_cloud": self.prefer_cloud,
        }
