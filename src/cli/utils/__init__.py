"""Tawiza CLI utilities (legacy v1 - retained subset).

Only `async_runner` remains; the other v1 utility modules were removed alongside
the v1 entrypoint.
"""

from .async_runner import run_async

__all__ = ["run_async"]
