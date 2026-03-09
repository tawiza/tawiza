"""Event Bus for Domain Events.

This module provides an in-memory event bus for publishing and subscribing
to domain events. For production, this could be replaced with RabbitMQ, Kafka, etc.
"""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from src.domain.events.base import DomainEvent

# Type alias for event handlers
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """In-memory Event Bus for Domain Events.

    Provides pub/sub functionality for domain events.
    Handlers are executed asynchronously and in parallel.
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Async function to handle the event

        Example:
            >>> async def handle_model_trained(event: ModelTrainedEvent):
            ...     print(f"Model {event.model_name} trained!")
            >>> event_bus.subscribe(ModelTrainedEvent, handle_model_trained)
        """
        self._handlers[event_type].append(handler)
        logger.info(
            f"Subscribed handler {handler.__name__} to {event_type.__name__}"
        )

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all events.

        Args:
            handler: Async function to handle any event

        Example:
            >>> async def log_all_events(event: DomainEvent):
            ...     logger.info(f"Event: {event.__class__.__name__}")
            >>> event_bus.subscribe_all(log_all_events)
        """
        self._global_handlers.append(handler)
        logger.info(f"Subscribed global handler {handler.__name__}")

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribers.

        Args:
            event: Domain event to publish

        Note:
            All handlers are executed in parallel using asyncio.gather
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        all_handlers = handlers + self._global_handlers

        if not all_handlers:
            logger.debug(f"No handlers for event {event_type.__name__}")
            return

        logger.info(
            f"Publishing {event_type.__name__} to {len(all_handlers)} handlers"
        )

        # Execute all handlers in parallel
        tasks = [self._safe_execute(handler, event) for handler in all_handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def publish_many(self, events: list[DomainEvent]) -> None:
        """Publish multiple events.

        Args:
            events: List of domain events to publish
        """
        if not events:
            return

        logger.info(f"Publishing {len(events)} events")
        tasks = [self.publish(event) for event in events]
        await asyncio.gather(*tasks)

    async def _safe_execute(
        self,
        handler: EventHandler,
        event: DomainEvent,
    ) -> None:
        """Execute a handler safely with error handling.

        Args:
            handler: Event handler function
            event: Domain event
        """
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"Error in handler {handler.__name__} "
                f"for event {type(event).__name__}: {e}",
                exc_info=True,
            )

    def clear_handlers(self, event_type: type[DomainEvent] | None = None) -> None:
        """Clear handlers for a specific event type or all handlers.

        Args:
            event_type: Event type to clear handlers for (None = clear all)
        """
        if event_type is None:
            self._handlers.clear()
            self._global_handlers.clear()
            logger.info("Cleared all event handlers")
        else:
            self._handlers.pop(event_type, None)
            logger.info(f"Cleared handlers for {event_type.__name__}")

    def get_handler_count(self, event_type: type[DomainEvent] | None = None) -> int:
        """Get the number of handlers registered.

        Args:
            event_type: Event type to count handlers for (None = all)

        Returns:
            Number of handlers
        """
        if event_type is None:
            total = len(self._global_handlers)
            total += sum(len(handlers) for handlers in self._handlers.values())
            return total
        return len(self._handlers.get(event_type, []))


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance.

    Returns:
        EventBus: Global event bus

    Example:
        >>> from src.infrastructure.messaging.event_bus import get_event_bus
        >>> event_bus = get_event_bus()
        >>> await event_bus.publish(event)
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def set_event_bus(event_bus: EventBus) -> None:
    """Set the global event bus instance.

    Args:
        event_bus: Event bus instance to use

    Note:
        Useful for testing with a mock event bus
    """
    global _event_bus
    _event_bus = event_bus


# Event handlers examples (to be moved to appropriate modules)

async def log_event_handler(event: DomainEvent) -> None:
    """Log all domain events (example handler).

    Args:
        event: Domain event
    """
    logger.info(
        f"Domain Event: {event.__class__.__name__} "
        f"(aggregate_id={event.aggregate_id})"
    )


async def publish_entity_events(entity: Any, event_bus: EventBus | None = None) -> None:
    """Publish all events from an aggregate root.

    Args:
        entity: Aggregate root entity with domain events
        event_bus: Event bus to use (uses global if not provided)

    Example:
        >>> model = MLModel(...)
        >>> model.deploy(...)  # This adds a domain event
        >>> await publish_entity_events(model)
    """
    if not hasattr(entity, "domain_events"):
        return

    bus = event_bus or get_event_bus()
    events = entity.domain_events

    if events:
        await bus.publish_many(events)
        entity.clear_domain_events()
