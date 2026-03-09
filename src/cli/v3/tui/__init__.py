"""Tawiza TUI v6 - Professional Terminal User Interface.

Exports are lazy to avoid heavy imports when just importing submodules.
"""

__all__ = ["TawizaApp", "run_tui"]


def __getattr__(name: str):
    """Lazy import to avoid loading the entire app on package import."""
    if name == "TawizaApp":
        from src.cli.v3.tui.app import TawizaApp
        return TawizaApp
    elif name == "run_tui":
        from src.cli.v3.tui.app import run_tui
        return run_tui
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
