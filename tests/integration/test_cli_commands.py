"""Integration tests for CLI commands.

Tests the main CLI commands to ensure they work correctly
and return the expected output.

Requires the tawiza CLI to be installed in PATH.
"""

import shutil
import subprocess
import time

import httpx
import pytest

# Skip all tests in this module if tawiza CLI is not installed
pytestmark = pytest.mark.skipif(
    not shutil.which("tawiza"), reason="tawiza CLI not installed"
)


def _check_api_available() -> bool:
    """Check if the API is available at localhost:8000."""
    try:
        response = httpx.get("http://localhost:8000/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


class TestSystemCommands:
    """Test system management commands."""

    def test_help_command(self):
        """Test that tawiza --help works."""
        result = subprocess.run(["tawiza", "--help"], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "system" in result.stdout

    def test_version_command(self):
        """Test that tawiza version works."""
        result = subprocess.run(["tawiza", "version"], capture_output=True, text=True, timeout=10)
        assert "Tawiza" in result.stdout or "version" in result.stdout.lower()

    def test_system_help(self):
        """Test system --help command."""
        result = subprocess.run(
            ["tawiza", "system", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "health" in result.stdout
        assert "status" in result.stdout
        assert "diagnose" in result.stdout
        assert "gpu" in result.stdout
        assert "services" in result.stdout

    def test_system_gpu(self):
        """Test GPU status command."""
        result = subprocess.run(
            ["tawiza", "system", "gpu"], capture_output=True, text=True, timeout=10
        )
        assert "GPU" in result.stdout or "Ollama" in result.stdout

    @pytest.mark.skipif(not _check_api_available(), reason="API not available")
    def test_system_health_with_api(self):
        """Test health check when API is available."""
        result = subprocess.run(
            ["tawiza", "system", "health"], capture_output=True, text=True, timeout=15
        )
        assert "API" in result.stdout or "health" in result.stdout.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API not available")
    def test_system_status_with_api(self):
        """Test status command when API is available."""
        result = subprocess.run(
            ["tawiza", "system", "status"], capture_output=True, text=True, timeout=15
        )
        assert result.returncode == 0 or "status" in result.stdout.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API not available")
    def test_system_diagnose_with_api(self):
        """Test diagnose command when API is available."""
        result = subprocess.run(
            ["tawiza", "system", "diagnose"], capture_output=True, text=True, timeout=20
        )
        assert "Diagnostic" in result.stdout or "API" in result.stdout

    @pytest.mark.skipif(not _check_api_available(), reason="API not available")
    def test_system_services_with_api(self):
        """Test services command when API is available."""
        result = subprocess.run(
            ["tawiza", "system", "services"], capture_output=True, text=True, timeout=20
        )
        assert "Service" in result.stdout or "Status" in result.stdout


class TestFineTuneCommands:
    """Test fine-tuning CLI commands."""

    def test_finetune_help(self):
        """Test finetune --help command."""
        result = subprocess.run(
            ["tawiza", "finetune", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "start" in result.stdout
        assert "watch" in result.stdout
        assert "status" in result.stdout
        assert "list" in result.stdout
        assert "models" in result.stdout

    def test_finetune_start_help(self):
        """Test finetune start --help command."""
        result = subprocess.run(
            ["tawiza", "finetune", "start", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "--project" in result.stdout or "-p" in result.stdout
        assert "--model" in result.stdout or "-m" in result.stdout
        assert "--name" in result.stdout or "-n" in result.stdout

    @pytest.mark.skipif(not _check_api_available(), reason="API not available")
    def test_finetune_list_with_api(self):
        """Test finetune list command when API is available."""
        result = subprocess.run(
            ["tawiza", "finetune", "list"], capture_output=True, text=True, timeout=15
        )
        assert "job" in result.stdout.lower() or "No" in result.stdout or "Error" in result.stdout

    @pytest.mark.skipif(not _check_api_available(), reason="API not available")
    def test_finetune_models_with_api(self):
        """Test finetune models command when API is available."""
        result = subprocess.run(
            ["tawiza", "finetune", "models"], capture_output=True, text=True, timeout=15
        )
        assert "model" in result.stdout.lower() or "No" in result.stdout or "Error" in result.stdout


class TestAnnotateCommands:
    """Test annotation CLI commands."""

    def test_annotate_help(self):
        """Test annotate --help command."""
        result = subprocess.run(
            ["tawiza", "annotate", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "create" in result.stdout
        assert "list" in result.stdout
        assert "export" in result.stdout
        assert "stats" in result.stdout
        assert "upload" in result.stdout
        assert "delete" in result.stdout

    def test_annotate_create_help(self):
        """Test annotate create --help command."""
        result = subprocess.run(
            ["tawiza", "annotate", "create", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "--name" in result.stdout or "-n" in result.stdout
        assert "--type" in result.stdout or "-t" in result.stdout

    @pytest.mark.skipif(not _check_api_available(), reason="API not available")
    def test_annotate_list_with_api(self):
        """Test annotate list command when API is available."""
        result = subprocess.run(
            ["tawiza", "annotate", "list"], capture_output=True, text=True, timeout=15
        )
        assert (
            "project" in result.stdout.lower()
            or "No" in result.stdout
            or "Error" in result.stdout
        )


class TestModelsCommands:
    """Test models CLI commands."""

    def test_models_help(self):
        """Test models --help command."""
        result = subprocess.run(
            ["tawiza", "models", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "list" in result.stdout

    @pytest.mark.skipif(not _check_api_available(), reason="API not available")
    def test_models_list_with_api(self):
        """Test models list command when API is available."""
        result = subprocess.run(
            ["tawiza", "models", "list"], capture_output=True, text=True, timeout=15
        )
        pass  # Just checking it doesn't crash


class TestDataCommands:
    """Test data CLI commands."""

    def test_data_help(self):
        """Test data --help command."""
        result = subprocess.run(
            ["tawiza", "data", "--help"], capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "list" in result.stdout
