"""Autonomous agent CLI commands.

Provides commands for LLM-guided browser automation:
- tawiza agent run: Execute autonomous task
- tawiza agent plan: Generate and show execution plan
- tawiza agent status: Show execution status
- tawiza agent cancel: Cancel running task
- tawiza agent resume: Resume paused task
"""

from src.cli.commands.agent.commands import app

__all__ = ["app"]
