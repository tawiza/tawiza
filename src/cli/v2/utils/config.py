"""Configuration management for Tawiza CLI v2."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Config directory
CONFIG_DIR = Path.home() / ".tawiza"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = CONFIG_DIR / "cache"
HISTORY_DIR = CONFIG_DIR / "history"
LOGS_DIR = CONFIG_DIR / "logs"


# Default configuration
DEFAULT_CONFIG = {
    "model": "qwen3.5:27b",
    "ollama_url": "http://localhost:11434",
    "gpu_enabled": True,
    "cache_enabled": True,
    "cache_ttl": 3600,
    "history_enabled": True,
    "history_limit": 100,
    "theme": "default",
    "language": "fr",
    "verbose": False,
    "timeout": 60,
}


@dataclass
class Config:
    """Configuration manager with persistence."""

    model: str = "qwen3.5:27b"
    ollama_url: str = "http://localhost:11434"
    gpu_enabled: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 3600
    history_enabled: bool = True
    history_limit: int = 100
    theme: str = "default"
    language: str = "fr"
    verbose: bool = False
    timeout: int = 60

    def __post_init__(self):
        """Ensure directories exist."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file."""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
                # Merge with defaults for any missing keys
                merged = {**DEFAULT_CONFIG, **data}
                return cls(**merged)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls(**DEFAULT_CONFIG)

    def save(self) -> None:
        """Save configuration to file."""
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return getattr(self, key, default)

    def set(self, key: str, value: Any) -> bool:
        """Set a configuration value."""
        if hasattr(self, key):
            # Type conversion
            current = getattr(self, key)
            if isinstance(current, bool):
                value = str(value).lower() in ("true", "1", "yes", "on")
            elif isinstance(current, int):
                value = int(value)
            setattr(self, key, value)
            self.save()
            return True
        return False

    def reset(self) -> None:
        """Reset configuration to defaults."""
        for key, value in DEFAULT_CONFIG.items():
            setattr(self, key, value)
        self.save()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def items(self):
        """Iterate over configuration items."""
        return asdict(self).items()


# Singleton instance
CONFIG = Config.load()


def get_config() -> Config:
    """Get the global configuration instance."""
    return CONFIG


def get_cache_dir() -> Path:
    """Get the cache directory."""
    return CACHE_DIR


def get_history_dir() -> Path:
    """Get the history directory."""
    return HISTORY_DIR


def get_logs_dir() -> Path:
    """Get the logs directory."""
    return LOGS_DIR
