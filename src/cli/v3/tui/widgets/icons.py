"""Icons and Visual Indicators - Unicode symbols for TUI.

This module provides a collection of Unicode icons and visual indicators
for use throughout the TUI interface.
"""



class Icons:
    """Collection of Unicode icons organized by category."""

    # =========================================================================
    # Status Indicators
    # =========================================================================
    STATUS_OK = "●"           # Filled circle - online/active
    STATUS_ERROR = "○"        # Empty circle - offline/error
    STATUS_WARNING = "◌"      # Dotted circle - warning
    STATUS_PENDING = "◐"      # Half circle - pending
    STATUS_RUNNING = "◉"      # Target circle - running
    STATUS_PAUSED = "◎"       # Double circle - paused

    # Checkmarks and crosses
    CHECK = "✓"
    CHECK_BOLD = "✔"
    CROSS = "✗"
    CROSS_BOLD = "✘"

    # =========================================================================
    # Arrows and Navigation
    # =========================================================================
    ARROW_RIGHT = "→"
    ARROW_LEFT = "←"
    ARROW_UP = "↑"
    ARROW_DOWN = "↓"
    ARROW_DOUBLE_RIGHT = "»"
    ARROW_DOUBLE_LEFT = "«"
    ARROW_RETURN = "↵"

    # Triangles (for expandable items)
    TRIANGLE_RIGHT = "▶"
    TRIANGLE_DOWN = "▼"
    TRIANGLE_UP = "▲"
    TRIANGLE_LEFT = "◀"

    # =========================================================================
    # Progress and Loading
    # =========================================================================
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    PROGRESS_EMPTY = "░"
    PROGRESS_HALF = "▒"
    PROGRESS_FULL = "█"
    HOURGLASS = "⏳"
    CLOCK = "⏰"

    # =========================================================================
    # File Types
    # =========================================================================
    FOLDER = "📁"
    FOLDER_OPEN = "📂"
    FILE = "📄"
    FILE_CODE = "📝"
    FILE_IMAGE = "🖼"
    FILE_CONFIG = "⚙"

    # Simple folder/file (more compatible)
    FOLDER_SIMPLE = "▸"
    FILE_SIMPLE = "•"

    # =========================================================================
    # Agent Types
    # =========================================================================
    AGENT_GENERAL = "🤖"
    AGENT_BROWSER = "🌐"
    AGENT_CODER = "💻"
    AGENT_DATA = "📊"
    ROBOT = "⚙"

    # Simple agent icons (more compatible)
    AGENT_SIMPLE = "◆"
    BROWSER_SIMPLE = "◇"

    # =========================================================================
    # Actions
    # =========================================================================
    PLAY = "▶"
    PAUSE = "⏸"
    STOP = "⏹"
    REFRESH = "↻"
    SYNC = "⇄"
    EDIT = "✎"
    DELETE = "✖"
    ADD = "＋"
    REMOVE = "－"
    SEARCH = "🔍"
    SETTINGS = "⚙"
    SAVE = "💾"
    COPY = "📋"

    # =========================================================================
    # Alerts and Notifications
    # =========================================================================
    INFO = "ℹ"
    WARNING = "⚠"
    ERROR = "✖"
    SUCCESS = "✔"
    BELL = "🔔"
    LIGHTNING = "⚡"
    FIRE = "🔥"
    BUG = "🐛"

    # =========================================================================
    # Metrics and Charts
    # =========================================================================
    CHART_BAR = "📊"
    CHART_LINE = "📈"
    CHART_DOWN = "📉"
    GAUGE = "🎯"
    CPU = "💻"
    MEMORY = "🧠"
    DISK = "💿"
    NETWORK = "🌐"
    GPU = "🎮"

    # Sparkline blocks
    BLOCKS = " ▁▂▃▄▅▆▇█"

    # =========================================================================
    # Communication
    # =========================================================================
    CHAT = "💬"
    MESSAGE = "✉"
    SEND = "➤"
    USER = "👤"
    ASSISTANT = "🤖"

    # =========================================================================
    # Borders and Decorations
    # =========================================================================
    BOX_TOP_LEFT = "╭"
    BOX_TOP_RIGHT = "╮"
    BOX_BOTTOM_LEFT = "╰"
    BOX_BOTTOM_RIGHT = "╯"
    BOX_HORIZONTAL = "─"
    BOX_VERTICAL = "│"

    DOUBLE_TOP_LEFT = "╔"
    DOUBLE_TOP_RIGHT = "╗"
    DOUBLE_BOTTOM_LEFT = "╚"
    DOUBLE_BOTTOM_RIGHT = "╝"
    DOUBLE_HORIZONTAL = "═"
    DOUBLE_VERTICAL = "║"

    DIVIDER = "─" * 40
    DIVIDER_DOUBLE = "═" * 40


class StatusBadge:
    """Generate status badges with icons and colors."""

    STYLES: dict[str, tuple] = {
        # (icon, color)
        "online": (Icons.STATUS_OK, "green"),
        "offline": (Icons.STATUS_ERROR, "red"),
        "warning": (Icons.STATUS_WARNING, "yellow"),
        "pending": (Icons.STATUS_PENDING, "dim"),
        "running": (Icons.STATUS_RUNNING, "cyan"),
        "paused": (Icons.STATUS_PAUSED, "yellow"),
        "completed": (Icons.CHECK, "green"),
        "failed": (Icons.CROSS, "red"),
        "success": (Icons.SUCCESS, "green"),
        "error": (Icons.ERROR, "red"),
        "info": (Icons.INFO, "blue"),
    }

    @classmethod
    def get(cls, status: str, text: str = "") -> str:
        """Get a formatted status badge.

        Args:
            status: Status key (online, offline, running, etc.)
            text: Optional text to display after icon

        Returns:
            Rich-formatted string with icon and color
        """
        icon, color = cls.STYLES.get(status, (Icons.STATUS_PENDING, "dim"))
        if text:
            return f"[{color}]{icon} {text}[/]"
        return f"[{color}]{icon}[/]"


class AgentBadge:
    """Generate agent type badges."""

    AGENTS: dict[str, tuple] = {
        # (icon, color, label)
        "general": (Icons.ROBOT, "cyan", "General"),
        "browser": (Icons.NETWORK, "blue", "Browser"),
        "coder": (Icons.FILE_CODE, "green", "Coder"),
        "data": (Icons.CHART_BAR, "yellow", "Data"),
        "system": (Icons.SETTINGS, "dim", "System"),
    }

    @classmethod
    def get(cls, agent: str, show_label: bool = True) -> str:
        """Get a formatted agent badge.

        Args:
            agent: Agent type (general, browser, coder, data)
            show_label: Whether to show the label text

        Returns:
            Rich-formatted string with icon and color
        """
        icon, color, label = cls.AGENTS.get(agent, ("◆", "dim", agent))
        if show_label:
            return f"[{color}]{icon} {label}[/]"
        return f"[{color}]{icon}[/]"


class ProgressBar:
    """Generate text-based progress bars."""

    @classmethod
    def render(
        cls,
        value: float,
        max_value: float = 100,
        width: int = 20,
        show_percent: bool = True,
        color_thresholds: bool = True
    ) -> str:
        """Render a progress bar.

        Args:
            value: Current value
            max_value: Maximum value
            width: Bar width in characters
            show_percent: Show percentage after bar
            color_thresholds: Use color based on percentage

        Returns:
            Rich-formatted progress bar string
        """
        if max_value == 0:
            max_value = 1

        pct = min(100, max(0, value / max_value * 100))
        filled = int(width * pct / 100)
        empty = width - filled

        # Choose color
        if color_thresholds:
            if pct < 50:
                color = "green"
            elif pct < 80:
                color = "yellow"
            else:
                color = "red"
        else:
            color = "primary"

        bar = f"[{color}]{Icons.PROGRESS_FULL * filled}[/][dim]{Icons.PROGRESS_EMPTY * empty}[/]"

        if show_percent:
            return f"{bar} [{color}]{pct:.0f}%[/]"
        return bar


class Spinner:
    """Animated spinner for loading states."""

    def __init__(self):
        self._frame = 0
        self._frames = Icons.SPINNER_FRAMES

    def next(self) -> str:
        """Get the next spinner frame."""
        frame = self._frames[self._frame]
        self._frame = (self._frame + 1) % len(self._frames)
        return f"[cyan]{frame}[/]"

    def reset(self) -> None:
        """Reset spinner to first frame."""
        self._frame = 0


# Common icon sets for quick access
FILE_ICONS = {
    ".py": "🐍",
    ".js": "📜",
    ".ts": "📘",
    ".json": "📋",
    ".yaml": "📋",
    ".yml": "📋",
    ".md": "📝",
    ".txt": "📄",
    ".html": "🌐",
    ".css": "🎨",
    ".sh": "⚡",
    ".sql": "🗄",
    ".toml": "⚙",
    ".env": "🔒",
}


def get_file_icon(filename: str) -> str:
    """Get an icon for a file based on its extension."""
    import os
    _, ext = os.path.splitext(filename)
    return FILE_ICONS.get(ext.lower(), Icons.FILE)
