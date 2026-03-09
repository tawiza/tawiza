"""Intelligent autocompletion system."""

from src.cli.v3.completion.base import CompletionProvider, CompletionResult
from src.cli.v3.completion.registry import complete, get_completer, register_completer

__all__ = [
    "CompletionProvider",
    "CompletionResult",
    "complete",
    "get_completer",
    "register_completer",
]
