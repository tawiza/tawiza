"""Tests for CLI constants module.

This module tests:
- Version constants
- Path constants
- Timeout constants
- Limit constants
- Valid value constants
"""

from pathlib import Path

import pytest

from src.cli.constants import (
    AGENT_DISPLAY_NAMES,
    AGENT_PRIORITIES,
    AGENT_TIMEOUT,
    # Agents
    AVAILABLE_AGENTS,
    # Security
    BLOCKED_FILE_EXTENSIONS,
    CACHE_TTL_EXTRA_LONG,
    CACHE_TTL_LONG,
    CACHE_TTL_MEDIUM,
    CACHE_TTL_SHORT,
    CLI_DESCRIPTION,
    CLI_NAME,
    # Version
    CLI_VERSION,
    CONFIG_DIR,
    DASHBOARD_UPDATE_INTERVAL,
    DATA_DIR,
    DATASETS_DIR,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CACHE_SIZE,
    DEFAULT_CONCURRENT_TASKS,
    DEFAULT_EPOCHS,
    DEFAULT_GPU_OPTIMIZATION,
    DEFAULT_LEARNING_RATE,
    DEFAULT_LOG_LEVEL,
    DEFAULT_METRICS,
    DEFAULT_MODEL,
    DEFAULT_MONITORING_INTERVAL,
    DEFAULT_RETRIES,
    DEFAULT_VISION_MODEL,
    GPU_MEMORY_LIMITS,
    # GPU
    GPU_OPTIMIZATION_LEVELS,
    # Timeouts
    HTTP_TIMEOUT,
    LABEL_STUDIO_DEFAULT_URL,
    LOG_FORMAT,
    LOG_UPDATE_INTERVAL,
    LOGS_DIR,
    MAX_CACHE_SIZE,
    MAX_CONCURRENT_TASKS,
    MAX_EPOCHS,
    MAX_INPUT_LENGTH,
    MAX_LEARNING_RATE,
    MAX_LOG_ENTRIES,
    MAX_LOG_LINE_LENGTH,
    MAX_PATH_LENGTH,
    MAX_RETRIES,
    # Messages
    MESSAGES,
    # Limits
    MIN_CONCURRENT_TASKS,
    MIN_EPOCHS,
    MIN_LEARNING_RATE,
    MIN_MONITORING_INTERVAL,
    MIN_RETRIES,
    MINIO_DEFAULT_URL,
    MLFLOW_DEFAULT_URL,
    MODELS_DIR,
    # API
    OLLAMA_DEFAULT_URL,
    OLLAMA_TIMEOUT,
    OUTPUT_DIR,
    # Paths
    PROJECT_ROOT,
    RETRY_BASE_DELAY,
    STATUS_ICONS,
    # Models
    SUPPORTED_MODELS,
    SYSTEM_CONFIG_FILE,
    # UI
    THEME_COLORS,
    TUI_REFRESH_INTERVAL,
    USER_CONFIG_FILE,
    # Batch sizes
    VALID_BATCH_SIZES,
    # Logging
    VALID_LOG_LEVELS,
    # Monitoring
    VALID_METRICS,
)


class TestVersionConstants:
    """Test suite for version constants."""

    def test_cli_version_format(self):
        """CLI version should be semantic version format."""
        parts = CLI_VERSION.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()

    def test_cli_name(self):
        """CLI name should be Tawiza-V2."""
        assert CLI_NAME == "Tawiza-V2"

    def test_cli_description_not_empty(self):
        """CLI description should not be empty."""
        assert len(CLI_DESCRIPTION) > 0


class TestPathConstants:
    """Test suite for path constants."""

    def test_project_root_is_path(self):
        """Project root should be a Path object."""
        assert isinstance(PROJECT_ROOT, Path)

    def test_config_dir_under_project_root(self):
        """Config dir should be under project root."""
        assert str(CONFIG_DIR).startswith(str(PROJECT_ROOT))

    def test_data_dir_under_project_root(self):
        """Data dir should be under project root."""
        assert str(DATA_DIR).startswith(str(PROJECT_ROOT))

    def test_all_dirs_are_paths(self):
        """All directory constants should be Path objects."""
        dirs = [
            CONFIG_DIR,
            DATA_DIR,
            DATASETS_DIR,
            OUTPUT_DIR,
            LOGS_DIR,
            MODELS_DIR,
        ]
        for d in dirs:
            assert isinstance(d, Path)

    def test_config_files_are_paths(self):
        """Config file paths should be Path objects."""
        assert isinstance(SYSTEM_CONFIG_FILE, Path)
        assert isinstance(USER_CONFIG_FILE, Path)


class TestTimeoutConstants:
    """Test suite for timeout constants."""

    def test_http_timeout_reasonable(self):
        """HTTP timeout should be reasonable (1-300 seconds)."""
        assert 1 <= HTTP_TIMEOUT <= 300

    def test_ollama_timeout_reasonable(self):
        """Ollama timeout should be reasonable (30-600 seconds)."""
        assert 30 <= OLLAMA_TIMEOUT <= 600

    def test_agent_timeout_reasonable(self):
        """Agent timeout should be reasonable (60-1800 seconds)."""
        assert 60 <= AGENT_TIMEOUT <= 1800

    def test_ui_intervals_are_positive(self):
        """UI intervals should be positive."""
        assert TUI_REFRESH_INTERVAL > 0
        assert DASHBOARD_UPDATE_INTERVAL > 0
        assert LOG_UPDATE_INTERVAL > 0

    def test_cache_ttls_increasing(self):
        """Cache TTLs should be in increasing order."""
        assert CACHE_TTL_SHORT < CACHE_TTL_MEDIUM
        assert CACHE_TTL_MEDIUM < CACHE_TTL_LONG
        assert CACHE_TTL_LONG < CACHE_TTL_EXTRA_LONG


class TestLimitConstants:
    """Test suite for limit constants."""

    def test_concurrent_tasks_range(self):
        """Concurrent tasks should have valid range."""
        assert MIN_CONCURRENT_TASKS >= 1
        assert MAX_CONCURRENT_TASKS > MIN_CONCURRENT_TASKS
        assert MIN_CONCURRENT_TASKS <= DEFAULT_CONCURRENT_TASKS <= MAX_CONCURRENT_TASKS

    def test_retries_range(self):
        """Retries should have valid range."""
        assert MIN_RETRIES >= 0
        assert MAX_RETRIES > MIN_RETRIES
        assert MIN_RETRIES <= DEFAULT_RETRIES <= MAX_RETRIES

    def test_retry_base_delay_positive(self):
        """Retry base delay should be positive."""
        assert RETRY_BASE_DELAY > 0

    def test_log_limits_positive(self):
        """Log limits should be positive."""
        assert MAX_LOG_ENTRIES > 0
        assert MAX_LOG_LINE_LENGTH > 0

    def test_cache_size_range(self):
        """Cache sizes should have valid range."""
        assert DEFAULT_CACHE_SIZE > 0
        assert MAX_CACHE_SIZE >= DEFAULT_CACHE_SIZE


class TestMLConstants:
    """Test suite for ML-related constants."""

    def test_valid_batch_sizes(self):
        """Batch sizes should be powers of 2."""
        for size in VALID_BATCH_SIZES:
            # Check if power of 2
            assert size > 0
            assert (size & (size - 1)) == 0 or size == 1

    def test_default_batch_size_in_valid(self):
        """Default batch size should be in valid list."""
        assert DEFAULT_BATCH_SIZE in VALID_BATCH_SIZES

    def test_learning_rate_range(self):
        """Learning rate should have valid range."""
        assert MIN_LEARNING_RATE > 0
        assert MAX_LEARNING_RATE > MIN_LEARNING_RATE
        assert MIN_LEARNING_RATE <= DEFAULT_LEARNING_RATE <= MAX_LEARNING_RATE

    def test_epochs_range(self):
        """Epochs should have valid range."""
        assert MIN_EPOCHS >= 1
        assert MAX_EPOCHS > MIN_EPOCHS
        assert MIN_EPOCHS <= DEFAULT_EPOCHS <= MAX_EPOCHS


class TestLoggingConstants:
    """Test suite for logging constants."""

    def test_valid_log_levels(self):
        """Valid log levels should include standard levels."""
        expected_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        assert set(VALID_LOG_LEVELS) == expected_levels

    def test_default_log_level_valid(self):
        """Default log level should be in valid levels."""
        assert DEFAULT_LOG_LEVEL in VALID_LOG_LEVELS

    def test_log_format_not_empty(self):
        """Log format should not be empty."""
        assert len(LOG_FORMAT) > 0


class TestAgentConstants:
    """Test suite for agent constants."""

    def test_available_agents_not_empty(self):
        """Available agents should not be empty."""
        assert len(AVAILABLE_AGENTS) > 0

    def test_agent_display_names_coverage(self):
        """All available agents should have display names."""
        for agent in AVAILABLE_AGENTS:
            assert agent in AGENT_DISPLAY_NAMES

    def test_agent_priorities_coverage(self):
        """All available agents should have priorities."""
        for agent in AVAILABLE_AGENTS:
            assert agent in AGENT_PRIORITIES

    def test_agent_priorities_are_positive(self):
        """Agent priorities should be positive integers."""
        for priority in AGENT_PRIORITIES.values():
            assert isinstance(priority, int)
            assert priority > 0


class TestModelConstants:
    """Test suite for model constants."""

    def test_supported_models_not_empty(self):
        """Supported models should not be empty."""
        assert len(SUPPORTED_MODELS) > 0

    def test_default_model_in_supported(self):
        """Default model should be in supported models."""
        assert DEFAULT_MODEL in SUPPORTED_MODELS

    def test_default_vision_model_not_empty(self):
        """Default vision model should not be empty."""
        assert len(DEFAULT_VISION_MODEL) > 0


class TestGPUConstants:
    """Test suite for GPU constants."""

    def test_gpu_optimization_levels(self):
        """GPU optimization levels should include standard options."""
        assert "auto" in GPU_OPTIMIZATION_LEVELS
        assert "conservative" in GPU_OPTIMIZATION_LEVELS
        assert "aggressive" in GPU_OPTIMIZATION_LEVELS

    def test_default_gpu_optimization_valid(self):
        """Default GPU optimization should be valid."""
        assert DEFAULT_GPU_OPTIMIZATION in GPU_OPTIMIZATION_LEVELS

    def test_gpu_memory_limits_range(self):
        """GPU memory limits should be in valid range."""
        for limit in GPU_MEMORY_LIMITS.values():
            assert 0 < limit <= 100


class TestMonitoringConstants:
    """Test suite for monitoring constants."""

    def test_valid_metrics_not_empty(self):
        """Valid metrics should not be empty."""
        assert len(VALID_METRICS) > 0

    def test_default_metrics_subset_of_valid(self):
        """Default metrics should be subset of valid metrics."""
        for metric in DEFAULT_METRICS:
            assert metric in VALID_METRICS

    def test_monitoring_intervals_positive(self):
        """Monitoring intervals should be positive."""
        assert MIN_MONITORING_INTERVAL > 0
        assert DEFAULT_MONITORING_INTERVAL > 0


class TestSecurityConstants:
    """Test suite for security constants."""

    def test_blocked_file_extensions_not_empty(self):
        """Blocked file extensions should not be empty."""
        assert len(BLOCKED_FILE_EXTENSIONS) > 0

    def test_blocked_extensions_start_with_dot(self):
        """Blocked extensions should start with dot."""
        for ext in BLOCKED_FILE_EXTENSIONS:
            assert ext.startswith(".")

    def test_path_length_limits_reasonable(self):
        """Path length limits should be reasonable."""
        assert MAX_PATH_LENGTH >= 256
        assert MAX_INPUT_LENGTH >= 100


class TestUIConstants:
    """Test suite for UI constants."""

    def test_theme_colors_valid_hex(self):
        """Theme colors should be valid hex colors."""
        for color in THEME_COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7

    def test_status_icons_not_empty(self):
        """Status icons should not be empty."""
        assert len(STATUS_ICONS) > 0

    def test_status_icons_have_common_statuses(self):
        """Status icons should have common statuses."""
        common_statuses = {"running", "idle", "stopped", "error", "success"}
        for status in common_statuses:
            assert status in STATUS_ICONS


class TestAPIConstants:
    """Test suite for API constants."""

    def test_ollama_url_valid(self):
        """Ollama URL should be valid HTTP URL."""
        assert OLLAMA_DEFAULT_URL.startswith("http")
        assert "11434" in OLLAMA_DEFAULT_URL

    def test_mlflow_url_valid(self):
        """MLflow URL should be valid HTTP URL."""
        assert MLFLOW_DEFAULT_URL.startswith("http")

    def test_all_urls_have_protocol(self):
        """All API URLs should have protocol."""
        urls = [
            OLLAMA_DEFAULT_URL,
            MLFLOW_DEFAULT_URL,
            LABEL_STUDIO_DEFAULT_URL,
            MINIO_DEFAULT_URL,
        ]
        for url in urls:
            assert url.startswith("http://") or url.startswith("https://")


class TestMessageConstants:
    """Test suite for message constants."""

    def test_messages_not_empty(self):
        """Messages should not be empty."""
        assert len(MESSAGES) > 0

    def test_common_messages_exist(self):
        """Common messages should exist."""
        expected_keys = [
            "init_success",
            "init_failed",
            "shutdown_success",
        ]
        for key in expected_keys:
            assert key in MESSAGES

    def test_messages_are_strings(self):
        """All messages should be strings."""
        for msg in MESSAGES.values():
            assert isinstance(msg, str)
            assert len(msg) > 0
