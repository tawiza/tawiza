"""Tests for system state management.

This module tests:
- InitializationConfig immutable dataclass
- SystemState immutable dataclass with functional updates
- SystemStateManager singleton pattern
- Thread safety
- Convenience functions
"""

from datetime import datetime
from threading import Barrier, Thread
from unittest.mock import MagicMock, patch

import pytest

from src.core.system_state import (
    InitializationConfig,
    SystemState,
    SystemStateManager,
    get_current_state,
    get_system_state_manager,
    is_system_initialized,
    require_initialized,
)


class TestInitializationConfig:
    """Test suite for InitializationConfig dataclass."""

    def test_creation_with_required_fields(self):
        """Config should be created with required fields."""
        config = InitializationConfig(
            gpu_enabled=True,
            monitoring_enabled=False,
        )

        assert config.gpu_enabled is True
        assert config.monitoring_enabled is False

    def test_default_values(self):
        """Config should have sensible defaults."""
        config = InitializationConfig(
            gpu_enabled=False,
            monitoring_enabled=True,
        )

        assert config.max_concurrent_tasks == 5
        assert config.auto_scale is True
        assert config.retry_failed_tasks == 3
        assert config.verbose is False

    def test_custom_values(self):
        """Config should accept custom values."""
        config = InitializationConfig(
            gpu_enabled=True,
            monitoring_enabled=True,
            max_concurrent_tasks=10,
            auto_scale=False,
            retry_failed_tasks=5,
            verbose=True,
        )

        assert config.max_concurrent_tasks == 10
        assert config.auto_scale is False
        assert config.retry_failed_tasks == 5
        assert config.verbose is True

    def test_immutability(self):
        """Config should be immutable (frozen)."""
        config = InitializationConfig(
            gpu_enabled=True,
            monitoring_enabled=True,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            config.gpu_enabled = False


class TestSystemState:
    """Test suite for SystemState dataclass."""

    def test_creation_with_defaults(self):
        """State should be created with defaults."""
        state = SystemState()

        assert state.agents is None
        assert state.monitoring is None
        assert state.config is None
        assert state.initialized_at is None
        assert state.version == "2.0.3"
        assert state.active_tasks == 0
        assert state.completed_tasks == 0
        assert state.failed_tasks == 0

    def test_is_initialized_property(self):
        """is_initialized should check initialized_at."""
        state_uninit = SystemState()
        state_init = SystemState(initialized_at=datetime.utcnow())

        assert state_uninit.is_initialized is False
        assert state_init.is_initialized is True

    def test_has_gpu_property_no_config(self):
        """has_gpu should return False when no config."""
        state = SystemState()

        assert state.has_gpu is False

    def test_has_gpu_property_with_config(self):
        """has_gpu should check config.gpu_enabled."""
        config_gpu = InitializationConfig(gpu_enabled=True, monitoring_enabled=False)
        config_no_gpu = InitializationConfig(gpu_enabled=False, monitoring_enabled=False)

        state_gpu = SystemState(config=config_gpu)
        state_no_gpu = SystemState(config=config_no_gpu)

        assert state_gpu.has_gpu is True
        assert state_no_gpu.has_gpu is False

    def test_has_monitoring_property(self):
        """has_monitoring should check monitoring field."""
        state_no_mon = SystemState()
        state_mon = SystemState(monitoring=MagicMock())

        assert state_no_mon.has_monitoring is False
        assert state_mon.has_monitoring is True

    def test_with_updates_creates_new_state(self):
        """with_updates should create new state, not modify original."""
        original = SystemState(active_tasks=5)
        updated = original.with_updates(active_tasks=10)

        assert original.active_tasks == 5  # Original unchanged
        assert updated.active_tasks == 10  # New state updated
        assert original is not updated

    def test_with_updates_preserves_other_fields(self):
        """with_updates should preserve fields not being updated."""
        original = SystemState(
            active_tasks=5,
            completed_tasks=10,
            version="2.0.3",
        )
        updated = original.with_updates(active_tasks=6)

        assert updated.completed_tasks == 10
        assert updated.version == "2.0.3"

    def test_immutability(self):
        """State should be immutable (frozen)."""
        state = SystemState(active_tasks=5)

        with pytest.raises(Exception):  # FrozenInstanceError
            state.active_tasks = 10


class TestSystemStateManager:
    """Test suite for SystemStateManager singleton."""

    def setup_method(self):
        """Reset singleton state before each test."""
        # Clear the singleton's state (not the instance itself)
        manager = SystemStateManager()
        manager.clear_state()

    def test_singleton_pattern(self):
        """SystemStateManager should be a singleton."""
        manager1 = SystemStateManager()
        manager2 = SystemStateManager()

        assert manager1 is manager2

    def test_initial_state_is_none(self):
        """Initial state should be None."""
        manager = SystemStateManager()
        manager.clear_state()

        assert manager.state is None

    def test_update_state(self):
        """Should be able to update state."""
        manager = SystemStateManager()
        state = SystemState(initialized_at=datetime.utcnow())

        manager.update_state(state)

        assert manager.state is state

    def test_update_state_type_checking(self):
        """update_state should reject non-SystemState values."""
        manager = SystemStateManager()

        with pytest.raises(TypeError):
            manager.update_state("not a state")

        with pytest.raises(TypeError):
            manager.update_state({"key": "value"})

    def test_clear_state(self):
        """clear_state should set state to None."""
        manager = SystemStateManager()
        manager.update_state(SystemState(initialized_at=datetime.utcnow()))

        manager.clear_state()

        assert manager.state is None

    def test_is_initialized_method(self):
        """is_initialized should check if state exists and is initialized."""
        manager = SystemStateManager()
        manager.clear_state()

        assert manager.is_initialized() is False

        # Uninitialized state
        manager.update_state(SystemState())
        assert manager.is_initialized() is False

        # Initialized state
        manager.update_state(SystemState(initialized_at=datetime.utcnow()))
        assert manager.is_initialized() is True

    def test_get_state_or_raise_when_initialized(self):
        """get_state_or_raise should return state when initialized."""
        manager = SystemStateManager()
        state = SystemState(initialized_at=datetime.utcnow())
        manager.update_state(state)

        result = manager.get_state_or_raise()

        assert result is state

    def test_get_state_or_raise_when_not_initialized(self):
        """get_state_or_raise should raise when not initialized."""
        from src.core.exceptions import SystemNotInitializedError

        manager = SystemStateManager()
        manager.clear_state()

        with pytest.raises(SystemNotInitializedError):
            manager.get_state_or_raise()

    def test_increment_tasks(self):
        """increment_tasks should update task counters."""
        manager = SystemStateManager()
        manager.update_state(
            SystemState(
                initialized_at=datetime.utcnow(),
                active_tasks=5,
                completed_tasks=10,
                failed_tasks=2,
            )
        )

        manager.increment_tasks(active=2, completed=1, failed=1)

        assert manager.state.active_tasks == 7
        assert manager.state.completed_tasks == 11
        assert manager.state.failed_tasks == 3

    def test_increment_tasks_prevents_negative_active(self):
        """increment_tasks should not allow negative active tasks."""
        manager = SystemStateManager()
        manager.update_state(
            SystemState(
                initialized_at=datetime.utcnow(),
                active_tasks=2,
            )
        )

        manager.increment_tasks(active=-5)  # Would go to -3

        assert manager.state.active_tasks == 0  # Clamped to 0

    def test_get_history(self):
        """get_history should return previous states."""
        manager = SystemStateManager()
        manager.clear_state()

        state1 = SystemState(active_tasks=1)
        state2 = SystemState(active_tasks=2)
        state3 = SystemState(active_tasks=3)

        manager.update_state(state1)
        manager.update_state(state2)
        manager.update_state(state3)

        history = manager.get_history()

        assert len(history) >= 2
        assert history[-1].active_tasks == 2  # Previous state

    def test_history_max_size(self):
        """History should be limited to max size."""
        manager = SystemStateManager()
        manager.clear_state()

        # Add more than max_history states
        for i in range(15):
            manager.update_state(SystemState(active_tasks=i))

        history = manager.get_history()

        # Should be capped at 10
        assert len(history) <= 10

    def test_get_metrics_uninitialized(self):
        """get_metrics should work when not initialized."""
        manager = SystemStateManager()
        manager.clear_state()

        metrics = manager.get_metrics()

        assert metrics["initialized"] is False
        assert metrics["active_tasks"] == 0

    def test_get_metrics_initialized(self):
        """get_metrics should return full metrics when initialized."""
        manager = SystemStateManager()
        config = InitializationConfig(gpu_enabled=True, monitoring_enabled=True)
        manager.update_state(
            SystemState(
                config=config,
                initialized_at=datetime.utcnow(),
                active_tasks=5,
                completed_tasks=100,
                failed_tasks=2,
            )
        )

        metrics = manager.get_metrics()

        assert metrics["initialized"] is True
        assert metrics["gpu_enabled"] is True
        assert metrics["monitoring_enabled"] is False  # monitoring field is None
        assert metrics["active_tasks"] == 5
        assert metrics["completed_tasks"] == 100
        assert metrics["failed_tasks"] == 2
        assert "initialized_at" in metrics
        assert metrics["version"] == "2.0.3"

    def test_repr(self):
        """__repr__ should return useful string."""
        manager = SystemStateManager()
        manager.clear_state()

        assert "None" in repr(manager)

        manager.update_state(SystemState(initialized_at=datetime.utcnow()))
        assert "initialized=True" in repr(manager)


class TestSystemStateManagerThreadSafety:
    """Test suite for thread safety of SystemStateManager."""

    def setup_method(self):
        """Reset singleton state before each test."""
        manager = SystemStateManager()
        manager.clear_state()
        manager.update_state(
            SystemState(
                initialized_at=datetime.utcnow(),
                active_tasks=0,
                completed_tasks=0,
            )
        )

    def test_concurrent_reads(self):
        """Multiple threads should be able to read state concurrently."""
        manager = SystemStateManager()
        results = []

        def read_state():
            for _ in range(100):
                state = manager.state
                if state:
                    results.append(state.is_initialized)

        threads = [Thread(target=read_state) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should succeed
        assert len(results) == 1000
        assert all(r is True for r in results)

    def test_concurrent_increments(self):
        """Concurrent increment_tasks should be atomic."""
        manager = SystemStateManager()
        num_threads = 10
        increments_per_thread = 100

        def increment_tasks():
            for _ in range(increments_per_thread):
                manager.increment_tasks(completed=1)

        threads = [Thread(target=increment_tasks) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All increments should be counted
        assert manager.state.completed_tasks == num_threads * increments_per_thread


class TestConvenienceFunctions:
    """Test suite for module-level convenience functions."""

    def setup_method(self):
        """Reset singleton state before each test."""
        manager = SystemStateManager()
        manager.clear_state()

    def test_get_system_state_manager(self):
        """get_system_state_manager should return singleton."""
        manager1 = get_system_state_manager()
        manager2 = get_system_state_manager()

        assert manager1 is manager2
        assert isinstance(manager1, SystemStateManager)

    def test_get_current_state(self):
        """get_current_state should return current state."""
        manager = get_system_state_manager()
        manager.clear_state()

        assert get_current_state() is None

        state = SystemState(initialized_at=datetime.utcnow())
        manager.update_state(state)

        assert get_current_state() is state

    def test_is_system_initialized(self):
        """is_system_initialized should check initialization status."""
        manager = get_system_state_manager()
        manager.clear_state()

        assert is_system_initialized() is False

        manager.update_state(SystemState(initialized_at=datetime.utcnow()))

        assert is_system_initialized() is True

    def test_require_initialized_success(self):
        """require_initialized should return state when initialized."""
        manager = get_system_state_manager()
        state = SystemState(initialized_at=datetime.utcnow())
        manager.update_state(state)

        result = require_initialized()

        assert result is state

    def test_require_initialized_failure(self):
        """require_initialized should raise when not initialized."""
        from src.core.exceptions import SystemNotInitializedError

        manager = get_system_state_manager()
        manager.clear_state()

        with pytest.raises(SystemNotInitializedError):
            require_initialized()
