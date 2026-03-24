"""Tests for TabSyncService."""

from datetime import datetime

import pytest

from src.cli.v3.tui.services.tab_sync import (
    SyncEvent,
    SyncEventType,
    TabSyncService,
    get_tab_sync_service,
)


class TestSyncEvent:
    """Test SyncEvent dataclass."""

    def test_creation(self):
        """Test SyncEvent can be created with required and optional fields."""
        # Test with minimal fields
        event = SyncEvent(event_type=SyncEventType.REGION_SELECTED, source="dashboard")
        assert event.event_type == SyncEventType.REGION_SELECTED
        assert event.source == "dashboard"
        assert event.data == {}
        assert isinstance(event.timestamp, datetime)

        # Test with all fields
        custom_time = datetime.now()
        event_with_data = SyncEvent(
            event_type=SyncEventType.ANALYSIS_COMPLETE,
            source="region_screen",
            data={"region": "us-east-1", "status": "success"},
            timestamp=custom_time,
        )
        assert event_with_data.event_type == SyncEventType.ANALYSIS_COMPLETE
        assert event_with_data.source == "region_screen"
        assert event_with_data.data == {"region": "us-east-1", "status": "success"}
        assert event_with_data.timestamp == custom_time


class TestTabSyncService:
    """Test TabSyncService."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before and after each test."""
        TabSyncService.reset()
        yield
        TabSyncService.reset()

    def test_subscribe_adds_callback(self):
        """Test that subscribe adds a callback for an event type."""
        service = TabSyncService()
        callback_called = []

        def callback(event: SyncEvent):
            callback_called.append(event)

        service.subscribe(SyncEventType.REGION_SELECTED, callback)

        # Emit event to verify callback was added
        event = SyncEvent(event_type=SyncEventType.REGION_SELECTED, source="test")
        service.emit(event)

        assert len(callback_called) == 1
        assert callback_called[0] == event

    def test_unsubscribe_removes_callback(self):
        """Test that unsubscribe removes a callback."""
        service = TabSyncService()
        callback_called = []

        def callback(event: SyncEvent):
            callback_called.append(event)

        # Subscribe then unsubscribe
        service.subscribe(SyncEventType.REGION_SELECTED, callback)
        service.unsubscribe(SyncEventType.REGION_SELECTED, callback)

        # Emit event - callback should not be called
        event = SyncEvent(event_type=SyncEventType.REGION_SELECTED, source="test")
        service.emit(event)

        assert len(callback_called) == 0

    def test_emit_calls_subscribers(self):
        """Test that emit calls all subscribers for an event type."""
        service = TabSyncService()
        callback1_calls = []
        callback2_calls = []

        def callback1(event: SyncEvent):
            callback1_calls.append(event)

        def callback2(event: SyncEvent):
            callback2_calls.append(event)

        service.subscribe(SyncEventType.ANALYSIS_STARTED, callback1)
        service.subscribe(SyncEventType.ANALYSIS_STARTED, callback2)

        event = SyncEvent(event_type=SyncEventType.ANALYSIS_STARTED, source="test")
        service.emit(event)

        assert len(callback1_calls) == 1
        assert len(callback2_calls) == 1
        assert callback1_calls[0] == event
        assert callback2_calls[0] == event

    def test_emit_does_not_call_other_subscribers(self):
        """Test that emit only calls subscribers for the specific event type."""
        service = TabSyncService()
        region_callback_calls = []
        analysis_callback_calls = []

        def region_callback(event: SyncEvent):
            region_callback_calls.append(event)

        def analysis_callback(event: SyncEvent):
            analysis_callback_calls.append(event)

        service.subscribe(SyncEventType.REGION_SELECTED, region_callback)
        service.subscribe(SyncEventType.ANALYSIS_STARTED, analysis_callback)

        # Emit REGION_SELECTED event
        event = SyncEvent(event_type=SyncEventType.REGION_SELECTED, source="test")
        service.emit(event)

        # Only region_callback should be called
        assert len(region_callback_calls) == 1
        assert len(analysis_callback_calls) == 0

    def test_get_state_returns_none_initially(self):
        """Test that get_state returns None for unset keys."""
        service = TabSyncService()
        assert service.get_state("nonexistent") is None
        assert service.get_state("nonexistent", "default") == "default"

    def test_set_and_get_state(self):
        """Test setting and getting state."""
        service = TabSyncService()

        service.set_state("selected_region", "us-west-2")
        assert service.get_state("selected_region") == "us-west-2"

        service.set_state("theme", "dark")
        assert service.get_state("theme") == "dark"
        assert service.get_state("selected_region") == "us-west-2"

    def test_clear_state(self):
        """Test clearing all state."""
        service = TabSyncService()

        service.set_state("key1", "value1")
        service.set_state("key2", "value2")

        service.clear_state()

        assert service.get_state("key1") is None
        assert service.get_state("key2") is None

    def test_get_recent_events(self):
        """Test getting recent events."""
        service = TabSyncService()

        event1 = SyncEvent(event_type=SyncEventType.REGION_SELECTED, source="test1")
        event2 = SyncEvent(event_type=SyncEventType.ANALYSIS_STARTED, source="test2")
        event3 = SyncEvent(event_type=SyncEventType.REGION_SELECTED, source="test3")

        service.emit(event1)
        service.emit(event2)
        service.emit(event3)

        # Get all recent events
        recent = service.get_recent_events(limit=10)
        assert len(recent) == 3
        assert recent[0] == event3  # Most recent first
        assert recent[1] == event2
        assert recent[2] == event1

        # Get filtered by event type
        region_events = service.get_recent_events(
            event_type=SyncEventType.REGION_SELECTED, limit=10
        )
        assert len(region_events) == 2
        assert region_events[0] == event3
        assert region_events[1] == event1

        # Test limit
        limited = service.get_recent_events(limit=2)
        assert len(limited) == 2
        assert limited[0] == event3
        assert limited[1] == event2

    def test_event_history_max_size(self):
        """Test that event history is limited to 100 events."""
        service = TabSyncService()

        # Emit 150 events
        for i in range(150):
            event = SyncEvent(event_type=SyncEventType.REGION_SELECTED, source=f"test{i}")
            service.emit(event)

        # Should only keep last 100
        recent = service.get_recent_events(limit=200)
        assert len(recent) == 100
        # Most recent should be test149
        assert recent[0].source == "test149"
        # Oldest should be test50
        assert recent[-1].source == "test50"

    def test_get_tab_sync_service_returns_singleton(self):
        """Test that get_tab_sync_service returns the same instance."""
        service1 = get_tab_sync_service()
        service2 = get_tab_sync_service()
        assert service1 is service2

        # Test state is shared
        service1.set_state("test", "value")
        assert service2.get_state("test") == "value"

    def test_reset_clears_singleton(self):
        """Test that reset() clears the singleton instance."""
        service1 = TabSyncService()
        service1.set_state("test", "value")

        TabSyncService.reset()

        service2 = TabSyncService()
        assert service2.get_state("test") is None
