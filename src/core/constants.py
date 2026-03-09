"""Application constants and configuration values.

This module centralizes all magic numbers, versions, and default values
to improve maintainability and reduce code duplication.
"""
from typing import Final

# ============================================================================
# Version Information
# ============================================================================
APP_VERSION: Final[str] = "2.0.3"
APP_NAME: Final[str] = "Tawiza-V2"
APP_DESCRIPTION: Final[str] = "Système Multi-Agents IA Avancé avec Optimisation GPU AMD ROCm"

# ============================================================================
# Python Version Requirements
# ============================================================================
MIN_PYTHON_VERSION: Final[tuple[int, int]] = (3, 10)

# ============================================================================
# Timeouts (in seconds)
# ============================================================================
COMMAND_TIMEOUT_SHORT: Final[int] = 5
COMMAND_TIMEOUT_MEDIUM: Final[int] = 10
COMMAND_TIMEOUT_LONG: Final[int] = 120
COMMAND_TIMEOUT_EXTENDED: Final[int] = 300
COMMAND_TIMEOUT_MAX: Final[int] = 600

# ============================================================================
# Network Timeouts
# ============================================================================
HTTP_TIMEOUT_DEFAULT: Final[int] = 60
HTTP_TIMEOUT_LONG: Final[int] = 120
HTTP_RETRY_MAX: Final[int] = 3

# ============================================================================
# Directory Paths
# ============================================================================
DIRS_TO_CREATE: Final[list[str]] = [
    "logs",
    "data",
    "models",
    "configs",
    "debug_reports",
    "outputs"
]

CONFIG_DIR: Final[str] = "configs"
LOG_DIR: Final[str] = "logs"
DATA_DIR: Final[str] = "data"
MODELS_DIR: Final[str] = "models"
DEBUG_REPORTS_DIR: Final[str] = "debug_reports"
OUTPUTS_DIR: Final[str] = "outputs"

# ============================================================================
# Configuration Files
# ============================================================================
SYSTEM_CONFIG_FILE: Final[str] = "configs/system_config.json"
DEBUG_LOG_FILE: Final[str] = "logs/advanced_debug.log"

# ============================================================================
# System Resource Thresholds
# ============================================================================
CPU_WARNING_THRESHOLD: Final[float] = 70.0
CPU_CRITICAL_THRESHOLD: Final[float] = 85.0
MEMORY_WARNING_THRESHOLD: Final[float] = 70.0
MEMORY_CRITICAL_THRESHOLD: Final[float] = 85.0
DISK_WARNING_THRESHOLD: Final[float] = 80.0
DISK_CRITICAL_THRESHOLD: Final[float] = 90.0

# ============================================================================
# Health Check Scores
# ============================================================================
HEALTH_SCORE_EXCELLENT: Final[int] = 90
HEALTH_SCORE_GOOD: Final[int] = 80
HEALTH_SCORE_MEDIUM: Final[int] = 60
HEALTH_SCORE_PENALTY_MAJOR: Final[int] = 10
HEALTH_SCORE_PENALTY_MINOR: Final[int] = 5
HEALTH_SCORE_PENALTY_CRITICAL: Final[int] = 20
HEALTH_SCORE_PENALTY_WARNING: Final[int] = 15

# ============================================================================
# Task Management
# ============================================================================
DEFAULT_MAX_CONCURRENT_TASKS: Final[int] = 5
DEFAULT_RETRY_FAILED_TASKS: Final[int] = 3

# ============================================================================
# Log Display
# ============================================================================
DEFAULT_LOG_LINES: Final[int] = 50
LOG_FOLLOW_SLEEP_INTERVAL: Final[float] = 0.1

# ============================================================================
# Demo Settings
# ============================================================================
DEMO_DEFAULT_DURATION: Final[int] = 60
DEMO_MAX_DURATION: Final[int] = 300

# ============================================================================
# Security
# ============================================================================
SECRET_KEY_MIN_LENGTH: Final[int] = 32
SECRET_KEY_ENV_VAR: Final[str] = "SECRET_KEY"
APP_ENV_VAR: Final[str] = "APP_ENV"
PRODUCTION_ENV: Final[str] = "production"

# ============================================================================
# GPU Settings
# ============================================================================
ROCM_PATH_DEFAULT: Final[str] = "/opt/rocm"
GPU_PLATFORM_AMD: Final[str] = "amd"

# ============================================================================
# Port Defaults
# ============================================================================
API_PORT_DEFAULT: Final[int] = 8000
PROMETHEUS_PORT_DEFAULT: Final[int] = 9090
GRAFANA_PORT_DEFAULT: Final[int] = 3000
MLFLOW_PORT_DEFAULT: Final[int] = 5000
LABEL_STUDIO_PORT_DEFAULT: Final[int] = 8080
MINIO_PORT_DEFAULT: Final[int] = 9000
VLLM_PORT_DEFAULT: Final[int] = 8001
OLLAMA_PORT_DEFAULT: Final[int] = 11434

# ============================================================================
# Database Settings
# ============================================================================
DB_POOL_SIZE_DEFAULT: Final[int] = 10
DB_POOL_SIZE_MIN: Final[int] = 1
DB_POOL_SIZE_MAX: Final[int] = 100
DB_MAX_OVERFLOW_DEFAULT: Final[int] = 20

# ============================================================================
# Redis Settings
# ============================================================================
REDIS_MAX_CONNECTIONS_DEFAULT: Final[int] = 50

# ============================================================================
# Ollama Settings
# ============================================================================
OLLAMA_POOL_CONNECTIONS_DEFAULT: Final[int] = 10
OLLAMA_POOL_MAXSIZE_DEFAULT: Final[int] = 20
OLLAMA_CACHE_TTL_DEFAULT: Final[int] = 300

# ============================================================================
# Training Settings
# ============================================================================
TRAINING_BATCH_SIZE_DEFAULT: Final[int] = 4
TRAINING_GRADIENT_ACCUMULATION_DEFAULT: Final[int] = 4
TRAINING_LEARNING_RATE_DEFAULT: Final[float] = 2e-5
TRAINING_EPOCHS_DEFAULT: Final[int] = 3
TRAINING_MAX_SEQ_LENGTH_DEFAULT: Final[int] = 2048
TRAINING_LORA_RANK_DEFAULT: Final[int] = 8
TRAINING_LORA_ALPHA_DEFAULT: Final[int] = 16

# ============================================================================
# Vector Database Settings
# ============================================================================
VECTOR_EMBEDDING_DIM_DEFAULT: Final[int] = 768
VECTOR_CHUNK_SIZE_DEFAULT: Final[int] = 512
VECTOR_CHUNK_OVERLAP_DEFAULT: Final[int] = 50
VECTOR_SEARCH_LIMIT_DEFAULT: Final[int] = 10
VECTOR_DISTANCE_THRESHOLD_DEFAULT: Final[float] = 1.0

# ============================================================================
# Monitoring Settings
# ============================================================================
PROGRESS_CLEANUP_AFTER_DEFAULT: Final[int] = 3600  # 1 hour
PROGRESS_MAX_EVENTS_PER_TASK_DEFAULT: Final[int] = 1000

# ============================================================================
# Status Icons and Indicators
# ============================================================================
ICON_SUCCESS: Final[str] = "✅"
ICON_WARNING: Final[str] = "⚠️"
ICON_ERROR: Final[str] = "❌"
ICON_INFO: Final[str] = "ℹ️"
ICON_RUNNING: Final[str] = "🔄"
ICON_PENDING: Final[str] = "⏳"

# ============================================================================
# Status Indicators (colored)
# ============================================================================
STATUS_GREEN: Final[str] = "🟢"
STATUS_YELLOW: Final[str] = "🟡"
STATUS_RED: Final[str] = "🔴"

# ============================================================================
# File Size Limits
# ============================================================================
MAX_LOG_FILE_SIZE: Final[int] = 100 * 1024 * 1024  # 100 MB
MAX_CONFIG_FILE_SIZE: Final[int] = 10 * 1024 * 1024  # 10 MB

# ============================================================================
# Encoding
# ============================================================================
DEFAULT_ENCODING: Final[str] = "utf-8"
