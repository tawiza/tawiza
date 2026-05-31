"""Unit tests for system state management (issue #161, batch 3 coverage).

Target module: ``src.core.system_state``.

Covers:
- ``InitializationConfig`` immutable (frozen) dataclass: construction,
  defaults, custom values, immutability.
- ``SystemState`` immutable (frozen) dataclass: construction, derived
  properties (``is_initialized`` / ``has_gpu`` / ``has_monitoring``),
  functional ``with_updates`` and immutability.
- ``SystemStateManager`` thread-safe singleton: double-checked-locking
  ``__new__`` returns the same instance, state transitions, type checks,
  history management and trimming, metrics, increments (with clamping),
  ``get_state_or_raise`` and ``__repr__``.
- Thread safety of reads and increments.
- Module-level convenience functions.

The production code is the source of truth. ``SystemStateManager`` is a
process-wide singleton, so each test runs against a *freshly reset* instance
(``_instance`` is set back to ``None`` by an autouse fixture) to guarantee
isolation -- otherwise ``_state`` and ``_history`` would leak between tests.
"""

from datetime import datetime, timezone
from threading import Thread
from unittest.mock import MagicMock

import pytest

from src.core.exceptions import SystemNotInitializedError
from src.core.system_state import (
    InitializationConfig,
    SystemState,
    SystemStateManager,
    get_current_state,
    get_system_state_manager,
    is_system_initialized,
    require_initialized,
)


def _now() -> datetime:
    """Timezone-aware UTC timestamp (avoids utcnow() deprecation noise)."""
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the SystemStateManager singleton before and after each test.

    The manager has no public reset hook, so we clear the class-level
    ``_instance`` directly. This forces ``__new__`` to rebuild a pristine
    instance (fresh ``_state`` and ``_history``) for every test, isolating
    them from one another.
    """
    SystemStateManager._instance = None
    yield
    SystemStateManager._instance = None


# ---------------------------------------------------------------------------
# InitializationConfig
# ---------------------------------------------------------------------------
class TestInitializationConfig:
    """Test suite for the InitializationConfig frozen dataclass."""

    def test_creation_with_required_fields(self):
        config = InitializationConfig(gpu_enabled=True, monitoring_enabled=False)

        assert config.gpu_enabled is True
        assert config.monitoring_enabled is False

    def test_default_values(self):
        config = InitializationConfig(gpu_enabled=False, monitoring_enabled=True)

        assert config.max_concurrent_tasks == 5
        assert config.auto_scale is True
        assert config.retry_failed_tasks == 3
        assert config.verbose is False

    def test_custom_values(self):
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
        config = InitializationConfig(gpu_enabled=True, monitoring_enabled=True)

        with pytest.raises(AttributeError):
            config.gpu_enabled = False

    def test_equality(self):
        a = InitializationConfig(gpu_enabled=True, monitoring_enabled=True)
        b = InitializationConfig(gpu_enabled=True, monitoring_enabled=True)
        c = InitializationConfig(gpu_enabled=False, monitoring_enabled=True)

        assert a == b
        assert a != c

    def test_is_hashable(self):
        # Frozen dataclasses are hashable, so they can live in sets / dict keys.
        a = InitializationConfig(gpu_enabled=True, monitoring_enabled=True)
        b = InitializationConfig(gpu_enabled=True, monitoring_enabled=True)

        assert hash(a) == hash(b)
        assert len({a, b}) == 1


# ---------------------------------------------------------------------------
# SystemState
# ---------------------------------------------------------------------------
class TestSystemState:
    """Test suite for the SystemState frozen dataclass."""

    def test_creation_with_defaults(self):
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
        assert SystemState().is_initialized is False
        assert SystemState(initialized_at=_now()).is_initialized is True

    def test_has_gpu_property_no_config(self):
        assert SystemState().has_gpu is False

    def test_has_gpu_property_with_config(self):
        config_gpu = InitializationConfig(gpu_enabled=True, monitoring_enabled=False)
        config_no_gpu = InitializationConfig(gpu_enabled=False, monitoring_enabled=False)

        assert SystemState(config=config_gpu).has_gpu is True
        assert SystemState(config=config_no_gpu).has_gpu is False

    def test_has_monitoring_property(self):
        assert SystemState().has_monitoring is False
        assert SystemState(monitoring=MagicMock()).has_monitoring is True

    def test_with_updates_creates_new_state(self):
        original = SystemState(active_tasks=5)
        updated = original.with_updates(active_tasks=10)

        assert original.active_tasks == 5  # original untouched
        assert updated.active_tasks == 10
        assert original is not updated

    def test_with_updates_preserves_other_fields(self):
        original = SystemState(active_tasks=5, completed_tasks=10, version="2.0.3")
        updated = original.with_updates(active_tasks=6)

        assert updated.active_tasks == 6
        assert updated.completed_tasks == 10
        assert updated.version == "2.0.3"

    def test_with_updates_no_args_returns_equal_copy(self):
        original = SystemState(active_tasks=3)
        copy = original.with_updates()

        assert copy == original
        assert copy is not original

    def test_immutability(self):
        state = SystemState(active_tasks=5)

        with pytest.raises(AttributeError):
            state.active_tasks = 10

    def test_post_init_runs(self):
        # __post_init__ only logs; assert it does not raise for either branch.
        SystemState()
        SystemState(initialized_at=_now())


# ---------------------------------------------------------------------------
# SystemStateManager singleton / double-checked locking
# ---------------------------------------------------------------------------
class TestSystemStateManagerSingleton:
    """Singleton identity and double-checked-locking behaviour."""

    def test_singleton_pattern(self):
        assert SystemStateManager() is SystemStateManager()

    def test_get_instance_returns_same_after_reset(self):
        first = SystemStateManager()
        # Force a rebuild and confirm a new instance is created post-reset.
        SystemStateManager._instance = None
        second = SystemStateManager()

        assert first is not second
        # But repeated calls keep returning the new one.
        assert second is SystemStateManager()

    def test_fresh_instance_has_clean_state_and_history(self):
        manager = SystemStateManager()

        assert manager.state is None
        assert manager.get_history() == []

    def test_double_checked_locking_concurrent_creation(self):
        # Reset, then build the singleton from many threads at once. Every
        # thread must observe the *same* object (double-checked locking).
        SystemStateManager._instance = None
        instances = []

        def build():
            instances.append(SystemStateManager())

        threads = [Thread(target=build) for _ in range(25)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(instances) == 25
        assert all(inst is instances[0] for inst in instances)


# ---------------------------------------------------------------------------
# SystemStateManager state transitions and behaviour
# ---------------------------------------------------------------------------
class TestSystemStateManager:
    """State transitions, type checks, history, metrics, increments."""

    def test_initial_state_is_none(self):
        assert SystemStateManager().state is None

    def test_update_state(self):
        manager = SystemStateManager()
        state = SystemState(initialized_at=_now())

        manager.update_state(state)

        assert manager.state is state

    @pytest.mark.parametrize("bad", ["not a state", {"k": "v"}, 42, None, object()])
    def test_update_state_type_checking(self, bad):
        manager = SystemStateManager()

        with pytest.raises(TypeError):
            manager.update_state(bad)

    def test_update_state_pushes_previous_to_history(self):
        manager = SystemStateManager()
        first = SystemState(active_tasks=1)
        second = SystemState(active_tasks=2)

        manager.update_state(first)  # no previous -> history stays empty
        assert manager.get_history() == []

        manager.update_state(second)  # first becomes history
        history = manager.get_history()
        assert len(history) == 1
        assert history[-1] is first
        assert manager.state is second

    def test_clear_state(self):
        manager = SystemStateManager()
        state = SystemState(initialized_at=_now())
        manager.update_state(state)

        manager.clear_state()

        assert manager.state is None
        # Cleared state is archived in history.
        assert manager.get_history()[-1] is state

    def test_clear_state_when_already_none(self):
        manager = SystemStateManager()

        manager.clear_state()  # nothing to archive

        assert manager.state is None
        assert manager.get_history() == []

    def test_is_initialized_method(self):
        manager = SystemStateManager()

        assert manager.is_initialized() is False  # state is None

        manager.update_state(SystemState())  # state exists but not initialized
        assert manager.is_initialized() is False

        manager.update_state(SystemState(initialized_at=_now()))
        assert manager.is_initialized() is True

    def test_get_state_or_raise_when_initialized(self):
        manager = SystemStateManager()
        state = SystemState(initialized_at=_now())
        manager.update_state(state)

        assert manager.get_state_or_raise() is state

    def test_get_state_or_raise_when_state_none(self):
        manager = SystemStateManager()

        with pytest.raises(SystemNotInitializedError):
            manager.get_state_or_raise()

    def test_get_state_or_raise_when_state_uninitialized(self):
        manager = SystemStateManager()
        manager.update_state(SystemState())  # present but initialized_at is None

        with pytest.raises(SystemNotInitializedError):
            manager.get_state_or_raise()

    def test_increment_tasks(self):
        manager = SystemStateManager()
        manager.update_state(
            SystemState(
                initialized_at=_now(),
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
        manager = SystemStateManager()
        manager.update_state(SystemState(initialized_at=_now(), active_tasks=2))

        manager.increment_tasks(active=-5)  # would be -3

        assert manager.state.active_tasks == 0  # clamped to 0

    def test_increment_tasks_negative_completed_not_clamped(self):
        # Only active_tasks is clamped; completed/failed are free to go negative.
        manager = SystemStateManager()
        manager.update_state(
            SystemState(initialized_at=_now(), completed_tasks=1, failed_tasks=1)
        )

        manager.increment_tasks(completed=-5, failed=-5)

        assert manager.state.completed_tasks == -4
        assert manager.state.failed_tasks == -4

    def test_increment_tasks_noop_when_state_none(self):
        manager = SystemStateManager()

        manager.increment_tasks(active=3, completed=3, failed=3)  # no state yet

        assert manager.state is None

    def test_increment_tasks_does_not_archive_to_history(self):
        # increment_tasks replaces _state directly, bypassing update_state,
        # so it must NOT add to history.
        manager = SystemStateManager()
        manager.update_state(SystemState(initialized_at=_now(), active_tasks=0))

        manager.increment_tasks(active=1)

        assert manager.get_history() == []

    def test_get_history_returns_copy(self):
        manager = SystemStateManager()
        manager.update_state(SystemState(active_tasks=1))
        manager.update_state(SystemState(active_tasks=2))

        history = manager.get_history()
        history.append(SystemState(active_tasks=999))

        # External mutation must not affect the manager's internal history.
        assert len(manager.get_history()) == 1

    def test_history_max_size(self):
        manager = SystemStateManager()

        for i in range(15):
            manager.update_state(SystemState(active_tasks=i))

        history = manager.get_history()

        # First update has no previous state, so 14 are archived then trimmed to 10.
        assert len(history) == 10
        # Should hold the 10 most recent archived states (active_tasks 4..13).
        assert [s.active_tasks for s in history] == list(range(4, 14))

    def test_get_metrics_uninitialized(self):
        manager = SystemStateManager()

        metrics = manager.get_metrics()

        assert metrics == {
            "initialized": False,
            "active_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
        }

    def test_get_metrics_initialized(self):
        manager = SystemStateManager()
        config = InitializationConfig(gpu_enabled=True, monitoring_enabled=True)
        ts = _now()
        manager.update_state(
            SystemState(
                config=config,
                initialized_at=ts,
                active_tasks=5,
                completed_tasks=100,
                failed_tasks=2,
            )
        )

        metrics = manager.get_metrics()

        assert metrics["initialized"] is True
        assert metrics["gpu_enabled"] is True
        # has_monitoring inspects the `monitoring` field (None here), NOT config.
        assert metrics["monitoring_enabled"] is False
        assert metrics["active_tasks"] == 5
        assert metrics["completed_tasks"] == 100
        assert metrics["failed_tasks"] == 2
        assert metrics["initialized_at"] == ts.isoformat()
        assert metrics["version"] == "2.0.3"

    def test_get_metrics_monitoring_enabled_via_field(self):
        manager = SystemStateManager()
        manager.update_state(
            SystemState(initialized_at=_now(), monitoring=MagicMock())
        )

        assert manager.get_metrics()["monitoring_enabled"] is True

    def test_get_metrics_initialized_at_none(self):
        # State present but initialized_at is None -> isoformat branch skipped.
        manager = SystemStateManager()
        manager.update_state(SystemState(active_tasks=1))

        metrics = manager.get_metrics()

        assert metrics["initialized"] is False
        assert metrics["initialized_at"] is None

    def test_repr_none(self):
        manager = SystemStateManager()

        assert repr(manager) == "SystemStateManager(state=None)"

    def test_repr_initialized(self):
        manager = SystemStateManager()
        manager.update_state(SystemState(initialized_at=_now()))

        assert repr(manager) == "SystemStateManager(initialized=True)"

    def test_repr_present_but_uninitialized(self):
        manager = SystemStateManager()
        manager.update_state(SystemState())

        assert repr(manager) == "SystemStateManager(initialized=False)"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------
class TestSystemStateManagerThreadSafety:
    """Concurrency tests for reads and atomic increments."""

    def test_concurrent_reads(self):
        manager = SystemStateManager()
        manager.update_state(SystemState(initialized_at=_now()))
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

        assert len(results) == 1000
        assert all(results)

    def test_concurrent_increments(self):
        manager = SystemStateManager()
        manager.update_state(SystemState(initialized_at=_now(), completed_tasks=0))
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

        assert manager.state.completed_tasks == num_threads * increments_per_thread


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------
class TestConvenienceFunctions:
    """Tests for the module-level helper functions."""

    def test_get_system_state_manager_returns_singleton(self):
        m1 = get_system_state_manager()
        m2 = get_system_state_manager()

        assert m1 is m2
        assert isinstance(m1, SystemStateManager)
        # It is the very same object as the class-level singleton.
        assert m1 is SystemStateManager()

    def test_get_current_state(self):
        assert get_current_state() is None

        state = SystemState(initialized_at=_now())
        get_system_state_manager().update_state(state)

        assert get_current_state() is state

    def test_is_system_initialized(self):
        assert is_system_initialized() is False

        get_system_state_manager().update_state(SystemState(initialized_at=_now()))

        assert is_system_initialized() is True

    def test_require_initialized_success(self):
        state = SystemState(initialized_at=_now())
        get_system_state_manager().update_state(state)

        assert require_initialized() is state

    def test_require_initialized_failure(self):
        with pytest.raises(SystemNotInitializedError):
            require_initialized()
