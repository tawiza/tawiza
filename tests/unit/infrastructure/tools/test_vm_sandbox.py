"""Tests for VM Sandbox execution tools."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.tools.code.bash_execute import BashExecuteTool
from src.infrastructure.tools.code.python_execute import PythonExecuteTool
from src.infrastructure.tools.security.vm_sandbox_client import (
    SandboxConfig,
    SandboxResult,
    VMSandboxClient,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sandbox_config():
    """Test sandbox configuration."""
    return SandboxConfig(
        host="http://test-sandbox:8100",
        api_key="test-key",
        default_timeout=10,
        max_timeout=30,
    )


@pytest.fixture
def mock_sandbox_result():
    """Sample successful sandbox result."""
    return SandboxResult(
        success=True,
        stdout="Hello World\n",
        stderr="",
        exit_code=0,
        duration_ms=150.5,
        run_id="test-run-123",
    )


@pytest.fixture
def mock_sandbox_client(mock_sandbox_result):
    """Mock VMSandboxClient."""
    client = MagicMock(spec=VMSandboxClient)
    client.run_bash = AsyncMock(return_value=mock_sandbox_result)
    client.run_python = AsyncMock(return_value=mock_sandbox_result)
    client.run_bash_stream = AsyncMock(return_value=mock_sandbox_result)
    client.run_python_stream = AsyncMock(return_value=mock_sandbox_result)
    return client


# ============================================================================
# VMSandboxClient Tests
# ============================================================================


class TestSandboxConfig:
    """Tests for SandboxConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SandboxConfig()
        assert config.host == "http://localhost:8100"
        assert config.api_key == "changeme"
        assert config.default_timeout == 30
        assert config.max_timeout == 120

    def test_custom_config(self):
        """Test custom configuration."""
        config = SandboxConfig(
            host="http://custom:9000",
            api_key="custom-key",
            default_timeout=60,
            max_timeout=300,
        )
        assert config.host == "http://custom:9000"
        assert config.api_key == "custom-key"
        assert config.default_timeout == 60
        assert config.max_timeout == 300


class TestSandboxResult:
    """Tests for SandboxResult dataclass."""

    def test_successful_result(self):
        """Test successful result creation."""
        result = SandboxResult(
            success=True,
            stdout="output",
            stderr="",
            exit_code=0,
            duration_ms=100.0,
            run_id="run-123",
        )
        assert result.success is True
        assert result.exit_code == 0
        assert result.error is None

    def test_failed_result(self):
        """Test failed result with error."""
        result = SandboxResult(
            success=False,
            stdout="",
            stderr="Error occurred",
            exit_code=1,
            duration_ms=50.0,
            run_id="run-456",
            error="Execution failed",
        )
        assert result.success is False
        assert result.exit_code == 1
        assert result.error == "Execution failed"


class TestVMSandboxClient:
    """Tests for VMSandboxClient."""

    def test_client_initialization(self, sandbox_config):
        """Test client initializes with config."""
        client = VMSandboxClient(sandbox_config)
        assert client.config == sandbox_config
        assert client._client is None

    def test_client_default_config(self):
        """Test client uses default config."""
        client = VMSandboxClient()
        assert client.config.host == "http://localhost:8100"


# ============================================================================
# BashExecuteTool VM Sandbox Tests
# ============================================================================


class TestBashExecuteVMSandbox:
    """Tests for BashExecuteTool with VM sandbox."""

    def test_vm_sandbox_flag(self, mock_sandbox_client):
        """Test VM sandbox mode is enabled."""
        tool = BashExecuteTool(
            use_vm_sandbox=True,
            vm_sandbox_client=mock_sandbox_client,
        )
        assert tool._use_vm_sandbox is True

    def test_vm_sandbox_fallback_without_client(self):
        """Test fallback to local when no client provided."""
        tool = BashExecuteTool(use_vm_sandbox=True)
        # Should fall back to local mode
        assert tool._use_vm_sandbox is False

    @pytest.mark.asyncio
    async def test_execute_in_vm(self, mock_sandbox_client, mock_sandbox_result):
        """Test execution via VM sandbox."""
        tool = BashExecuteTool(
            use_vm_sandbox=True,
            vm_sandbox_client=mock_sandbox_client,
        )

        result = await tool.execute(command="echo hello")

        assert result.success is True
        assert result.output["stdout"] == "Hello World\n"
        assert result.output["exit_code"] == 0
        mock_sandbox_client.run_bash.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_in_vm_with_working_dir(self, mock_sandbox_client):
        """Test working directory is prepended."""
        tool = BashExecuteTool(
            use_vm_sandbox=True,
            vm_sandbox_client=mock_sandbox_client,
        )

        await tool.execute(command="ls", working_dir="/tmp")

        # Check that cd was prepended
        call_args = mock_sandbox_client.run_bash.call_args
        assert "cd /tmp && ls" in call_args.kwargs["code"]

    @pytest.mark.asyncio
    async def test_execute_stream_requires_vm_sandbox(self):
        """Test streaming requires VM sandbox mode."""
        tool = BashExecuteTool(use_vm_sandbox=False)

        result = await tool.execute_stream(command="echo test")

        assert result.success is False
        assert "requires VM sandbox mode" in result.error


# ============================================================================
# PythonExecuteTool VM Sandbox Tests
# ============================================================================


class TestPythonExecuteVMSandbox:
    """Tests for PythonExecuteTool with VM sandbox."""

    def test_vm_sandbox_flag(self, mock_sandbox_client):
        """Test VM sandbox mode is enabled."""
        tool = PythonExecuteTool(
            use_vm_sandbox=True,
            vm_sandbox_client=mock_sandbox_client,
        )
        assert tool._use_vm_sandbox is True

    @pytest.mark.asyncio
    async def test_execute_in_vm(self, mock_sandbox_client, mock_sandbox_result):
        """Test execution via VM sandbox."""
        tool = PythonExecuteTool(
            use_vm_sandbox=True,
            vm_sandbox_client=mock_sandbox_client,
        )

        result = await tool.execute(code="print('hello')")

        assert result.success is True
        assert result.output["stdout"] == "Hello World\n"
        mock_sandbox_client.run_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_stream_requires_vm_sandbox(self):
        """Test streaming requires VM sandbox mode."""
        tool = PythonExecuteTool(use_vm_sandbox=False)

        result = await tool.execute_stream(code="print('test')")

        assert result.success is False
        assert "requires VM sandbox mode" in result.error


# ============================================================================
# Streaming Tests
# ============================================================================


class TestStreamingExecution:
    """Tests for streaming execution."""

    @pytest.mark.asyncio
    async def test_bash_stream_calls_client(self, mock_sandbox_client):
        """Test bash streaming calls the client correctly."""
        tool = BashExecuteTool(
            use_vm_sandbox=True,
            vm_sandbox_client=mock_sandbox_client,
        )

        output_chunks = []

        async def capture_output(stream_type: str, content: str):
            output_chunks.append((stream_type, content))

        result = await tool.execute_stream(
            command="echo test",
            on_output=capture_output,
        )

        assert result.success is True
        mock_sandbox_client.run_bash_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_python_stream_calls_client(self, mock_sandbox_client):
        """Test Python streaming calls the client correctly."""
        tool = PythonExecuteTool(
            use_vm_sandbox=True,
            vm_sandbox_client=mock_sandbox_client,
        )

        async def capture_output(stream_type: str, content: str):
            pass

        result = await tool.execute_stream(
            code="print('test')",
            on_output=capture_output,
        )

        assert result.success is True
        mock_sandbox_client.run_python_stream.assert_called_once()
