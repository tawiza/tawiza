"""Config Screen - Application settings and configuration."""

import json
import os
from typing import Any

from loguru import logger
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Rule, Select, Static, Switch


class SettingRow(Horizontal):
    """A single setting row with label and control."""

    DEFAULT_CSS = """
    SettingRow {
        width: 100%;
        height: auto;
        min-height: 3;
        padding: 1 0;
        margin: 0 1;
        border-bottom: solid $surface-lighten-1;
        align: left middle;
    }

    SettingRow .setting-label {
        width: 18;
        height: auto;
        color: $text;
        text-style: bold;
    }

    SettingRow .setting-description {
        width: 1fr;
        color: $text-muted;
        height: auto;
        padding: 0 2;
    }

    SettingRow .setting-control {
        width: 35;
        height: auto;
    }
    """


class ConfigScreen(Container):
    """Config content (Container for ContentSwitcher)."""

    BINDINGS = [
        Binding("ctrl+s", "save_config", "^S:Save", show=True, priority=True),
        Binding("ctrl+r", "reload_config", "^R:Reload", show=True),
        Binding("ctrl+t", "test_connection", "^T:Test", show=True),
    ]

    DEFAULT_CSS = """
    ConfigScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }

    #config-header {
        height: 3;
        padding: 0 1;
        border-bottom: solid $primary;
        background: $surface-darken-1;
    }

    #config-content {
        height: 1fr;
        padding: 1;
    }

    .config-section {
        border: solid $surface-lighten-2;
        margin: 1 0;
        padding: 1;
        background: $surface;
    }

    .section-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .section-description {
        color: $text-muted;
        margin-bottom: 1;
    }

    #config-actions {
        height: 4;
        padding: 1;
        border-top: solid $primary;
        background: $surface-darken-1;
    }

    #config-actions Button {
        margin: 0 1;
    }

    .status-ok {
        color: $success;
    }

    .status-error {
        color: $error;
    }

    .status-warning {
        color: $warning;
    }
    """

    has_changes = reactive(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._config: dict[str, Any] = {}
        self._available_models: list = []
        self._load_config()

    def _load_tui_preferences(self) -> dict[str, Any]:
        """Load TUI preferences from JSON file."""
        from src.cli.constants import PROJECT_ROOT

        prefs_path = PROJECT_ROOT / ".tui_preferences.json"
        if prefs_path.exists():
            try:
                with open(prefs_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load TUI preferences: {e}")
        return {"theme": "dark"}

    def _save_tui_preferences(self) -> None:
        """Save TUI preferences to JSON file."""
        from src.cli.constants import PROJECT_ROOT

        prefs_path = PROJECT_ROOT / ".tui_preferences.json"
        try:
            with open(prefs_path, "w") as f:
                json.dump(self._tui_prefs, f, indent=2)
            logger.info("TUI preferences saved")
        except Exception as e:
            logger.error(f"Could not save TUI preferences: {e}")

    def _load_config(self) -> None:
        """Load configuration directly from .env file."""
        from src.cli.constants import PROJECT_ROOT

        env_path = PROJECT_ROOT / ".env"
        env_vars = {}

        # Read .env file directly
        if env_path.exists():
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            env_vars[key.strip()] = value.strip()
            except Exception as e:
                logger.warning(f"Could not read .env: {e}")

        # Load TUI preferences from separate file
        self._tui_prefs = self._load_tui_preferences()

        # Map env vars to config with defaults
        self._config = {
            # Application
            "app_name": env_vars.get("APP_NAME", "Tawiza"),
            "app_env": env_vars.get("APP_ENV", "development"),
            "debug": env_vars.get("DEBUG", "false").lower() == "true",
            "log_level": env_vars.get("LOG_LEVEL", "INFO"),
            # Appearance (from TUI prefs)
            "theme": self._tui_prefs.get("theme", "dark"),
            # Ollama
            "ollama_url": env_vars.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            "ollama_model": env_vars.get("OLLAMA_MODEL_NAME", "qwen3.5:27b"),
            "ollama_temperature": float(env_vars.get("OLLAMA_TEMPERATURE", "0.7")),
            "ollama_timeout": int(env_vars.get("OLLAMA_TIMEOUT", "300")),
            # Database
            "db_pool_size": int(env_vars.get("DATABASE_POOL_SIZE", "10")),
            "db_echo": env_vars.get("DATABASE_ECHO", "false").lower() == "true",
            # API
            "api_host": env_vars.get("API_HOST", "0.0.0.0"),
            "api_port": int(env_vars.get("API_PORT", "8000")),
            # Redis
            "redis_url": env_vars.get("REDIS_URL", "redis://localhost:6379/0"),
            # VectorDB
            "vectordb_enabled": env_vars.get("VECTORDB_ENABLED", "true").lower() == "true",
            "vectordb_chunk_size": int(env_vars.get("VECTORDB_CHUNK_SIZE", "512")),
        }

        logger.debug(f"Loaded config: {len(self._config)} settings from .env")

    def _get_defaults(self) -> dict[str, Any]:
        """Get default configuration values."""
        return {
            "app_name": "Tawiza",
            "app_env": "development",
            "debug": False,
            "log_level": "INFO",
            "ollama_url": "http://localhost:11434",
            "ollama_model": "qwen3.5:27b",
            "ollama_temperature": 0.7,
            "ollama_timeout": 300,
            "db_pool_size": 10,
            "db_echo": False,
            "api_host": "0.0.0.0",
            "api_port": 8000,
            "redis_url": "redis://localhost:6379/0",
            "vectordb_enabled": True,
            "vectordb_chunk_size": 512,
        }

    def compose(self) -> ComposeResult:
        """Create the config layout."""
        # Header
        with Horizontal(id="config-header"):
            yield Static("[bold cyan]CONFIG[/] - Tawiza Application Settings")
            yield Static("", id="config-status")

        # Content
        with ScrollableContainer(id="config-content"):
            # Ollama Section
            with Vertical(classes="config-section"):
                yield Static("[bold cyan]Ollama LLM Settings[/]", classes="section-title")
                yield Static("Configure the local LLM connection", classes="section-description")

                with SettingRow():
                    yield Static("Ollama URL", classes="setting-label")
                    yield Static("API endpoint for Ollama", classes="setting-description")
                    yield Input(
                        value=self._config.get("ollama_url", ""),
                        placeholder="http://localhost:11434",
                        id="setting-ollama_url",
                        classes="setting-control",
                    )

                with SettingRow():
                    yield Static("Model", classes="setting-label")
                    yield Static("Default LLM model", classes="setting-description")
                    yield Select(
                        [("Loading...", "")],
                        allow_blank=True,
                        id="setting-ollama_model",
                        classes="setting-control",
                    )

                with SettingRow():
                    yield Static("Temperature", classes="setting-label")
                    yield Static("Response creativity (0.0-2.0)", classes="setting-description")
                    yield Input(
                        value=str(self._config.get("ollama_temperature", 0.7)),
                        placeholder="0.7",
                        id="setting-ollama_temperature",
                        classes="setting-control",
                    )

                with SettingRow():
                    yield Static("Timeout", classes="setting-label")
                    yield Static("Request timeout in seconds", classes="setting-description")
                    yield Input(
                        value=str(self._config.get("ollama_timeout", 300)),
                        placeholder="300",
                        id="setting-ollama_timeout",
                        classes="setting-control",
                    )

            yield Rule()

            # Application Section
            with Vertical(classes="config-section"):
                yield Static("[bold cyan]Application Settings[/]", classes="section-title")
                yield Static("General application configuration", classes="section-description")

                with SettingRow():
                    yield Static("Environment", classes="setting-label")
                    yield Static("Application environment", classes="setting-description")
                    yield Select(
                        [
                            ("Development", "development"),
                            ("Production", "production"),
                            ("Testing", "testing"),
                        ],
                        value=self._config.get("app_env", "development"),
                        id="setting-app_env",
                        classes="setting-control",
                    )

                with SettingRow():
                    yield Static("Debug Mode", classes="setting-label")
                    yield Static("Enable debug logging", classes="setting-description")
                    yield Switch(
                        value=self._config.get("debug", False),
                        id="setting-debug",
                        classes="setting-control",
                    )

                with SettingRow():
                    yield Static("Log Level", classes="setting-label")
                    yield Static("Minimum log level", classes="setting-description")
                    yield Select(
                        [
                            ("DEBUG", "DEBUG"),
                            ("INFO", "INFO"),
                            ("WARNING", "WARNING"),
                            ("ERROR", "ERROR"),
                        ],
                        value=self._config.get("log_level", "INFO"),
                        id="setting-log_level",
                        classes="setting-control",
                    )

            yield Rule()

            # Appearance Section
            with Vertical(classes="config-section"):
                yield Static("[bold cyan]Appearance[/]", classes="section-title")
                yield Static("Theme applied on next TUI launch", classes="section-description")

                with SettingRow():
                    yield Static("Theme", classes="setting-label")
                    yield Static("Color scheme for TUI", classes="setting-description")
                    # Use all available Textual themes
                    theme_options = [
                        ("Dracula", "dracula"),
                        ("Nord", "nord"),
                        ("Tokyo Night", "tokyo-night"),
                        ("Monokai", "monokai"),
                        ("Gruvbox", "gruvbox"),
                        ("Catppuccin Mocha", "catppuccin-mocha"),
                        ("Catppuccin Latte", "catppuccin-latte"),
                        ("Solarized Light", "solarized-light"),
                        ("Textual Dark", "textual-dark"),
                        ("Textual Light", "textual-light"),
                    ]
                    valid_themes = [t[1] for t in theme_options]
                    saved_theme = self._tui_prefs.get("theme", "dracula")
                    # Fallback to dracula if saved theme is invalid
                    theme_value = saved_theme if saved_theme in valid_themes else "dracula"
                    yield Select(
                        theme_options,
                        value=theme_value,
                        id="setting-theme",
                        classes="setting-control",
                    )

            yield Rule()

            # API Section
            with Vertical(classes="config-section"):
                yield Static("[bold cyan]API Settings[/]", classes="section-title")
                yield Static("REST API server configuration", classes="section-description")

                with SettingRow():
                    yield Static("API Host", classes="setting-label")
                    yield Static("Server bind address", classes="setting-description")
                    yield Input(
                        value=self._config.get("api_host", "0.0.0.0"),
                        placeholder="0.0.0.0",
                        id="setting-api_host",
                        classes="setting-control",
                    )

                with SettingRow():
                    yield Static("API Port", classes="setting-label")
                    yield Static("Server port number", classes="setting-description")
                    yield Input(
                        value=str(self._config.get("api_port", 8000)),
                        placeholder="8000",
                        id="setting-api_port",
                        classes="setting-control",
                    )

            yield Rule()

            # Database Section
            with Vertical(classes="config-section"):
                yield Static("[bold cyan]Database Settings[/]", classes="section-title")
                yield Static("PostgreSQL connection settings", classes="section-description")

                with SettingRow():
                    yield Static("Pool Size", classes="setting-label")
                    yield Static("Connection pool size", classes="setting-description")
                    yield Input(
                        value=str(self._config.get("db_pool_size", 10)),
                        placeholder="10",
                        id="setting-db_pool_size",
                        classes="setting-control",
                    )

                with SettingRow():
                    yield Static("Echo SQL", classes="setting-label")
                    yield Static("Log SQL queries", classes="setting-description")
                    yield Switch(
                        value=self._config.get("db_echo", False),
                        id="setting-db_echo",
                        classes="setting-control",
                    )

            yield Rule()

            # Redis Section
            with Vertical(classes="config-section"):
                yield Static("[bold cyan]Redis Settings[/]", classes="section-title")
                yield Static("Redis cache configuration", classes="section-description")

                with SettingRow():
                    yield Static("Redis URL", classes="setting-label")
                    yield Static("Redis connection URL", classes="setting-description")
                    yield Input(
                        value=self._config.get("redis_url", ""),
                        placeholder="redis://localhost:6379/0",
                        id="setting-redis_url",
                        classes="setting-control",
                    )

            yield Rule()

            # VectorDB Section
            with Vertical(classes="config-section"):
                yield Static("[bold cyan]Vector Database[/]", classes="section-title")
                yield Static("Embedding storage settings", classes="section-description")

                with SettingRow():
                    yield Static("Enabled", classes="setting-label")
                    yield Static("Enable vector storage", classes="setting-description")
                    yield Switch(
                        value=self._config.get("vectordb_enabled", True),
                        id="setting-vectordb_enabled",
                        classes="setting-control",
                    )

                with SettingRow():
                    yield Static("Chunk Size", classes="setting-label")
                    yield Static("Document chunk size", classes="setting-description")
                    yield Input(
                        value=str(self._config.get("vectordb_chunk_size", 512)),
                        placeholder="512",
                        id="setting-vectordb_chunk_size",
                        classes="setting-control",
                    )

            yield Rule()

            # Service Status Section
            with Vertical(classes="config-section"):
                yield Static("[bold cyan]Service Status[/]", classes="section-title")
                yield Static("Current connection status", classes="section-description")
                yield Static("", id="service-status")

        # Action buttons
        with Horizontal(id="config-actions"):
            yield Button("Save Config", variant="primary", id="btn-save")
            yield Button("Reload", variant="default", id="btn-reload")
            yield Button("Test Connections", variant="warning", id="btn-test")

    def on_mount(self) -> None:
        """Initialize on mount."""
        self._update_status()
        # Use run_worker to properly schedule async coroutines
        self.run_worker(self._check_services())
        self.run_worker(self._load_ollama_models())

    def _update_status(self) -> None:
        """Update the status indicator."""
        status = self.query_one("#config-status", Static)
        if self.has_changes:
            status.update("[yellow]● Unsaved changes[/]")
        else:
            status.update("[green]● Saved[/]")

    async def _check_services(self) -> None:
        """Check service connection status."""
        status_widget = self.query_one("#service-status", Static)

        lines = []

        # Check Ollama
        ollama_status = await self._check_ollama()
        if ollama_status:
            lines.append(f"[green]●[/] Ollama: Connected ({ollama_status})")
        else:
            lines.append("[red]○[/] Ollama: Not connected")

        # Check Redis
        redis_status = await self._check_redis()
        if redis_status:
            lines.append("[green]●[/] Redis: Connected")
        else:
            lines.append("[yellow]○[/] Redis: Not connected")

        # Check Database
        db_status = await self._check_database()
        if db_status:
            lines.append("[green]●[/] Database: Connected")
        else:
            lines.append("[yellow]○[/] Database: Not connected")

        status_widget.update("\n".join(lines))

    async def _check_ollama(self) -> str | None:
        """Check Ollama connection."""
        try:
            import httpx

            url = self._config.get("ollama_url", "http://localhost:11434")
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return f"{len(models)} models"
        except Exception as e:
            logger.debug(f"Ollama check failed: {e}")
        return None

    async def _load_ollama_models(self) -> None:
        """Load available Ollama models and update the Select widget."""
        try:
            import httpx

            url = self._config.get("ollama_url", "http://localhost:11434")
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])

                    if models:
                        # Build options list with model name and size
                        options = []
                        for m in models:
                            name = m.get("name", "unknown")
                            size_bytes = m.get("size", 0)
                            size_gb = size_bytes / (1024**3)
                            display = f"{name} ({size_gb:.1f}GB)" if size_gb > 0.1 else name
                            options.append((display, name))

                        # Update the Select widget
                        try:
                            model_select = self.query_one("#setting-ollama_model", Select)
                            model_select.set_options(options)

                            # Set current value if it exists in the list
                            current = self._config.get("ollama_model", "")
                            if any(opt[1] == current for opt in options):
                                model_select.value = current
                            elif options:
                                model_select.value = options[0][1]

                            self._available_models = [m["name"] for m in models]
                            logger.debug(f"Loaded {len(options)} Ollama models")
                        except Exception as e:
                            logger.debug(f"Could not update model select: {e}")
        except Exception as e:
            logger.debug(f"Could not load Ollama models: {e}")

    async def _check_redis(self) -> bool:
        """Check Redis connection."""
        try:
            import redis.asyncio as aioredis

            url = self._config.get("redis_url", "redis://localhost:6379/0")
            # Parse password from URL if present
            client = aioredis.from_url(url, decode_responses=True)
            await client.ping()
            await client.close()
            return True
        except Exception as e:
            logger.debug(f"Redis check failed: {e}")
            # SECURITY: No hardcoded fallback - use REDIS_URL or REDIS_PASSWORD env var
            redis_password = os.environ.get("REDIS_PASSWORD")
            if redis_password:
                try:
                    import redis.asyncio as aioredis

                    client = aioredis.Redis(
                        host="localhost", port=6379, password=redis_password, decode_responses=True
                    )
                    await client.ping()
                    await client.close()
                    return True
                except Exception:
                    pass
        return False

    async def _check_database(self) -> bool:
        """Check database connection."""
        try:
            import asyncpg

            # Get database URL from .env
            from src.cli.constants import PROJECT_ROOT

            env_path = PROJECT_ROOT / ".env"
            db_url = None
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("DATABASE_URL="):
                            db_url = line.split("=", 1)[1].strip()
                            break
            if db_url:
                # Convert SQLAlchemy URL to asyncpg format
                # postgresql+asyncpg://user:pass@host:port/db -> postgresql://user:pass@host:port/db
                if "+asyncpg" in db_url:
                    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
                conn = await asyncpg.connect(db_url, timeout=5.0)
                await conn.close()
                return True
        except Exception as e:
            logger.debug(f"Database check failed: {e}")
        return False

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch changes."""
        setting_id = event.switch.id
        if setting_id and setting_id.startswith("setting-"):
            key = setting_id.replace("setting-", "")
            self._config[key] = event.value
            self.has_changes = True
            self._update_status()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select changes."""
        setting_id = event.select.id
        if setting_id and setting_id.startswith("setting-"):
            key = setting_id.replace("setting-", "")
            self._config[key] = event.value

            # Handle theme change - save and apply for next launch
            if key == "theme" and event.value:
                self._apply_theme_for_next_launch(str(event.value))
            else:
                self.has_changes = True
                self._update_status()

    def _apply_theme_for_next_launch(self, theme: str) -> None:
        """Save theme preference and copy theme file for next launch."""
        import shutil

        try:
            # Update TUI preferences
            self._tui_prefs["theme"] = theme
            self._save_tui_preferences()

            # Copy the selected theme to theme.tcss
            from src.cli.constants import PROJECT_ROOT

            styles_dir = PROJECT_ROOT / "src" / "cli" / "v3" / "tui" / "styles"
            theme_file = styles_dir / f"theme-{theme}.tcss"
            target_file = styles_dir / "theme.tcss"

            if theme_file.exists():
                shutil.copy(theme_file, target_file)
                self.app.notify(f"Theme '{theme}' will apply on next launch", timeout=3)
                logger.info(f"Theme set to {theme}")
            else:
                self.app.notify(f"Theme file not found: {theme_file}", timeout=3)

        except Exception as e:
            logger.error(f"Failed to set theme: {e}")
            self.app.notify(f"Failed to set theme: {e}", timeout=3)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        setting_id = event.input.id
        if setting_id and setting_id.startswith("setting-"):
            key = setting_id.replace("setting-", "")
            self._config[key] = event.value
            self.has_changes = True
            self._update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-save":
            self.action_save_config()
        elif event.button.id == "btn-reload":
            self.action_reload_config()
        elif event.button.id == "btn-test":
            self.action_test_connection()

    def action_save_config(self) -> None:
        """Save configuration to .env file."""
        try:
            from src.cli.constants import PROJECT_ROOT

            env_path = PROJECT_ROOT / ".env"

            # Read existing .env
            env_vars = {}
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            env_vars[key] = value

            # Update with new values
            env_vars["OLLAMA_BASE_URL"] = self._config.get("ollama_url", "")
            env_vars["OLLAMA_MODEL_NAME"] = self._config.get("ollama_model", "")
            env_vars["OLLAMA_TEMPERATURE"] = str(self._config.get("ollama_temperature", 0.7))
            env_vars["OLLAMA_TIMEOUT"] = str(self._config.get("ollama_timeout", 300))
            env_vars["APP_ENV"] = self._config.get("app_env", "development")
            env_vars["DEBUG"] = str(self._config.get("debug", False)).lower()
            env_vars["LOG_LEVEL"] = self._config.get("log_level", "INFO")
            env_vars["API_HOST"] = self._config.get("api_host", "0.0.0.0")
            env_vars["API_PORT"] = str(self._config.get("api_port", 8000))
            env_vars["DATABASE_POOL_SIZE"] = str(self._config.get("db_pool_size", 10))
            env_vars["DATABASE_ECHO"] = str(self._config.get("db_echo", False)).lower()
            env_vars["REDIS_URL"] = self._config.get("redis_url", "")
            env_vars["VECTORDB_ENABLED"] = str(self._config.get("vectordb_enabled", True)).lower()
            env_vars["VECTORDB_CHUNK_SIZE"] = str(self._config.get("vectordb_chunk_size", 512))

            # Write back
            with open(env_path, "w") as f:
                f.write("# Tawiza Configuration\n")
                f.write("# Generated by TUI Config Screen\n\n")
                for key, value in sorted(env_vars.items()):
                    f.write(f"{key}={value}\n")

            self.has_changes = False
            self._update_status()
            self.app.notify("Configuration saved to .env!", timeout=2)
            logger.info("Config saved to .env")

        except Exception as e:
            self.app.notify(f"Failed to save: {e}", timeout=3)
            logger.error(f"Failed to save config: {e}")

    def action_reload_config(self) -> None:
        """Reload configuration from settings."""
        self._load_config()
        self.has_changes = False
        self._update_status()
        self.app.notify("Configuration reloaded", timeout=2)

    async def action_test_connection(self) -> None:
        """Test all service connections."""
        self.app.notify("Testing connections...", timeout=1)
        await self._check_services()
        self.app.notify("Connection test complete", timeout=2)
