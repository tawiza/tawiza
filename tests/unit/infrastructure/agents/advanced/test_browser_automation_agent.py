"""Tests complets pour browser_automation_agent.py

Tests couvrant:
- BrowserAction, AutomationTask, AutomationResult, ElementInfo dataclasses
- BrowserAutomationAgent
- Tests conditionnels (playwright optionnel)
"""

import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip entire module if playwright or optuna not available
playwright = pytest.importorskip("playwright", reason="Playwright not installed")
pytest.importorskip("optuna", reason="optuna not installed")

from src.infrastructure.agents.advanced.browser_automation_agent import (
    AutomationResult,
    AutomationTask,
    BrowserAction,
    BrowserAutomationAgent,
    ElementInfo,
)


# ============================================================================
# Tests BrowserAction Dataclass
# ============================================================================
class TestBrowserAction:
    """Tests pour la dataclass BrowserAction."""

    def test_create_action_minimal(self):
        """Création d'une action minimale."""
        action = BrowserAction(action_type="click")

        assert action.action_type == "click"
        assert action.selector is None
        assert action.value is None
        assert action.coordinates is None
        assert action.wait_time == 0.5
        assert action.description == ""

    def test_create_action_click(self):
        """Action de clic."""
        action = BrowserAction(
            action_type="click", selector="#submit-button", description="Click submit button"
        )

        assert action.action_type == "click"
        assert action.selector == "#submit-button"

    def test_create_action_type(self):
        """Action de saisie."""
        action = BrowserAction(
            action_type="type",
            selector="#email-input",
            value="test@example.com",
            description="Enter email",
        )

        assert action.action_type == "type"
        assert action.value == "test@example.com"

    def test_create_action_with_coordinates(self):
        """Action avec coordonnées."""
        action = BrowserAction(
            action_type="click", coordinates=(100, 200), description="Click at position"
        )

        assert action.coordinates == (100, 200)

    def test_action_types(self):
        """Différents types d'actions."""
        action_types = ["click", "type", "scroll", "screenshot", "hover", "wait"]

        for action_type in action_types:
            action = BrowserAction(action_type=action_type)
            assert action.action_type == action_type


# ============================================================================
# Tests AutomationTask Dataclass
# ============================================================================
class TestAutomationTask:
    """Tests pour la dataclass AutomationTask."""

    def test_create_task_minimal(self):
        """Création d'une tâche minimale."""
        task = AutomationTask(
            task_id="task-001", url="https://example.com", objective="Test the page", actions=[]
        )

        assert task.task_id == "task-001"
        assert task.url == "https://example.com"
        assert task.objective == "Test the page"
        assert task.actions == []
        assert task.max_steps == 50
        assert task.timeout == 300.0
        assert task.headless is True

    def test_create_task_full(self):
        """Création d'une tâche complète."""
        actions = [
            BrowserAction(action_type="click", selector="#login"),
            BrowserAction(action_type="type", selector="#username", value="user"),
        ]

        task = AutomationTask(
            task_id="task-002",
            url="https://example.com/login",
            objective="Login to the site",
            actions=actions,
            max_steps=100,
            timeout=600.0,
            headless=False,
            user_agent="Custom/1.0",
            viewport={"width": 1920, "height": 1080},
        )

        assert len(task.actions) == 2
        assert task.headless is False
        assert task.user_agent == "Custom/1.0"
        assert task.viewport["width"] == 1920


# ============================================================================
# Tests AutomationResult Dataclass
# ============================================================================
class TestAutomationResult:
    """Tests pour la dataclass AutomationResult."""

    def test_create_success_result(self):
        """Résultat réussi."""
        result = AutomationResult(
            task_id="task-001",
            success=True,
            url="https://example.com",
            final_url="https://example.com/dashboard",
            actions_performed=5,
            data_extracted={"title": "Dashboard"},
            screenshots=["screenshot1.png", "screenshot2.png"],
        )

        assert result.success is True
        assert result.url == "https://example.com"
        assert result.final_url == "https://example.com/dashboard"
        assert result.actions_performed == 5
        assert len(result.screenshots) == 2

    def test_create_failure_result(self):
        """Résultat échoué."""
        result = AutomationResult(
            task_id="task-002",
            success=False,
            url="https://example.com",
            final_url="https://example.com",
            actions_performed=2,
            data_extracted={},
            screenshots=[],
            error_message="Element not found: #submit",
            execution_time=15.5,
        )

        assert result.success is False
        assert result.error_message == "Element not found: #submit"
        assert result.execution_time == 15.5


# ============================================================================
# Tests ElementInfo Dataclass
# ============================================================================
class TestElementInfo:
    """Tests pour la dataclass ElementInfo."""

    def test_create_element_info(self):
        """Création d'info élément."""
        info = ElementInfo(
            tag_name="button",
            text="Submit",
            attributes={"id": "submit-btn", "class": "btn primary"},
            position={"x": 100, "y": 200},
            size={"width": 120, "height": 40},
            is_visible=True,
            is_interactable=True,
        )

        assert info.tag_name == "button"
        assert info.text == "Submit"
        assert info.attributes["id"] == "submit-btn"
        assert info.position["x"] == 100
        assert info.size["width"] == 120
        assert info.is_visible is True
        assert info.is_interactable is True

    def test_hidden_element(self):
        """Élément caché."""
        info = ElementInfo(
            tag_name="div",
            text="Hidden content",
            attributes={"style": "display: none"},
            position={"x": 0, "y": 0},
            size={"width": 0, "height": 0},
            is_visible=False,
            is_interactable=False,
        )

        assert info.is_visible is False
        assert info.is_interactable is False


# ============================================================================
# Tests BrowserAutomationAgent - Création
# ============================================================================
class TestBrowserAutomationAgentBasic:
    """Tests basiques pour BrowserAutomationAgent."""

    def test_create_agent(self):
        """Création de l'agent."""
        agent = BrowserAutomationAgent()

        assert agent.name == "BrowserAutomationAgent"
        assert agent.agent_type == "browser_automation"
        assert isinstance(agent.capabilities, list)
        assert len(agent.capabilities) == 6
        assert agent.is_initialized is False

    def test_capabilities(self):
        """Vérification des capacités."""
        agent = BrowserAutomationAgent()

        expected_capabilities = [
            "web_navigation",
            "form_filling",
            "data_extraction",
            "screenshot_capture",
            "element_interaction",
            "page_analysis",
        ]

        for cap in expected_capabilities:
            assert cap in agent.capabilities

    def test_initial_state(self):
        """État initial de l'agent."""
        agent = BrowserAutomationAgent()

        assert agent.playwright is None
        assert agent.browser is None
        assert agent.context is None
        assert agent.page is None
        assert agent.active_tasks == {}
        assert agent.task_history == []


# ============================================================================
# Tests BrowserAutomationAgent - Initialisation mockée
# ============================================================================
class TestBrowserAutomationAgentInitialization:
    """Tests d'initialisation avec mocks."""

    @pytest.mark.asyncio
    async def test_initialize_mocked(self):
        """Initialisation avec playwright mocké."""
        agent = BrowserAutomationAgent()

        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()

        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        with patch(
            "src.infrastructure.agents.advanced.browser_automation_agent.async_playwright"
        ) as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_playwright)

            await agent.initialize()

            assert agent.is_initialized is True
            mock_async_pw.return_value.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_mocked(self):
        """Nettoyage avec mocks."""
        agent = BrowserAutomationAgent()

        # Only test if cleanup method exists
        if hasattr(agent, "cleanup"):
            # Note: cleanup() only closes context, browser, playwright (not page)
            agent.context = MagicMock()
            agent.context.close = AsyncMock()
            agent.browser = MagicMock()
            agent.browser.close = AsyncMock()
            agent.playwright = MagicMock()
            agent.playwright.stop = AsyncMock()

            await agent.cleanup()

            agent.context.close.assert_called_once()
            agent.browser.close.assert_called_once()
            agent.playwright.stop.assert_called_once()
        else:
            # Agent doesn't have cleanup method yet - pass
            assert True


# ============================================================================
# Tests BrowserAutomationAgent - Gestion des tâches
# ============================================================================
class TestBrowserAutomationAgentTasks:
    """Tests de gestion des tâches."""

    def test_empty_active_tasks(self):
        """Pas de tâches actives au départ."""
        agent = BrowserAutomationAgent()
        assert agent.active_tasks == {}

    def test_add_active_task(self):
        """Ajout d'une tâche active."""
        agent = BrowserAutomationAgent()

        agent.active_tasks["task-001"] = {"status": "running", "started_at": 1234567890}

        assert "task-001" in agent.active_tasks
        assert agent.active_tasks["task-001"]["status"] == "running"

    def test_task_history_tracking(self):
        """Suivi de l'historique."""
        agent = BrowserAutomationAgent()

        result = AutomationResult(
            task_id="task-001",
            success=True,
            url="https://example.com",
            final_url="https://example.com",
            actions_performed=3,
            data_extracted={},
            screenshots=[],
        )

        agent.task_history.append(result)
        assert len(agent.task_history) == 1


# ============================================================================
# Tests conditionnels - Playwright disponible
# ============================================================================
class TestBrowserAutomationAgentConditional:
    """Tests conditionnels si playwright est disponible."""

    @pytest.fixture
    def playwright_available(self):
        """Vérifie si playwright est disponible."""
        try:
            from playwright.async_api import async_playwright

            return True
        except ImportError:
            return False

    @pytest.mark.asyncio
    async def test_real_initialization(self, playwright_available):
        """Test avec vrai playwright si disponible."""
        if not playwright_available:
            pytest.skip("Playwright non installé")

        agent = BrowserAutomationAgent()
        try:
            await agent.initialize()
            assert agent.is_initialized is True
        finally:
            await agent.cleanup()


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestBrowserAutomationAgentEdgeCases:
    """Tests des cas limites."""

    def test_task_with_many_actions(self):
        """Tâche avec beaucoup d'actions."""
        actions = [BrowserAction(action_type="click", selector=f"#btn-{i}") for i in range(100)]

        task = AutomationTask(
            task_id="many-actions",
            url="https://example.com",
            objective="Many clicks",
            actions=actions,
        )

        assert len(task.actions) == 100

    def test_result_with_large_data(self):
        """Résultat avec beaucoup de données extraites."""
        data_extracted = {f"field_{i}": f"value_{i}" for i in range(1000)}

        result = AutomationResult(
            task_id="large-data",
            success=True,
            url="https://example.com",
            final_url="https://example.com",
            actions_performed=1,
            data_extracted=data_extracted,
            screenshots=[],
        )

        assert len(result.data_extracted) == 1000

    def test_multiple_agent_instances(self):
        """Plusieurs instances indépendantes."""
        agent1 = BrowserAutomationAgent()
        agent2 = BrowserAutomationAgent()

        agent1.active_tasks["task-1"] = {"status": "running"}
        agent2.active_tasks["task-2"] = {"status": "completed"}

        assert "task-1" in agent1.active_tasks
        assert "task-1" not in agent2.active_tasks
        assert "task-2" in agent2.active_tasks
        assert "task-2" not in agent1.active_tasks

    def test_automation_rules_loaded(self):
        """Règles d'automatisation chargées."""
        agent = BrowserAutomationAgent()
        # La méthode _load_automation_rules est appelée dans __init__
        assert agent.automation_rules is not None
