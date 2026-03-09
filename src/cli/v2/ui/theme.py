"""Tawiza CLI v2 Design System - Minimal theme with subtle accents."""


# Core color palette
THEME: dict[str, str] = {
    "bg": "default",
    "text": "white",
    "dim": "bright_black",
    "accent": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "highlight": "magenta",
}

# Semantic aliases
COLOR_OK = THEME["success"]
COLOR_WARN = THEME["warning"]
COLOR_ERR = THEME["error"]
COLOR_INFO = THEME["accent"]

# Status indicators
STATUS = {
    "ok": "●",
    "warn": "●",
    "err": "●",
    "pending": "○",
}


def header(title: str, width: int = 40) -> str:
    """Create a minimal header line."""
    padding = width - len(title) - 5
    return f"─── {title} " + "─" * max(padding, 3)


def footer(width: int = 40) -> str:
    """Create a minimal footer line."""
    return "─" * width


def center_text(text: str, width: int = 50) -> str:
    """Center text within given width."""
    return text.center(width)
