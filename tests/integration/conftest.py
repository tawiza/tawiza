"""Configuration for integration tests.

Integration tests require external services (Ollama, PostgreSQL, MinIO, etc.)
They are skipped by default unless the service is available.
Run with: pytest -m integration --run-integration
"""

import shutil
import subprocess

import pytest


def _is_service_available(url: str, timeout: float = 2.0) -> bool:
    """Check if an HTTP service is available."""
    try:
        import httpx

        response = httpx.get(url, timeout=timeout)
        return response.status_code < 500
    except Exception:
        return False


def _is_cli_available(cmd: str) -> bool:
    """Check if a CLI command is available in PATH."""
    return shutil.which(cmd) is not None


def _is_postgres_available() -> bool:
    """Check if PostgreSQL is available."""
    try:
        import asyncio

        import asyncpg

        async def _check():
            try:
                conn = await asyncpg.connect(
                    host="localhost",
                    port=5433,
                    user="tawiza",
                    database="tawiza",
                    timeout=2,
                )
                await conn.close()
                return True
            except Exception:
                return False

        return asyncio.get_event_loop().run_until_complete(_check())
    except Exception:
        return False


# Service availability flags
_ollama_available = _is_service_available("http://localhost:11434/api/tags")
_api_available = _is_service_available("http://localhost:8000/health")
_minio_available = _is_service_available("http://localhost:9000/minio/health/live")
_cli_available = _is_cli_available("tawiza")

# Skip reasons
skip_no_ollama = pytest.mark.skipif(
    not _ollama_available, reason="Ollama service not available"
)
skip_no_api = pytest.mark.skipif(
    not _api_available, reason="API server not running"
)
skip_no_minio = pytest.mark.skipif(
    not _minio_available, reason="MinIO service not available"
)
skip_no_cli = pytest.mark.skipif(
    not _cli_available, reason="tawiza CLI not installed"
)
