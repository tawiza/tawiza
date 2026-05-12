"""Tawiza CLI commands (legacy v1 - retained subset).

Only `unified_agent` remains from the v1 CLI. The v1 entrypoint and its other
commands were removed; the production CLI lives under `src.cli.v2`.
"""

from . import unified_agent

__all__ = ["unified_agent"]
