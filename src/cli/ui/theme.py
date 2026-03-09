"""UI Theme constants for Tawiza-V2 CLI.

This module centralizes all theme colors and UI styling constants
to ensure consistency across the CLI interface.
"""
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Theme:
    """Immutable theme configuration.

    Using a dataclass ensures type safety and immutability.
    """
    header_color: str
    accent_color: str
    success_color: str
    info_color: str
    warning_color: str
    error_color: str
    text_color: str
    dim_color: str


# ============================================================================
# Sunset Theme (Default)
# ============================================================================
SUNSET_THEME: Final[Theme] = Theme(
    header_color="#FF6B35",
    accent_color="#F7931E",
    success_color="#FFD23F",
    info_color="#06FFA5",
    warning_color="#FF8E53",
    error_color="#FF5252",
    text_color="#F0F0F0",
    dim_color="#B0B0B0"
)


# ============================================================================
# Dark Theme (Alternative)
# ============================================================================
DARK_THEME: Final[Theme] = Theme(
    header_color="#7C3AED",
    accent_color="#8B5CF6",
    success_color="#10B981",
    info_color="#3B82F6",
    warning_color="#F59E0B",
    error_color="#EF4444",
    text_color="#E5E7EB",
    dim_color="#9CA3AF"
)


# ============================================================================
# Light Theme (Alternative)
# ============================================================================
LIGHT_THEME: Final[Theme] = Theme(
    header_color="#6366F1",
    accent_color="#8B5CF6",
    success_color="#059669",
    info_color="#0284C7",
    warning_color="#D97706",
    error_color="#DC2626",
    text_color="#1F2937",
    dim_color="#6B7280"
)


# ============================================================================
# No-Color Theme (For terminals without color support)
# ============================================================================
NO_COLOR_THEME: Final[Theme] = Theme(
    header_color="white",
    accent_color="white",
    success_color="white",
    info_color="white",
    warning_color="white",
    error_color="white",
    text_color="white",
    dim_color="white"
)


# ============================================================================
# Default Theme
# ============================================================================
DEFAULT_THEME: Final[Theme] = SUNSET_THEME


# ============================================================================
# Theme Registry
# ============================================================================
THEMES: Final[dict[str, Theme]] = {
    "sunset": SUNSET_THEME,
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
    "no-color": NO_COLOR_THEME,
}


def get_theme(name: str = "sunset") -> Theme:
    """Get theme by name with fallback to default.

    Args:
        name: Theme name (sunset, dark, light, no-color)

    Returns:
        Theme configuration

    Example:
        >>> theme = get_theme("sunset")
        >>> print(theme.header_color)
        #FF6B35
    """
    return THEMES.get(name.lower(), DEFAULT_THEME)


def list_themes() -> list[str]:
    """List all available theme names.

    Returns:
        List of theme names
    """
    return list(THEMES.keys())


def theme_to_dict(theme: Theme) -> dict[str, str]:
    """Convert theme to dictionary for backward compatibility.

    Args:
        theme: Theme instance

    Returns:
        Dictionary representation
    """
    return {
        "header_color": theme.header_color,
        "accent_color": theme.accent_color,
        "success_color": theme.success_color,
        "info_color": theme.info_color,
        "warning_color": theme.warning_color,
        "error_color": theme.error_color,
        "text_color": theme.text_color,
        "dim_color": theme.dim_color,
    }


# ============================================================================
# ASCII Art and Decorations
# ============================================================================

HEADER_SUNSET_ASCII: Final[str] = """
╔══════════════════════════════════════════════════════════════╗
║              🌅 Tawiza-V2 - Sunset Interface 🌅              ║
║         Système Multi-Agents IA Avancé & GPU ROCm          ║
╚══════════════════════════════════════════════════════════════╝
"""

SEPARATOR_LINE: Final[str] = "─" * 60
SEPARATOR_DOUBLE: Final[str] = "═" * 60
SEPARATOR_THICK: Final[str] = "━" * 60


# ============================================================================
# Box Styles (for rich.box)
# ============================================================================
BOX_STYLE_HEADER: Final[str] = "DOUBLE"
BOX_STYLE_TABLE: Final[str] = "ROUNDED"
BOX_STYLE_PANEL: Final[str] = "HEAVY"
BOX_STYLE_CODE: Final[str] = "SQUARE"


# ============================================================================
# Progress Bar Styles
# ============================================================================
PROGRESS_BAR_COMPLETE: Final[str] = "█"
PROGRESS_BAR_INCOMPLETE: Final[str] = "░"
PROGRESS_BAR_WIDTH: Final[int] = 40


# ============================================================================
# Table Styling
# ============================================================================
TABLE_PADDING: Final[tuple[int, int]] = (0, 1)  # (vertical, horizontal)
TABLE_MIN_WIDTH: Final[int] = 60
TABLE_MAX_WIDTH: Final[int] = 120


# ============================================================================
# Panel Styling
# ============================================================================
PANEL_PADDING: Final[int] = 1
PANEL_EXPAND: Final[bool] = False


# ============================================================================
# Status Messages
# ============================================================================
MSG_SYSTEM_INITIALIZING: Final[str] = "⚡ Initialisation du système Tawiza-V2..."
MSG_SYSTEM_INITIALIZED: Final[str] = "✅ Système Tawiza-V2 initialisé avec succès!"
MSG_SYSTEM_STOPPING: Final[str] = "🛑 Arrêt du système Tawiza-V2..."
MSG_SYSTEM_STOPPED: Final[str] = "✅ Système Tawiza-V2 arrêté avec succès!"
MSG_SYSTEM_RESTARTING: Final[str] = "🔄 Redémarrage du système Tawiza-V2..."
MSG_SYSTEM_NOT_INITIALIZED: Final[str] = "⚠️  Le système n'est pas initialisé."
MSG_DEBUG_STARTING: Final[str] = "🐛 Démarrage du système de débogage..."
MSG_DEBUG_STARTED: Final[str] = "✅ Système de débogage démarré!"


# ============================================================================
# Emoji Sets
# ============================================================================

class Emoji:
    """Emoji constants for consistent usage."""

    # System
    ROCKET: Final[str] = "🚀"
    GEAR: Final[str] = "⚙️"
    LIGHTNING: Final[str] = "⚡"
    STOP: Final[str] = "🛑"
    REFRESH: Final[str] = "🔄"

    # Status
    SUCCESS: Final[str] = "✅"
    WARNING: Final[str] = "⚠️"
    ERROR: Final[str] = "❌"
    INFO: Final[str] = "ℹ️"

    # Progress
    HOURGLASS: Final[str] = "⏳"
    CLOCK: Final[str] = "⏰"
    CHECKMARK: Final[str] = "✓"
    CROSSMARK: Final[str] = "✗"

    # Components
    BUG: Final[str] = "🐛"
    MAGNIFIER: Final[str] = "🔍"
    BRAIN: Final[str] = "🧠"
    ROBOT: Final[str] = "🤖"
    CHART: Final[str] = "📊"
    CODE: Final[str] = "💻"
    GPU: Final[str] = "🎮"
    NETWORK: Final[str] = "🌐"
    DATABASE: Final[str] = "💾"

    # Actions
    FOLDER: Final[str] = "📁"
    FILE: Final[str] = "📄"
    CLIPBOARD: Final[str] = "📋"
    SAVE: Final[str] = "💾"
    LOAD: Final[str] = "📂"

    # Misc
    FIRE: Final[str] = "🔥"
    STAR: Final[str] = "⭐"
    SPARKLES: Final[str] = "✨"
    SUNSET: Final[str] = "🌅"
    BULB: Final[str] = "💡"


# ============================================================================
# Helper Functions for Backward Compatibility
# ============================================================================

from rich import box
from rich.align import Align
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Singleton theme instance for compatibility with theme_sunset imports
sunset_theme = theme_to_dict(SUNSET_THEME)


def get_sunset_banner(text: str, subtitle: str = None) -> Panel:
    """Create a sunset-styled banner panel.

    Args:
        text: Main banner text
        subtitle: Optional subtitle

    Returns:
        Rich Panel with sunset styling
    """
    content = Text()
    content.append(text, style=f"bold {SUNSET_THEME.header_color}")
    if subtitle:
        content.append(f"\n{subtitle}", style=f"{SUNSET_THEME.dim_color}")

    return Panel(
        Align.center(content),
        border_style=SUNSET_THEME.accent_color,
        box=box.DOUBLE,
        padding=1
    )


def get_sunset_table(title: str, columns: list = None) -> Table:
    """Create a sunset-styled table.

    Args:
        title: Table title
        columns: List of column names (optional)

    Returns:
        Rich Table with sunset styling
    """
    table = Table(
        title=f"[bold {SUNSET_THEME.header_color}]{title}[/]",
        border_style=SUNSET_THEME.accent_color,
        header_style=f"bold {SUNSET_THEME.info_color}",
        box=box.ROUNDED
    )

    if columns:
        for col in columns:
            table.add_column(col, style=SUNSET_THEME.text_color)

    return table


def get_animated_status(status: str, message: str) -> Panel:
    """Create an animated status panel.

    Args:
        status: Status type (success, error, warning, info, running)
        message: Status message

    Returns:
        Rich Panel with status styling
    """
    status_styles = {
        "success": (SUNSET_THEME.success_color, Emoji.SUCCESS),
        "error": (SUNSET_THEME.error_color, Emoji.ERROR),
        "warning": (SUNSET_THEME.warning_color, Emoji.WARNING),
        "info": (SUNSET_THEME.info_color, Emoji.INFO),
        "running": (SUNSET_THEME.accent_color, Emoji.HOURGLASS),
    }

    color, icon = status_styles.get(status, (SUNSET_THEME.text_color, ""))

    content = Text()
    content.append(f"{icon} ", style=color)
    content.append(message, style=f"bold {color}")

    return Panel(
        Align.center(content),
        border_style=color,
        box=box.ROUNDED,
        padding=(0, 2)
    )
