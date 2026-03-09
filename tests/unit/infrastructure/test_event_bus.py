"""Unit tests for Event Bus."""

from uuid import uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.ml_events import ModelTrainedEvent
from src.infrastructure.messaging.event_bus import EventBus


class TestEvent(DomainEvent):
    """Test domain event."""

    def __init__(self, aggregate_id, data: str):
        super().__init__(aggregate_id)
        object.__setattr__(self, "data", data)


class TestEventBus:
    """Test suite for Event Bus."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh event bus for each test."""
        return EventBus()

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, event_bus):
        """Test subscribing to and publishing events."""
        received_events = []

        async def handler(event: TestEvent):
            received_events.append(event)

        # Subscribe
        event_bus.subscribe(TestEvent, handler)

        # Publish
        event = TestEvent(aggregate_id=uuid4(), data="test data")
        await event_bus.publish(event)

        # Verify
        assert len(received_events) == 1
        assert received_events[0] == event
        assert received_events[0].data == "test data"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, event_bus):
        """Test multiple handlers for same event type."""
        handler1_called = []
        handler2_called = []

        async def handler1(event: TestEvent):
            handler1_called.append(event)

        async def handler2(event: TestEvent):
            handler2_called.append(event)

        # Subscribe both handlers
        event_bus.subscribe(TestEvent, handler1)
        event_bus.subscribe(TestEvent, handler2)

        # Publish
        event = TestEvent(aggregate_id=uuid4(), data="test")
        await event_bus.publish(event)

        # Both handlers should be called
        assert len(handler1_called) == 1
        assert len(handler2_called) == 1

    @pytest.mark.asyncio
    async def test_subscribe_all(self, event_bus):
        """Test subscribing to all events."""
        received_events = []

        async def global_handler(event: DomainEvent):
            received_events.append(event)

        # Subscribe to all events
        event_bus.subscribe_all(global_handler)

        # Publish different event types
        event1 = TestEvent(aggregate_id=uuid4(), data="test1")
        event2 = ModelTrainedEvent(
            model_id=uuid4(),
            model_name="test-model",
            version="1.0.0",
            accuracy=0.95,
        )

        await event_bus.publish(event1)
        await event_bus.publish(event2)

        # Global handler should receive both
        assert len(received_events) == 2
        assert isinstance(received_events[0], TestEvent)
        assert isinstance(received_events[1], ModelTrainedEvent)

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_stop_others(self, event_bus):
        """Test that one handler's error doesn't stop other handlers."""
        handler2_called = []

        async def failing_handler(event: TestEvent):
            raise Exception("Handler error!")

        async def working_handler(event: TestEvent):
            handler2_called.append(event)

        # Subscribe both
        event_bus.subscribe(TestEvent, failing_handler)
        event_bus.subscribe(TestEvent, working_handler)

        # Publish
        event = TestEvent(aggregate_id=uuid4(), data="test")
        await event_bus.publish(event)

        # Working handler should still be called
        assert len(handler2_called) == 1

    @pytest.mark.asyncio
    async def test_publish_many(self, event_bus):
        """Test publishing multiple events at once."""
        received_events = []

        async def handler(event: TestEvent):
            received_events.append(event)

        event_bus.subscribe(TestEvent, handler)

        # Publish multiple events
        events = [TestEvent(aggregate_id=uuid4(), data=f"test{i}") for i in range(5)]
        await event_bus.publish_many(events)

        # All should be received
        assert len(received_events) == 5

    def test_get_handler_count(self, event_bus):
        """Test getting handler count."""

        async def handler1(event: TestEvent):
            pass

        async def handler2(event: TestEvent):
            pass

        async def global_handler(event: DomainEvent):
            pass

        # Initially no handlers
        assert event_bus.get_handler_count() == 0
        assert event_bus.get_handler_count(TestEvent) == 0

        # Add handlers
        event_bus.subscribe(TestEvent, handler1)
        event_bus.subscribe(TestEvent, handler2)
        event_bus.subscribe_all(global_handler)

        # Check counts
        assert event_bus.get_handler_count(TestEvent) == 2
        assert event_bus.get_handler_count() == 3  # 2 specific + 1 global

    def test_clear_handlers(self, event_bus):
        """Test clearing handlers."""

        async def handler(event: TestEvent):
            pass

        event_bus.subscribe(TestEvent, handler)
        assert event_bus.get_handler_count(TestEvent) == 1

        # Clear specific event handlers
        event_bus.clear_handlers(TestEvent)
        assert event_bus.get_handler_count(TestEvent) == 0

        # Add again and clear all
        event_bus.subscribe(TestEvent, handler)
        event_bus.clear_handlers()
        assert event_bus.get_handler_count() == 0
