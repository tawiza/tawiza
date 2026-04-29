"""Unit tests for src.interfaces.api.v1.tajine.routes.

Targets the routes that don't require a real TAJINEAgent / DB / WebSocket:
- GET /cognitive/levels (static response)
- GET /health (degraded fallback when agent fails)
- GET /knowledge/stats (mocked agent)
- POST /knowledge/query (mocked agent)
- POST /cognitive/process (mocked agent)
- CRUD /conversations (in-memory dict, no agent needed)
- GET /analyses/recent (in-memory _running_tasks)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.interfaces.api.v1.tajine import routes as tajine_routes


@pytest.fixture
def app():
    """Build a minimal FastAPI app exposing only the tajine router."""
    application = FastAPI()
    application.include_router(tajine_routes.router)
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_in_memory_state():
    """Reset module-level dicts before/after each test for isolation."""
    tajine_routes._conversations.clear()
    tajine_routes._running_tasks.clear()
    yield
    tajine_routes._conversations.clear()
    tajine_routes._running_tasks.clear()


class TestCognitiveLevels:
    """GET /api/v1/tajine/cognitive/levels — static metadata."""

    def test_returns_five_levels(self, client):
        response = client.get("/api/v1/tajine/cognitive/levels")
        assert response.status_code == 200
        data = response.json()
        assert "levels" in data
        assert len(data["levels"]) == 5

    def test_each_level_has_required_fields(self, client):
        response = client.get("/api/v1/tajine/cognitive/levels")
        for level in response.json()["levels"]:
            assert "level" in level
            assert "name" in level
            assert "description" in level
            assert "outputs" in level
            assert isinstance(level["outputs"], list)

    def test_levels_are_numbered_one_to_five(self, client):
        response = client.get("/api/v1/tajine/cognitive/levels")
        levels = [item["level"] for item in response.json()["levels"]]
        assert levels == [1, 2, 3, 4, 5]


class TestHealthCheck:
    """GET /api/v1/tajine/health — agent reachability."""

    def test_healthy_when_agent_initializes(self, client):
        with patch.object(tajine_routes, "get_tajine_agent", new=AsyncMock(return_value=MagicMock())):
            response = client.get("/api/v1/tajine/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["agent"] == "TAJINE"
        assert "capabilities" in data
        assert "running_tasks" in data
        assert data["running_tasks"] == 0

    def test_degraded_when_agent_fails(self, client):
        with patch.object(
            tajine_routes,
            "get_tajine_agent",
            new=AsyncMock(side_effect=Exception("agent down")),
        ):
            response = client.get("/api/v1/tajine/health")
        # Health route catches the exception and returns degraded (200, not 500)
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"

    def test_running_tasks_count_reflects_state(self, client):
        tajine_routes._running_tasks["task-1"] = {"status": "running"}
        tajine_routes._running_tasks["task-2"] = {"status": "completed"}
        with patch.object(tajine_routes, "get_tajine_agent", new=AsyncMock(return_value=MagicMock())):
            response = client.get("/api/v1/tajine/health")
        assert response.json()["running_tasks"] == 2


class TestKnowledgeStats:
    """GET /api/v1/tajine/knowledge/stats."""

    def test_not_initialized_when_kg_missing(self, client):
        agent = MagicMock(spec=[])  # No knowledge_graph attribute
        with patch.object(tajine_routes, "get_tajine_agent", new=AsyncMock(return_value=agent)):
            response = client.get("/api/v1/tajine/knowledge/stats")
        assert response.status_code == 200
        assert response.json()["status"] == "not_initialized"

    def test_returns_active_stats_when_kg_present(self, client):
        kg = MagicMock()
        kg.entity_count = 42
        kg.triple_count = 100
        kg.source_count = 7
        agent = MagicMock()
        agent.knowledge_graph = kg
        with patch.object(tajine_routes, "get_tajine_agent", new=AsyncMock(return_value=agent)):
            response = client.get("/api/v1/tajine/knowledge/stats")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["entities"] == 42
        assert body["triples"] == 100
        assert body["sources"] == 7

    def test_returns_500_on_unexpected_error(self, client):
        with patch.object(
            tajine_routes,
            "get_tajine_agent",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            response = client.get("/api/v1/tajine/knowledge/stats")
        assert response.status_code == 500


class TestKnowledgeQuery:
    """POST /api/v1/tajine/knowledge/query."""

    def test_rejects_empty_query(self, client):
        # No subject / predicate / object → 400
        response = client.post("/api/v1/tajine/knowledge/query")
        assert response.status_code == 400


class TestCognitiveProcess:
    """POST /api/v1/tajine/cognitive/process."""

    def test_runs_with_default_levels(self, client):
        agent = MagicMock()
        agent.cognitive_process = AsyncMock(
            return_value={"results": {"discovery": "found 3 signals"}, "confidence": 0.85}
        )
        with patch.object(tajine_routes, "get_tajine_agent", new=AsyncMock(return_value=agent)):
            response = client.post(
                "/api/v1/tajine/cognitive/process", json={"input": "test data"}
            )
        assert response.status_code == 200
        body = response.json()
        assert body["levels_processed"] == [1, 2, 3, 4, 5]
        assert body["confidence"] == 0.85
        assert body["results"] == {"discovery": "found 3 signals"}

    def test_accepts_custom_levels(self, client):
        agent = MagicMock()
        agent.cognitive_process = AsyncMock(return_value={"results": {}, "confidence": 0.5})
        with patch.object(tajine_routes, "get_tajine_agent", new=AsyncMock(return_value=agent)):
            response = client.post(
                "/api/v1/tajine/cognitive/process?levels=1&levels=2",
                json={"input": "test"},
            )
        assert response.status_code == 200
        assert response.json()["levels_processed"] == [1, 2]

    def test_returns_500_on_agent_error(self, client):
        with patch.object(
            tajine_routes,
            "get_tajine_agent",
            new=AsyncMock(side_effect=Exception("crash")),
        ):
            response = client.post("/api/v1/tajine/cognitive/process", json={})
        assert response.status_code == 500


class TestConversationsCRUD:
    """CRUD on /api/v1/tajine/conversations — fully in-memory."""

    def test_create_conversation_minimal(self, client):
        response = client.post("/api/v1/tajine/conversations", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["id"].startswith("conv-")
        assert body["status"] == "pending"
        assert body["messages"] == []
        assert body["cognitive_level"] == "analytical"
        assert body["department_code"] is None

    def test_create_conversation_with_metadata(self, client):
        response = client.post(
            "/api/v1/tajine/conversations",
            json={"department_code": "75", "cognitive_level": "strategic"},
        )
        body = response.json()
        assert body["department_code"] == "75"
        assert body["cognitive_level"] == "strategic"

    def test_list_empty(self, client):
        response = client.get("/api/v1/tajine/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_conversations(self, client):
        client.post("/api/v1/tajine/conversations", json={"department_code": "75"})
        client.post("/api/v1/tajine/conversations", json={"department_code": "13"})
        response = client.get("/api/v1/tajine/conversations")
        assert len(response.json()) == 2

    def test_list_filters_by_department(self, client):
        client.post("/api/v1/tajine/conversations", json={"department_code": "75"})
        client.post("/api/v1/tajine/conversations", json={"department_code": "13"})
        response = client.get("/api/v1/tajine/conversations?dept=75")
        body = response.json()
        assert len(body) == 1
        assert body[0]["department_code"] == "75"

    def test_list_pagination(self, client):
        for i in range(5):
            client.post("/api/v1/tajine/conversations", json={})
        response = client.get("/api/v1/tajine/conversations?limit=2&offset=1")
        assert len(response.json()) == 2

    def test_get_conversation_by_id(self, client):
        created = client.post("/api/v1/tajine/conversations", json={}).json()
        response = client.get(f"/api/v1/tajine/conversations/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_conversation_404(self, client):
        response = client.get("/api/v1/tajine/conversations/conv-doesnotexist")
        assert response.status_code == 404

    def test_delete_conversation(self, client):
        created = client.post("/api/v1/tajine/conversations", json={}).json()
        response = client.delete(f"/api/v1/tajine/conversations/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]
        # Confirm deletion
        followup = client.get(f"/api/v1/tajine/conversations/{created['id']}")
        assert followup.status_code == 404

    def test_delete_unknown_returns_404(self, client):
        response = client.delete("/api/v1/tajine/conversations/conv-doesnotexist")
        assert response.status_code == 404


class TestConversationMessages:
    """POST /api/v1/tajine/conversations/{id}/messages."""

    def _create_conv(self, client) -> str:
        return client.post("/api/v1/tajine/conversations", json={}).json()["id"]

    def test_add_user_message_sets_query_preview(self, client):
        conv_id = self._create_conv(client)
        client.post(
            f"/api/v1/tajine/conversations/{conv_id}/messages",
            json={"role": "user", "content": "What is the territorial health?"},
        )
        conv = client.get(f"/api/v1/tajine/conversations/{conv_id}").json()
        assert conv["query_preview"].startswith("What is the territorial health?")
        assert len(conv["messages"]) == 1

    def test_add_assistant_message_marks_completed(self, client):
        conv_id = self._create_conv(client)
        client.post(
            f"/api/v1/tajine/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "Analysis result..."},
        )
        conv = client.get(f"/api/v1/tajine/conversations/{conv_id}").json()
        assert conv["status"] == "completed"

    def test_long_user_message_truncated_to_preview(self, client):
        conv_id = self._create_conv(client)
        long_content = "A" * 200
        client.post(
            f"/api/v1/tajine/conversations/{conv_id}/messages",
            json={"role": "user", "content": long_content},
        )
        conv = client.get(f"/api/v1/tajine/conversations/{conv_id}").json()
        # Preview is 100 chars + "..." appended
        assert conv["query_preview"].endswith("...")
        assert len(conv["query_preview"]) == 103

    def test_invalid_role_rejected(self, client):
        conv_id = self._create_conv(client)
        response = client.post(
            f"/api/v1/tajine/conversations/{conv_id}/messages",
            json={"role": "system", "content": "x"},  # only user/assistant allowed
        )
        assert response.status_code == 422

    def test_message_to_unknown_conversation_404(self, client):
        response = client.post(
            "/api/v1/tajine/conversations/conv-nope/messages",
            json={"role": "user", "content": "x"},
        )
        assert response.status_code == 404


class TestAnalysesRecent:
    """GET /api/v1/tajine/analyses/recent."""

    def test_empty_when_no_tasks(self, client):
        response = client.get("/api/v1/tajine/analyses/recent")
        assert response.status_code == 200
        assert response.json() == []

    def test_skips_running_tasks(self, client):
        tajine_routes._running_tasks["t-running"] = {
            "status": "running",
            "prompt": "test",
            "created_at": "2026-04-29T10:00:00",
        }
        response = client.get("/api/v1/tajine/analyses/recent")
        assert response.json() == []

    def test_includes_completed_tasks(self, client):
        tajine_routes._running_tasks["t-1"] = {
            "status": "completed",
            "prompt": "Analyze Paris",
            "created_at": "2026-04-29T10:00:00",
            "completed_at": "2026-04-29T10:00:30",
        }
        response = client.get("/api/v1/tajine/analyses/recent")
        body = response.json()
        assert len(body) == 1
        assert body[0]["status"] == "completed"
        assert body[0]["department"] == "75 - Paris"  # Detected from prompt
        assert body[0]["duration"] == "30.0s"

    def test_failed_tasks_marked_as_error(self, client):
        tajine_routes._running_tasks["t-fail"] = {
            "status": "failed",
            "prompt": "Some query",
            "created_at": "2026-04-29T11:00:00",
            "completed_at": "2026-04-29T11:00:05",
        }
        response = client.get("/api/v1/tajine/analyses/recent")
        body = response.json()
        assert len(body) == 1
        assert body[0]["status"] == "error"

    def test_lyon_detected_from_prompt(self, client):
        tajine_routes._running_tasks["t-lyon"] = {
            "status": "completed",
            "prompt": "Quels signaux pour Lyon",
            "created_at": "2026-04-29T11:00:00",
            "completed_at": "2026-04-29T11:00:05",
        }
        response = client.get("/api/v1/tajine/analyses/recent")
        assert response.json()[0]["department"] == "69 - Rhone"

    def test_long_prompt_truncated_in_query(self, client):
        long_prompt = "Q" * 200
        tajine_routes._running_tasks["t-long"] = {
            "status": "completed",
            "prompt": long_prompt,
            "created_at": "2026-04-29T11:00:00",
            "completed_at": "2026-04-29T11:00:05",
        }
        response = client.get("/api/v1/tajine/analyses/recent")
        body = response.json()
        assert body[0]["query"].endswith("...")
        assert len(body[0]["query"]) == 103

    def test_limit_query_param(self, client):
        for i in range(10):
            tajine_routes._running_tasks[f"t-{i}"] = {
                "status": "completed",
                "prompt": f"task {i}",
                "created_at": f"2026-04-29T1{i}:00:00",
                "completed_at": f"2026-04-29T1{i}:00:05",
            }
        response = client.get("/api/v1/tajine/analyses/recent?limit=3")
        assert len(response.json()) == 3

    def test_default_department_when_no_match(self, client):
        tajine_routes._running_tasks["t-x"] = {
            "status": "completed",
            "prompt": "general analysis",
            "created_at": "2026-04-29T11:00:00",
            "completed_at": "2026-04-29T11:00:05",
        }
        response = client.get("/api/v1/tajine/analyses/recent")
        assert response.json()[0]["department"] == "France"

    def test_territory_in_context_overrides_default(self, client):
        tajine_routes._running_tasks["t-ctx"] = {
            "status": "completed",
            "prompt": "general",
            "context": {"territory": "Marseille"},
            "created_at": "2026-04-29T11:00:00",
            "completed_at": "2026-04-29T11:00:05",
        }
        response = client.get("/api/v1/tajine/analyses/recent")
        assert response.json()[0]["department"] == "Marseille"
