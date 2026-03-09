"""Messaging and event handling module.

Provides an event bus for domain event publishing and subscription.
"""

from src.infrastructure.messaging.event_bus import (
    EventBus,
    EventHandler,
)

__all__ = [
    "EventBus",
    "EventHandler",
]
