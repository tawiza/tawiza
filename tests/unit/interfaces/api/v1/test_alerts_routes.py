"""Tests for alerts API routes."""

import pytest
from fastapi.testclient import TestClient

from src.application.services.alert_service import AlertService
from src.interfaces.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    # Reset singleton
    AlertService._instance = None
    return TestClient(app)


class TestAlertsEndpoints:
    """Test alerts API endpoints."""

    def test_list_alerts(self, client):
        """Should list alerts."""
        response = client.get("/alerts/")
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data

    def test_list_alerts_with_filters(self, client):
        """Should accept filter parameters."""
        response = client.get("/alerts/?status=new&limit=10")
        assert response.status_code == 200

    def test_get_stats(self, client):
        """Should return stats."""
        response = client.get("/alerts/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_type" in data

    def test_list_types(self, client):
        """Should list alert types."""
        response = client.get("/alerts/types")
        assert response.status_code == 200
        types = response.json()
        assert isinstance(types, list)
        assert "enterprise_creation" in types

    def test_list_severities(self, client):
        """Should list severities."""
        response = client.get("/alerts/severities")
        assert response.status_code == 200
        severities = response.json()
        assert "info" in severities
        assert "warning" in severities
        assert "critical" in severities

    def test_mark_read_nonexistent(self, client):
        """Should handle nonexistent alert."""
        response = client.post("/alerts/nonexistent-id/read")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
