"""Code generation tools for the unified agent."""

import builtins
import contextlib
import time
from typing import Any

from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


def register_coder_tools(registry: ToolRegistry) -> None:
    """Register code generation tools."""

    async def coder_generate(description: str, language: str = "python") -> dict[str, Any]:
        """Generate code from a description."""
        try:
            from src.infrastructure.agents.advanced.code_generator_agent import (
                CodeGenerationRequest,
                CodeGeneratorAgent,
            )

            agent = CodeGeneratorAgent()
            await agent.initialize()

            # Create request
            request = CodeGenerationRequest(
                request_id=f"unified_{int(time.time())}",
                language=language,
                description=description,
            )

            result = await agent.generate_code(request)

            return {
                "success": True,
                "code": result.code,
                "language": language,
                "quality_score": result.quality_score,
                "file_structure": result.file_structure,
                "tests": result.tests[:2] if result.tests else [],  # First 2 tests
                "documentation": result.documentation[:500],  # Truncated
            }
        except Exception as e:
            logger.error(f"Coder generate failed: {e}")
            return {"success": False, "error": str(e)}

    async def coder_execute(code: str) -> dict[str, Any]:
        """Execute Python code safely in a subprocess."""
        try:
            import os
            import subprocess
            import tempfile

            # Write code to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name

            try:
                # Execute with timeout
                result = subprocess.run(
                    ['python3', temp_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                }
            finally:
                # Clean up temp file
                with contextlib.suppress(builtins.BaseException):
                    os.unlink(temp_path)

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timed out (30s)"}
        except Exception as e:
            logger.error(f"Coder execute failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tools
    registry._tools["coder.generate"] = Tool(
        name="coder.generate",
        func=coder_generate,
        category=ToolCategory.CODER,
        description="Generate code from natural language description (Python, JavaScript)",
    )

    registry._tools["coder.execute"] = Tool(
        name="coder.execute",
        func=coder_execute,
        category=ToolCategory.CODER,
        description="Execute Python code safely and get output",
    )

    logger.debug("Registered 2 coder tools")
