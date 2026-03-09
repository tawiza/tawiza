"""Tawiza anonymous telemetry — opt-out via TELEMETRY_ENABLED=false.

See TELEMETRY.md at the root of the repository for full details on what
is collected, what is NOT collected, and how to opt out.
"""

import hashlib
import os
import platform
import uuid
from functools import lru_cache
from pathlib import Path

from loguru import logger

TELEMETRY_ENABLED = os.getenv("TELEMETRY_ENABLED", "true").lower() in ("true", "1", "yes")

# PostHog project key — points to the Tawiza team's analytics dashboard.
# This is a write-only key (cannot read data). Users can opt out entirely
# by setting TELEMETRY_ENABLED=false.
POSTHOG_API_KEY = "phc_PIhsounBxTTOTt7xYTitoorK6pXfmXHGaKZfLQsSvIo"
POSTHOG_HOST = "https://eu.i.posthog.com"

_posthog_client = None


@lru_cache(maxsize=1)
def _get_anonymous_id() -> str:
    """Generate a stable anonymous ID per installation (no PII)."""
    marker = Path.home() / ".tawiza" / ".telemetry_id"
    try:
        if marker.exists():
            return marker.read_text().strip()
        marker.parent.mkdir(parents=True, exist_ok=True)
        anon_id = hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16]
        marker.write_text(anon_id)
        return anon_id
    except Exception:
        return "anonymous"


def _get_client():
    """Lazy-init PostHog client."""
    global _posthog_client
    if _posthog_client is not None:
        return _posthog_client
    if not TELEMETRY_ENABLED or not POSTHOG_API_KEY:
        return None
    try:
        from posthog import Posthog

        _posthog_client = Posthog(
            api_key=POSTHOG_API_KEY,
            host=POSTHOG_HOST,
            debug=False,
            on_error=lambda e, items: None,  # fail silently
        )
        _posthog_client.disabled = not TELEMETRY_ENABLED
        return _posthog_client
    except ImportError:
        logger.debug("posthog package not installed, telemetry disabled")
        return None
    except Exception:
        return None


def capture(event: str, properties: dict | None = None):
    """Capture an anonymous telemetry event. Fails silently."""
    if not TELEMETRY_ENABLED:
        return
    client = _get_client()
    if client is None:
        return
    try:
        base_props = {
            "tawiza_version": os.getenv("APP_VERSION", "unknown"),
            "python_version": platform.python_version(),
            "os": platform.system(),
            "arch": platform.machine(),
        }
        if properties:
            base_props.update(properties)
        client.capture(
            distinct_id=_get_anonymous_id(),
            event=event,
            properties=base_props,
        )
    except Exception:
        pass  # telemetry must never break the app


def capture_feature(feature: str, **kwargs):
    """Shortcut: capture a feature usage event."""
    capture(f"feature:{feature}", kwargs if kwargs else None)


def capture_agent(agent_name: str, level: str | None = None, duration_ms: int | None = None):
    """Capture an agent execution event."""
    props = {"agent": agent_name}
    if level:
        props["cognitive_level"] = level
    if duration_ms is not None:
        props["duration_ms"] = duration_ms
    capture("agent:execution", props)


def capture_datasource(source: str, success: bool = True, duration_ms: int | None = None):
    """Capture a data source API call."""
    props = {"source": source, "success": success}
    if duration_ms is not None:
        props["duration_ms"] = duration_ms
    capture("datasource:call", props)


def capture_startup():
    """Capture app startup with system info."""
    capture("app:startup", {
        "llm_provider": os.getenv("OLLAMA__BASE_URL", "none"),
        "db_type": "postgresql" if "postgresql" in os.getenv("DATABASE_URL", "") else "sqlite",
        "vectordb_enabled": os.getenv("VECTORDB__ENABLED", "false"),
    })


def shutdown():
    """Flush pending events on shutdown."""
    client = _get_client()
    if client:
        try:
            client.flush()
            client.shutdown()
        except Exception:
            pass
