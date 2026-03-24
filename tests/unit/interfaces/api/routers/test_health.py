"""Tests for health check router.

This module tests:
- Liveness probe
- Readiness probe
- Startup probe
- Full health check
- Health check functions
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.interfaces.api.routers.health import (
    DependencyHealth,
    FullHealthResponse,
    HealthStatus,
    check_disk_space,
    check_memory,
    get_uptime,
    mark_startup_complete,
)


class TestHealthStatus:
    """Test suite for HealthStatus model."""

    def test_health_status_fields(self):
        """HealthStatus should have required fields."""
        status = HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            uptime_seconds=100.5,
        )
        assert status.status == "healthy"
        assert status.uptime_seconds == 100.5
        assert status.version == "2.0.3"

    def test_health_status_custom_version(self):
        """HealthStatus should allow custom version."""
        status = HealthStatus(
            status="degraded",
            timestamp=datetime.utcnow().isoformat(),
            uptime_seconds=50.0,
            version="3.0.0",
        )
        assert status.version == "3.0.0"


class TestDependencyHealth:
    """Test suite for DependencyHealth model."""

    def test_dependency_health_minimal(self):
        """DependencyHealth should work with minimal fields."""
        health = DependencyHealth(
            name="database",
            status="up",
        )
        assert health.name == "database"
        assert health.status == "up"
        assert health.latency_ms is None

    def test_dependency_health_with_details(self):
        """DependencyHealth should include optional details."""
        health = DependencyHealth(
            name="redis",
            status="down",
            latency_ms=15.5,
            message="Connection refused",
            details={"host": "localhost", "port": 6379},
        )
        assert health.latency_ms == 15.5
        assert health.message == "Connection refused"
        assert health.details["host"] == "localhost"


class TestFullHealthResponse:
    """Test suite for FullHealthResponse model."""

    def test_full_health_response(self):
        """FullHealthResponse should contain dependencies."""
        response = FullHealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat(),
            version="2.0.3",
            uptime_seconds=100.0,
            dependencies=[
                DependencyHealth(name="db", status="up"),
                DependencyHealth(name="cache", status="up"),
            ],
        )
        assert len(response.dependencies) == 2
        assert response.dependencies[0].name == "db"


class TestStateFunctions:
    """Test suite for state management functions."""

    def test_get_uptime_returns_positive(self):
        """get_uptime should return positive value."""
        uptime = get_uptime()
        assert uptime >= 0

    def test_mark_startup_complete(self):
        """mark_startup_complete should set flag."""
        # Import the module to access the flag
        import src.interfaces.api.routers.health as health_module

        # Store original value
        original = health_module._startup_complete

        # Mark complete
        mark_startup_complete()
        assert health_module._startup_complete is True

        # Restore (for other tests)
        health_module._startup_complete = original


class TestCheckDiskSpace:
    """Test suite for check_disk_space function."""

    @pytest.mark.asyncio
    async def test_check_disk_space_healthy(self):
        """Should return healthy status when disk space is sufficient."""
        with patch("shutil.disk_usage") as mock_usage:
            # 100GB total, 50GB used, 50GB free
            mock_usage.return_value = (100 * 1024**3, 50 * 1024**3, 50 * 1024**3)

            result = await check_disk_space()

            assert result.name == "disk"
            assert result.status == "up"
            assert result.details["free_gb"] == pytest.approx(50.0, rel=0.1)

    @pytest.mark.asyncio
    async def test_check_disk_space_degraded(self):
        """Should return degraded status when disk space is low."""
        with patch("shutil.disk_usage") as mock_usage:
            # 100GB total, 97GB used, 3GB free
            mock_usage.return_value = (100 * 1024**3, 97 * 1024**3, 3 * 1024**3)

            result = await check_disk_space()

            assert result.status == "degraded"
            assert "Warning" in result.message

    @pytest.mark.asyncio
    async def test_check_disk_space_critical(self):
        """Should return down status when disk space is critical."""
        with patch("shutil.disk_usage") as mock_usage:
            # 100GB total, 99.5GB used, 0.5GB free
            mock_usage.return_value = (100 * 1024**3, 99.5 * 1024**3, 0.5 * 1024**3)

            result = await check_disk_space()

            assert result.status == "down"
            assert "Critical" in result.message

    @pytest.mark.asyncio
    async def test_check_disk_space_error(self):
        """Should handle errors gracefully."""
        with patch("shutil.disk_usage") as mock_usage:
            mock_usage.side_effect = OSError("Permission denied")

            result = await check_disk_space()

            assert result.status == "degraded"
            assert "Permission denied" in result.message


class TestCheckMemory:
    """Test suite for check_memory function."""

    @pytest.mark.asyncio
    async def test_check_memory_healthy(self):
        """Should return healthy status when memory is sufficient."""
        mock_memory = MagicMock()
        mock_memory.available = 10 * 1024**3  # 10GB
        mock_memory.percent = 50.0

        with patch("psutil.virtual_memory", return_value=mock_memory):
            result = await check_memory()

            assert result.name == "memory"
            assert result.status == "up"
            assert result.details["used_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_check_memory_degraded(self):
        """Should return degraded status when memory is high."""
        mock_memory = MagicMock()
        mock_memory.available = 2 * 1024**3  # 2GB
        mock_memory.percent = 90.0

        with patch("psutil.virtual_memory", return_value=mock_memory):
            result = await check_memory()

            assert result.status == "degraded"
            assert "Warning" in result.message

    @pytest.mark.asyncio
    async def test_check_memory_critical(self):
        """Should return down status when memory is critical."""
        mock_memory = MagicMock()
        mock_memory.available = 0.5 * 1024**3  # 0.5GB
        mock_memory.percent = 97.0

        with patch("psutil.virtual_memory", return_value=mock_memory):
            result = await check_memory()

            assert result.status == "down"
            assert "Critical" in result.message

    @pytest.mark.asyncio
    async def test_check_memory_error(self):
        """Should handle errors gracefully."""
        with patch("psutil.virtual_memory") as mock_memory:
            mock_memory.side_effect = Exception("psutil error")

            result = await check_memory()

            assert result.status == "degraded"
            assert "psutil error" in result.message


class TestHealthEndpointsIntegration:
    """Integration tests for health endpoints using FastAPI TestClient."""

    @pytest.fixture
    def test_client(self):
        """Create FastAPI test client."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.interfaces.api.routers.health import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_liveness_endpoint(self, test_client):
        """GET /health/live should return 200."""
        response = test_client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data

    def test_root_health_endpoint(self, test_client):
        """GET /health/ should return 200 (alias for live)."""
        response = test_client.get("/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_startup_endpoint_not_complete(self, test_client):
        """GET /health/startup should return 503 before startup complete."""
        import src.interfaces.api.routers.health as health_module

        original = health_module._startup_complete
        health_module._startup_complete = False

        try:
            response = test_client.get("/health/startup")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "starting"
        finally:
            health_module._startup_complete = original

    def test_startup_endpoint_complete(self, test_client):
        """GET /health/startup should return 200 after startup complete."""
        import src.interfaces.api.routers.health as health_module

        original = health_module._startup_complete
        health_module._startup_complete = True

        try:
            response = test_client.get("/health/startup")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
        finally:
            health_module._startup_complete = original
