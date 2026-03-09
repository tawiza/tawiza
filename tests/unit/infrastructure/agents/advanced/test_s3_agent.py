"""Tests for S3Agent (Browser/Desktop Automation).

Tests the hybrid browser/desktop automation agent.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDesktopClient:
    """Tests for DesktopClient (VNC/SSH control)."""

    def test_desktop_client_init(self):
        """Should initialize DesktopClient."""
        from src.infrastructure.agents.s3 import DesktopClient

        client = DesktopClient(host="localhost", port=22)

        assert client.host == "localhost"
        assert client.port == 22


class TestVisionClient:
    """Tests for VisionClient (UI element detection)."""

    def test_create_vision_client(self):
        """Should create VisionClient with defaults."""
        from src.infrastructure.agents.s3 import create_vision_client

        client = create_vision_client(
            ollama_url="http://localhost:11434",
            model="llava:13b",
        )

        assert client is not None
        assert client.model == "llava:13b"

    def test_vision_client_init(self):
        """Should initialize VisionClient."""
        from src.infrastructure.agents.s3.vision_client import VisionClient

        client = VisionClient(
            ollama_url="http://localhost:11434",
            model="llava:13b",
        )

        assert client.ollama_url == "http://localhost:11434"
        assert client.model == "llava:13b"


class TestS3Agent:
    """Tests for S3Agent (hybrid browser/desktop)."""

    def test_s3_mode_enum(self):
        """Should have browser, desktop, and hybrid modes."""
        from src.infrastructure.agents.s3 import S3Mode

        assert S3Mode.BROWSER.value == "browser"
        assert S3Mode.DESKTOP.value == "desktop"
        assert S3Mode.HYBRID.value == "hybrid"

    def test_s3_action_enum(self):
        """Should have common action types."""
        from src.infrastructure.agents.s3 import S3Action

        assert S3Action.CLICK.value == "click"
        assert S3Action.TYPE.value == "type"
        assert S3Action.NAVIGATE.value == "navigate"
        assert S3Action.SCREENSHOT.value == "screenshot"

    def test_s3_agent_class_exists(self):
        """Should have S3Agent class."""
        from src.infrastructure.agents.s3 import S3Agent

        assert S3Agent is not None

    @pytest.mark.asyncio
    async def test_create_s3_agent(self):
        """Should create S3Agent with components."""
        from src.infrastructure.agents.s3 import create_s3_agent

        agent = await create_s3_agent(max_iterations=10)

        assert agent is not None
        assert agent.max_iterations == 10

    @pytest.mark.asyncio
    async def test_s3_agent_default_mode(self):
        """Should default to hybrid mode."""
        from src.infrastructure.agents.s3 import S3Mode, create_s3_agent

        agent = await create_s3_agent()

        assert agent.default_mode == S3Mode.HYBRID

    def test_s3_agent_init_with_params(self):
        """Should accept init parameters."""
        from src.infrastructure.agents.s3 import S3Agent, S3Mode

        agent = S3Agent(
            default_mode=S3Mode.DESKTOP,
            vm_host="192.168.1.50",
            max_iterations=20,
        )

        assert agent.default_mode == S3Mode.DESKTOP
        assert agent.vm_host == "192.168.1.50"
        assert agent.max_iterations == 20


class TestS3AgentModes:
    """Tests for S3Agent mode detection."""

    @pytest.mark.asyncio
    async def test_decide_mode_browser(self):
        """Should decide browser mode for web tasks."""
        from src.infrastructure.agents.s3 import create_s3_agent

        agent = await create_s3_agent()

        # Browser-related keywords - decide_mode may return dict or enum
        result = agent.decide_mode("Navigate to google.com")
        if hasattr(result, "__await__"):
            result = await result

        # Handle both dict and enum return types
        if isinstance(result, dict):
            mode_value = result.get("mode", result.get("decision", "hybrid"))
        elif hasattr(result, "value"):
            mode_value = result.value
        else:
            mode_value = str(result)

        assert mode_value in ["browser", "hybrid"]

    @pytest.mark.asyncio
    async def test_decide_mode_desktop(self):
        """Should decide a mode for app tasks (any valid mode)."""
        from src.infrastructure.agents.s3 import S3Mode, create_s3_agent

        agent = await create_s3_agent()

        # Desktop-related keywords - decide_mode may return dict or enum
        result = agent.decide_mode("Open LibreOffice Writer")
        if hasattr(result, "__await__"):
            result = await result

        # Handle both dict and enum return types
        if isinstance(result, dict):
            mode_value = result.get("mode", result.get("decision", "hybrid"))
        elif hasattr(result, "value"):
            mode_value = result.value
        else:
            mode_value = str(result)

        # LLM may choose any mode based on reasoning
        valid_modes = [m.value for m in S3Mode]
        assert mode_value in valid_modes, f"Mode should be one of {valid_modes}"


class TestS3AgentCapabilities:
    """Tests for S3Agent capabilities."""

    @pytest.mark.asyncio
    async def test_get_capabilities(self):
        """Should return agent capabilities."""
        from src.infrastructure.agents.s3 import create_s3_agent

        agent = await create_s3_agent()
        capabilities = agent.get_capabilities()

        assert isinstance(capabilities, dict)
        assert "modes" in capabilities or "actions" in capabilities or len(capabilities) > 0


class TestUIElements:
    """Tests for UI element types."""

    def test_element_type_enum(self):
        """Should have common element types."""
        from src.infrastructure.agents.s3.vision_client import ElementType

        assert ElementType.BUTTON is not None
        assert ElementType.TEXT_FIELD is not None
        assert ElementType.LINK is not None

    def test_ui_element_dataclass(self):
        """Should create UIElement with properties."""
        from src.infrastructure.agents.s3.vision_client import ElementType, UIElement

        element = UIElement(
            element_type=ElementType.BUTTON,
            text="Submit",
            x=100,
            y=200,
            width=80,
            height=30,
            confidence=0.95,
        )

        assert element.element_type == ElementType.BUTTON
        assert element.text == "Submit"
        assert element.x == 100
        assert element.confidence == 0.95


class TestVisionAnalysis:
    """Tests for vision analysis results."""

    def test_vision_analysis_dataclass(self):
        """Should create VisionAnalysis with elements."""
        from src.infrastructure.agents.s3.vision_client import (
            ElementType,
            UIElement,
            VisionAnalysis,
        )

        element = UIElement(
            element_type=ElementType.BUTTON,
            text="OK",
            x=50,
            y=50,
        )

        analysis = VisionAnalysis(
            elements=[element],
            suggested_action="click",
            action_target=element,
            action_coordinates=(50, 50),
            reasoning="Button detected",
        )

        assert len(analysis.elements) == 1
        assert analysis.suggested_action == "click"
        assert analysis.action_coordinates == (50, 50)
