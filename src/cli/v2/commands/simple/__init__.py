"""Simple commands for Tawiza CLI v2 (5 core commands)."""

from .chat import chat_command
from .run import run_command
from .status import status_command
from .tajine import tajine_command

__all__ = ["status_command", "chat_command", "run_command", "tajine_command"]
