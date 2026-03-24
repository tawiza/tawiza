"""Unified output formatting system.

Provides automatic format detection and multiple output formatters.
"""

from src.cli.v3.output.base import OutputFormat, OutputFormatter
from src.cli.v3.output.renderer import output, render

__all__ = [
    "OutputFormat",
    "OutputFormatter",
    "output",
    "render",
]
