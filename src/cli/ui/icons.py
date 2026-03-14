"""
Icon System - Contextual icons for CLI

Provides consistent iconography across the CLI interface.
Icons are mapped to specific contexts and commands for visual coherence.
"""

from dataclasses import dataclass
from enum import Enum


class IconSet(Enum):
    """Available icon sets"""

    NERD_FONTS = "nerd_fonts"  # Nerd Fonts (requires compatible terminal)
    EMOJI = "emoji"  # Unicode emoji
    ASCII = "ascii"  # ASCII fallback


@dataclass
class Icon:
    """Icon representation with multiple set support"""

    nerd: str  # Nerd Fonts icon
    emoji: str  # Emoji icon
    ascii: str  # ASCII fallback


class Icons:
    """
    Centralized icon library for Tawiza CLI

    Organized by context for consistent UX
    """

    # ========================================================================
    # SYSTEM & STATUS
    # ========================================================================

    # System operations
    SYSTEM = Icon(nerd="", emoji="💻", ascii="[SYS]")
    CPU = Icon(nerd="", emoji="🔥", ascii="[CPU]")
    MEMORY = Icon(nerd="", emoji="🧠", ascii="[MEM]")
    DISK = Icon(nerd="", emoji="💾", ascii="[DSK]")
    GPU = Icon(nerd="", emoji="🎮", ascii="[GPU]")
    NETWORK = Icon(nerd="", emoji="🌐", ascii="[NET]")

    # Status indicators
    SUCCESS = Icon(nerd="", emoji="✅", ascii="[OK]")
    ERROR = Icon(nerd="", emoji="❌", ascii="[ERR]")
    WARNING = Icon(nerd="", emoji="⚠️", ascii="[WARN]")
    INFO = Icon(nerd="", emoji="ℹ️", ascii="[INFO]")
    PENDING = Icon(nerd="", emoji="⏳", ascii="[...]")
    RUNNING = Icon(nerd="", emoji="⚡", ascii="[RUN]")

    # Health status
    HEALTHY = Icon(nerd="", emoji="💚", ascii="[+]")
    UNHEALTHY = Icon(nerd="", emoji="❤️", ascii="[-]")
    DEGRADED = Icon(nerd="", emoji="💛", ascii="[~]")

    # ========================================================================
    # MACHINE LEARNING
    # ========================================================================

    # Models
    MODEL = Icon(nerd="", emoji="🤖", ascii="[MDL]")
    BRAIN = Icon(nerd="󰛙", emoji="🧠", ascii="[AI]")
    NEURAL_NETWORK = Icon(nerd="", emoji="🕸️", ascii="[NN]")
    TRAINING = Icon(nerd="", emoji="🏋️", ascii="[TRN]")
    INFERENCE = Icon(nerd="", emoji="🔮", ascii="[INF]")

    # Data
    DATASET = Icon(nerd="", emoji="📊", ascii="[DATA]")
    DATABASE = Icon(nerd="", emoji="🗄️", ascii="[DB]")
    FILE = Icon(nerd="", emoji="📄", ascii="[FILE]")
    FOLDER = Icon(nerd="", emoji="📁", ascii="[DIR]")

    # ML Operations
    EXPERIMENT = Icon(nerd="", emoji="🧪", ascii="[EXP]")
    METRICS = Icon(nerd="", emoji="📈", ascii="[MET]")
    ACCURACY = Icon(nerd="", emoji="🎯", ascii="[ACC]")
    LOSS = Icon(nerd="", emoji="📉", ascii="[LOSS]")

    # ========================================================================
    # AUTOMATION & BROWSER
    # ========================================================================

    # Browser automation
    BROWSER = Icon(nerd="", emoji="🌐", ascii="[WWW]")
    CLICK = Icon(nerd="", emoji="👆", ascii="[CLK]")
    FORM = Icon(nerd="", emoji="📝", ascii="[FORM]")
    SCREENSHOT = Icon(nerd="", emoji="📸", ascii="[SCR]")
    ROBOT = Icon(nerd="󰚩", emoji="🤖", ascii="[BOT]")

    # Task automation
    TASK = Icon(nerd="", emoji="📋", ascii="[TSK]")
    WORKFLOW = Icon(nerd="", emoji="⚙️", ascii="[WRK]")
    SCHEDULE = Icon(nerd="", emoji="📅", ascii="[SCH]")
    AUTOMATION = Icon(nerd="", emoji="⚡", ascii="[AUTO]")

    # ========================================================================
    # PROMPTS & TEMPLATES
    # ========================================================================

    # Prompt management
    PROMPT = Icon(nerd="", emoji="💬", ascii="[PRM]")
    TEMPLATE = Icon(nerd="", emoji="📋", ascii="[TPL]")
    VARIABLE = Icon(nerd="", emoji="🔤", ascii="[VAR]")
    CHAT = Icon(nerd="󰭹", emoji="💭", ascii="[CHT]")

    # Prompt types
    CLASSIFICATION = Icon(nerd="", emoji="🏷️", ascii="[CLS]")
    SUMMARIZATION = Icon(nerd="", emoji="📝", ascii="[SUM]")
    GENERATION = Icon(nerd="", emoji="✨", ascii="[GEN]")
    TRANSLATION = Icon(nerd="", emoji="🌍", ascii="[TRL]")

    # ========================================================================
    # STORAGE & VERSIONING
    # ========================================================================

    # Storage
    STORAGE = Icon(nerd="", emoji="💾", ascii="[STR]")
    CLOUD = Icon(nerd="", emoji="☁️", ascii="[CLD]")
    BACKUP = Icon(nerd="", emoji="💿", ascii="[BCK]")
    ARCHIVE = Icon(nerd="", emoji="🗜️", ascii="[ARC]")

    # Versioning
    VERSION = Icon(nerd="", emoji="🏷️", ascii="[VER]")
    GIT = Icon(nerd="", emoji="🌿", ascii="[GIT]")
    BRANCH = Icon(nerd="", emoji="🌿", ascii="[BR]")
    TAG = Icon(nerd="", emoji="🏷️", ascii="[TAG]")

    # ========================================================================
    # ANNOTATION & LABELING
    # ========================================================================

    # Annotation
    ANNOTATION = Icon(nerd="", emoji="🏷️", ascii="[ANN]")
    LABEL = Icon(nerd="", emoji="🔖", ascii="[LBL]")
    PROJECT = Icon(nerd="", emoji="📁", ascii="[PRJ]")
    REVIEW = Icon(nerd="", emoji="👁️", ascii="[REV]")

    # ========================================================================
    # SECURITY & CREDENTIALS
    # ========================================================================

    # Security
    SECURITY = Icon(nerd="", emoji="🔒", ascii="[SEC]")
    KEY = Icon(nerd="", emoji="🔑", ascii="[KEY]")
    CERTIFICATE = Icon(nerd="", emoji="📜", ascii="[CERT]")
    SHIELD = Icon(nerd="", emoji="🛡️", ascii="[SHLD]")

    # Credentials
    CREDENTIAL = Icon(nerd="", emoji="🔐", ascii="[CRED]")
    PASSWORD = Icon(nerd="", emoji="🔑", ascii="[PASS]")
    TOKEN = Icon(nerd="", emoji="🎫", ascii="[TKN]")

    # ========================================================================
    # OPERATIONS & ACTIONS
    # ========================================================================

    # Actions
    START = Icon(nerd="", emoji="▶️", ascii="[>]")
    STOP = Icon(nerd="", emoji="⏹️", ascii="[#]")
    PAUSE = Icon(nerd="", emoji="⏸️", ascii="[||]")
    RESTART = Icon(nerd="", emoji="🔄", ascii="[@]")
    DELETE = Icon(nerd="", emoji="🗑️", ascii="[X]")

    # Operations
    UPLOAD = Icon(nerd="", emoji="📤", ascii="[UP]")
    DOWNLOAD = Icon(nerd="", emoji="📥", ascii="[DN]")
    SYNC = Icon(nerd="", emoji="🔄", ascii="[SYN]")
    SEARCH = Icon(nerd="", emoji="🔍", ascii="[?]")
    FILTER = Icon(nerd="", emoji="🔽", ascii="[FLT]")

    # ========================================================================
    # UI ELEMENTS
    # ========================================================================

    # Navigation
    ARROW_RIGHT = Icon(nerd="", emoji="→", ascii="->")
    ARROW_LEFT = Icon(nerd="", emoji="←", ascii="<-")
    ARROW_UP = Icon(nerd="", emoji="↑", ascii="^")
    ARROW_DOWN = Icon(nerd="", emoji="↓", ascii="v")

    # Indicators
    BULLET = Icon(nerd="●", emoji="•", ascii="*")
    CHECKBOX = Icon(nerd="", emoji="☑️", ascii="[x]")
    RADIO = Icon(nerd="", emoji="⚪", ascii="()")
    STAR = Icon(nerd="", emoji="⭐", ascii="*")

    # Decorative
    SPARKLES = Icon(nerd="", emoji="✨", ascii="**")
    FIRE = Icon(nerd="", emoji="🔥", ascii="^")
    ROCKET = Icon(nerd="", emoji="🚀", ascii="==>")
    ZAP = Icon(nerd="", emoji="⚡", ascii="/!")


class IconManager:
    """
    Icon manager for consistent icon rendering

    Handles icon set selection and rendering
    """

    def __init__(self, icon_set: IconSet = IconSet.EMOJI):
        """
        Initialize icon manager

        Args:
            icon_set: Icon set to use
        """
        self.icon_set = icon_set

    def get(self, icon: Icon) -> str:
        """
        Get icon string for current icon set

        Args:
            icon: Icon to render

        Returns:
            Icon string
        """
        if self.icon_set == IconSet.NERD_FONTS:
            return icon.nerd
        elif self.icon_set == IconSet.EMOJI:
            return icon.emoji
        elif self.icon_set == IconSet.ASCII:
            return icon.ascii
        return icon.emoji  # Default fallback

    def format(self, icon: Icon, text: str, *, spacing: int = 1) -> str:
        """
        Format icon with text

        Args:
            icon: Icon to use
            text: Text to append
            spacing: Number of spaces between icon and text

        Returns:
            Formatted string
        """
        icon_str = self.get(icon)
        space = " " * spacing
        return f"{icon_str}{space}{text}"


class CommandIcons:
    """
    Icon mappings for CLI commands

    Provides consistent iconography for each command group
    """

    # Command group icons
    COMMAND_ICONS: dict[str, Icon] = {
        # Main commands
        "version": Icons.VERSION,
        "system": Icons.SYSTEM,
        "models": Icons.MODEL,
        "train": Icons.TRAINING,
        "data": Icons.DATASET,
        "browser": Icons.BROWSER,
        "live": Icons.ROBOT,
        "chat": Icons.CHAT,
        "automate": Icons.AUTOMATION,
        "credentials": Icons.CREDENTIAL,
        "captcha": Icons.SHIELD,
        "finetune": Icons.TRAINING,
        "annotate": Icons.ANNOTATION,
        "prompts": Icons.PROMPT,
        # System subcommands
        "health": Icons.HEALTHY,
        "status": Icons.INFO,
        "gpu": Icons.GPU,
        "services": Icons.WORKFLOW,
        # Model operations
        "list": Icons.FOLDER,
        "show": Icons.INFO,
        "delete": Icons.DELETE,
        # Training operations
        "start": Icons.START,
        "stop": Icons.STOP,
        "logs": Icons.FILE,
        # Browser operations
        "navigate": Icons.BROWSER,
        "click": Icons.CLICK,
        "screenshot": Icons.SCREENSHOT,
        # Status indicators
        "success": Icons.SUCCESS,
        "error": Icons.ERROR,
        "warning": Icons.WARNING,
        "pending": Icons.PENDING,
        "running": Icons.RUNNING,
    }

    @classmethod
    def get_command_icon(cls, command: str) -> Icon | None:
        """
        Get icon for command

        Args:
            command: Command name

        Returns:
            Icon if found, None otherwise
        """
        return cls.COMMAND_ICONS.get(command.lower())


# Singleton icon manager
_icon_manager: IconManager | None = None


def get_icon_manager(icon_set: IconSet | None = None) -> IconManager:
    """
    Get global icon manager instance

    Args:
        icon_set: Icon set to use (creates new manager if different)

    Returns:
        IconManager instance
    """
    global _icon_manager

    if _icon_manager is None or (icon_set and _icon_manager.icon_set != icon_set):
        _icon_manager = IconManager(icon_set or IconSet.EMOJI)

    return _icon_manager


def icon(icon_obj: Icon, text: str = "", *, spacing: int = 1) -> str:
    """
    Convenience function to format icon with text

    Args:
        icon_obj: Icon to use
        text: Text to append
        spacing: Spacing between icon and text

    Returns:
        Formatted string

    Examples:
        >>> icon(Icons.SUCCESS, "Operation completed")
        "✅ Operation completed"

        >>> icon(Icons.MODEL)
        "🤖"
    """
    manager = get_icon_manager()

    if text:
        return manager.format(icon_obj, text, spacing=spacing)
    return manager.get(icon_obj)


# Convenience functions for common patterns
def status_icon(status: str) -> str:
    """Get icon for status"""
    status_map = {
        "success": Icons.SUCCESS,
        "error": Icons.ERROR,
        "warning": Icons.WARNING,
        "info": Icons.INFO,
        "pending": Icons.PENDING,
        "running": Icons.RUNNING,
        "healthy": Icons.HEALTHY,
        "unhealthy": Icons.UNHEALTHY,
        "degraded": Icons.DEGRADED,
    }
    icon_obj = status_map.get(status.lower(), Icons.INFO)
    return icon(icon_obj)


def command_icon(command: str, text: str = "") -> str:
    """Get icon for command"""
    icon_obj = CommandIcons.get_command_icon(command) or Icons.INFO
    return icon(icon_obj, text)
