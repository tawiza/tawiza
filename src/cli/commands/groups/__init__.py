"""Command groups for Tawiza CLI."""

from .ai import app as ai_app
from .automation import app as automation_app
from .data import app as data_app
from .infra import app as infra_app

__all__ = ["ai_app", "data_app", "automation_app", "infra_app"]
