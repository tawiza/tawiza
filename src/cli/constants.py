#!/usr/bin/env python3
"""
Constantes centralisées pour Tawiza-V2 CLI

Ce module centralise toutes les constantes utilisées dans l'interface CLI
pour faciliter la maintenance et la cohérence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

# ==============================================================================
# VERSIONING
# ==============================================================================

CLI_VERSION: Final[str] = "3.0.0"
CLI_NAME: Final[str] = "Tawiza-V2"
CLI_DESCRIPTION: Final[str] = "Multi-Platform to Ollama - Unified AI Platform"

# ==============================================================================
# PATHS
# ==============================================================================


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains pyproject.toml)."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT: Final[Path] = _find_project_root()
CONFIG_DIR: Final[Path] = PROJECT_ROOT / "configs"
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
DATASETS_DIR: Final[Path] = PROJECT_ROOT / "datasets"
OUTPUT_DIR: Final[Path] = PROJECT_ROOT / "output"
LOGS_DIR: Final[Path] = PROJECT_ROOT / "logs"
MODELS_DIR: Final[Path] = PROJECT_ROOT / "models"

# Config files
SYSTEM_CONFIG_FILE: Final[Path] = CONFIG_DIR / "system_config.json"
USER_CONFIG_FILE: Final[Path] = CONFIG_DIR / "user_config.json"

# ==============================================================================
# TIMEOUTS (en secondes)
# ==============================================================================

# Timeouts réseau
HTTP_TIMEOUT: Final[float] = 30.0
OLLAMA_TIMEOUT: Final[float] = 120.0
AGENT_TIMEOUT: Final[float] = 300.0

# Timeouts UI
TUI_REFRESH_INTERVAL: Final[float] = 1.0
DASHBOARD_UPDATE_INTERVAL: Final[float] = 2.0
LOG_UPDATE_INTERVAL: Final[float] = 0.5

# Cache TTLs
CACHE_TTL_SHORT: Final[int] = 5  # 5 secondes
CACHE_TTL_MEDIUM: Final[int] = 60  # 1 minute
CACHE_TTL_LONG: Final[int] = 300  # 5 minutes
CACHE_TTL_EXTRA_LONG: Final[int] = 3600  # 1 heure

# ==============================================================================
# LIMITES
# ==============================================================================

# Tâches concurrentes
MIN_CONCURRENT_TASKS: Final[int] = 1
MAX_CONCURRENT_TASKS: Final[int] = 100
DEFAULT_CONCURRENT_TASKS: Final[int] = 5

# Retries
MIN_RETRIES: Final[int] = 0
MAX_RETRIES: Final[int] = 10
DEFAULT_RETRIES: Final[int] = 3
RETRY_BASE_DELAY: Final[float] = 0.5

# Logs
MAX_LOG_ENTRIES: Final[int] = 1000
MAX_LOG_LINE_LENGTH: Final[int] = 500

# Cache
DEFAULT_CACHE_SIZE: Final[int] = 1000
MAX_CACHE_SIZE: Final[int] = 10000

# ==============================================================================
# BATCH SIZES (pour ML)
# ==============================================================================

VALID_BATCH_SIZES: Final[tuple[int, ...]] = (1, 2, 4, 8, 16, 32, 64, 128)
DEFAULT_BATCH_SIZE: Final[int] = 8

# Learning rates
MIN_LEARNING_RATE: Final[float] = 1e-6
MAX_LEARNING_RATE: Final[float] = 1.0
DEFAULT_LEARNING_RATE: Final[float] = 2e-4

# Epochs
MIN_EPOCHS: Final[int] = 1
MAX_EPOCHS: Final[int] = 100
DEFAULT_EPOCHS: Final[int] = 3

# ==============================================================================
# LOGGING
# ==============================================================================

VALID_LOG_LEVELS: Final[tuple[str, ...]] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
DEFAULT_LOG_LEVEL: Final[str] = "INFO"
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ==============================================================================
# AGENTS
# ==============================================================================

AVAILABLE_AGENTS: Final[tuple[str, ...]] = (
    "data_analyst",
    "ml_engineer",
    "code_generator",
    "browser_automation",
    "gpu_optimizer",
)

AGENT_DISPLAY_NAMES: Final[dict[str, str]] = {
    "data_analyst": "🔍 Data Analyst",
    "ml_engineer": "🧠 ML Engineer",
    "code_generator": "💻 Code Generator",
    "browser_automation": "🌐 Browser Automation",
    "gpu_optimizer": "🎮 GPU Optimizer",
}

AGENT_PRIORITIES: Final[dict[str, int]] = {
    "data_analyst": 5,
    "ml_engineer": 6,
    "code_generator": 4,
    "browser_automation": 3,
    "gpu_optimizer": 7,
}

# ==============================================================================
# MODELS
# ==============================================================================

SUPPORTED_MODELS: Final[tuple[str, ...]] = (
    "qwen3.5:27b",
    "qwen3-coder:30b",
    "llama3:70b",
    "mistral:latest",
    "mixtral:8x7b",
)

DEFAULT_MODEL: Final[str] = "qwen3.5:27b"
DEFAULT_VISION_MODEL: Final[str] = "llava:13b"

# ==============================================================================
# GPU
# ==============================================================================

GPU_OPTIMIZATION_LEVELS: Final[tuple[str, ...]] = ("auto", "conservative", "aggressive")
DEFAULT_GPU_OPTIMIZATION: Final[str] = "auto"

GPU_MEMORY_LIMITS: Final[dict[str, float]] = {
    "low": 25.0,
    "medium": 50.0,
    "high": 75.0,
    "max": 95.0,
}

# ==============================================================================
# MONITORING
# ==============================================================================

VALID_METRICS: Final[tuple[str, ...]] = ("cpu", "memory", "gpu", "disk", "network")
DEFAULT_METRICS: Final[tuple[str, ...]] = ("cpu", "memory", "gpu")
MIN_MONITORING_INTERVAL: Final[float] = 0.1
DEFAULT_MONITORING_INTERVAL: Final[float] = 1.0

# ==============================================================================
# SECURITY
# ==============================================================================

BLOCKED_FILE_EXTENSIONS: Final[tuple[str, ...]] = (
    ".exe",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".dll",
    ".so",
    ".dylib",
)

MAX_PATH_LENGTH: Final[int] = 4096
MAX_INPUT_LENGTH: Final[int] = 10000

# ==============================================================================
# UI / THEME
# ==============================================================================

# Sunset theme colors
THEME_COLORS: Final[dict[str, str]] = {
    "primary": "#FF6B35",  # Orange sunset
    "secondary": "#F7931E",  # Amber
    "accent": "#FFD23F",  # Yellow
    "success": "#06FFA5",  # Green
    "warning": "#FFD23F",  # Yellow
    "error": "#FF4444",  # Red
    "info": "#4A90D9",  # Blue
    "text": "#F0F0F0",  # Light gray
    "muted": "#B0B0B0",  # Gray
    "disabled": "#858585",  # Dark gray
}

# Status indicators
STATUS_ICONS: Final[dict[str, str]] = {
    "running": "🟢",
    "idle": "🟡",
    "stopped": "🔴",
    "error": "❌",
    "warning": "⚠️",
    "success": "✅",
    "pending": "⏳",
    "unknown": "❓",
}

# ==============================================================================
# API ENDPOINTS (pour référence)
# ==============================================================================

OLLAMA_DEFAULT_URL: Final[str] = "http://localhost:11434"
MLFLOW_DEFAULT_URL: Final[str] = "http://localhost:5000"
LABEL_STUDIO_DEFAULT_URL: Final[str] = "http://localhost:8080"
MINIO_DEFAULT_URL: Final[str] = "http://localhost:9000"

# ==============================================================================
# MESSAGE TEMPLATES
# ==============================================================================

MESSAGES: Final[dict[str, str]] = {
    "init_success": "✅ Système initialisé avec succès",
    "init_failed": "❌ Échec de l'initialisation",
    "shutdown_success": "✅ Système arrêté proprement",
    "config_saved": "✅ Configuration sauvegardée",
    "config_error": "❌ Erreur de configuration",
    "operation_cancelled": "⚠️  Opération annulée",
    "no_gpu": "⚠️  Aucun GPU détecté",
    "ollama_unavailable": "⚠️  Ollama non disponible",
}
