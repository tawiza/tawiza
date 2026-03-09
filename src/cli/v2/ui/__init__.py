"""UI components for Tawiza CLI v2."""

from .mascot import MASCOT, mascot_welcome
from .spinners import create_spinner, wave_spinner
from .theme import THEME, footer, header

__all__ = [
    "THEME",
    "header",
    "footer",
    "MASCOT",
    "mascot_welcome",
    "wave_spinner",
    "create_spinner",
]
