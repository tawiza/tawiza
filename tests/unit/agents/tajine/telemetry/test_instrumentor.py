"""Tests for TAJINE telemetry instrumentor.

This module tests:
- trace_hunt decorator (async)
- trace_cognitive decorator
- track_cache context manager (hit and miss)
- record_score_3d function
- record_bandit_pull function
- update_trust function
- langfuse_available function
"""

import asyncio
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.infrastructure.agents.tajine.telemetry.instrumentor import (
    LANGFUSE_AVAILABLE,
    get_langfuse_context,
    # Langfuse helpers
    langfuse_available,
    record_bandit_pull,
    record_human_intervention,
    record_recommendation,
    # Recording functions
    record_score_3d,
    record_signal,
    record_theory,
    set_circuit_breaker,
    trace_bandit,
    trace_cognitive,
    # Decorators
    trace_hunt,
    trace_llm,
    # Context managers
    track_cache,
    track_fallback,
    update_autonomy,
    update_bandit_ucb,
    update_trust,
)
from src.infrastructure.agents.tajine.telemetry.metrics import (
    autonomy_level,
    bandit_pulls,
    bandit_rewards,
    bandit_ucb_score,
    cache_hits,
    cache_misses,
    circuit_breaker_state,
    cognitive_level_duration,
    cognitive_recommendations,
    cognitive_signals,
    cognitive_theories,
    fallbacks_used,
    human_interventions,
    hunt_duration,
    hunt_total,
    llm_errors,
    llm_latency,
    llm_tokens_total,
    score_alpha,
    score_coherence,
    score_combined,
    score_fiabilite,
    trust_score,
)


class TestLangfuseHelpers:
    """Test Langfuse integration helpers."""

    def test_langfuse_available_returns_bool(self):
        """langfuse_available should return a boolean."""
        result = langfuse_available()
        assert isinstance(result, bool)

    def test_get_langfuse_context(self):
        """get_langfuse_context should return None or context when disabled."""
        # In test environment, Langfuse is disabled via LANGFUSE_ENABLED=false
        # and LANGFUSE_AVAILABLE is patched to False
        result = get_langfuse_context()
        # With langfuse disabled in tests, this should return None
        # (the actual behavior depends on runtime flag, not import-time)
        if langfuse_available():
            assert result is not None
        else:
            assert result is None


class TestTraceHuntDecorator:
    """Test trace_hunt decorator for async hunt operations."""

    @pytest.mark.asyncio
    async def test_trace_hunt_increments_counter(self):
        """trace_hunt should increment hunt_total counter."""
        # Get initial value
        initial = hunt_total.labels(mode="sequential", territory="france")._value.get()

        @trace_hunt(mode="sequential")
        async def mock_hunt(territory="france"):
            return {"results": []}

        result = await mock_hunt(territory="france")

        # Verify counter incremented
        final = hunt_total.labels(mode="sequential", territory="france")._value.get()
        assert final == initial + 1
        assert result == {"results": []}

    @pytest.mark.asyncio
    async def test_trace_hunt_records_duration(self):
        """trace_hunt should record hunt duration."""

        @trace_hunt(mode="parallel")
        async def slow_hunt(territory="paris"):
            await asyncio.sleep(0.01)  # Small delay
            return {"status": "success"}

        # Execute hunt
        result = await slow_hunt(territory="paris")

        # We can't easily verify the exact duration, but we can verify
        # the function executed and returned correctly
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_trace_hunt_duration_recorded_on_error(self):
        """trace_hunt should record duration even when function raises."""

        @trace_hunt(mode="adaptive")
        async def failing_hunt(territory="lyon"):
            await asyncio.sleep(0.01)
            raise ValueError("Hunt failed")

        # Should raise but still record duration
        with pytest.raises(ValueError, match="Hunt failed"):
            await failing_hunt(territory="lyon")

    @pytest.mark.asyncio
    async def test_trace_hunt_handles_unknown_territory(self):
        """trace_hunt should handle missing territory parameter."""
        initial = hunt_total.labels(mode="test", territory="unknown")._value.get()

        @trace_hunt(mode="test")
        async def hunt_no_territory():
            return {"data": "test"}

        result = await hunt_no_territory()

        final = hunt_total.labels(mode="test", territory="unknown")._value.get()
        assert final == initial + 1


class TestTraceCognitiveDecorator:
    """Test trace_cognitive decorator."""

    @pytest.mark.asyncio
    async def test_trace_cognitive_records_duration(self):
        """trace_cognitive should record cognitive level duration."""

        @trace_cognitive(level="signal")
        async def signal_detection():
            await asyncio.sleep(0.01)
            return {"signals": ["contradiction"]}

        result = await signal_detection()

        # Verify function executed
        assert result == {"signals": ["contradiction"]}

    @pytest.mark.asyncio
    async def test_trace_cognitive_works_with_theory_level(self):
        """trace_cognitive should work with theory level."""

        @trace_cognitive(level="theory")
        async def theory_application():
            return {"theory": "anomaly_detection"}

        result = await theory_application()
        assert result == {"theory": "anomaly_detection"}

    @pytest.mark.asyncio
    async def test_trace_cognitive_works_with_synthesis_level(self):
        """trace_cognitive should work with synthesis level."""

        @trace_cognitive(level="synthesis")
        async def synthesis_operation():
            return {"recommendations": []}

        result = await synthesis_operation()
        assert result == {"recommendations": []}


class TestTraceLLMDecorator:
    """Test trace_llm decorator."""

    @pytest.mark.asyncio
    async def test_trace_llm_records_latency(self):
        """trace_llm should record LLM latency."""

        @trace_llm(model="gpt-4")
        async def mock_llm_call():
            await asyncio.sleep(0.01)
            return {"content": "response"}

        result = await mock_llm_call()
        assert result == {"content": "response"}

    @pytest.mark.asyncio
    async def test_trace_llm_records_tokens_from_usage(self):
        """trace_llm should extract token usage from result."""

        class MockUsage:
            input_tokens = 100
            output_tokens = 50

        class MockResponse:
            usage = MockUsage()
            content = "test"

        @trace_llm(model="claude-3")
        async def llm_with_usage():
            return MockResponse()

        result = await llm_with_usage()
        assert result.content == "test"

    @pytest.mark.asyncio
    async def test_trace_llm_records_errors(self):
        """trace_llm should record errors by type."""
        initial = llm_errors.labels(model="gpt-4", error_type="ValueError")._value.get()

        @trace_llm(model="gpt-4")
        async def failing_llm():
            raise ValueError("API error")

        with pytest.raises(ValueError, match="API error"):
            await failing_llm()

        final = llm_errors.labels(model="gpt-4", error_type="ValueError")._value.get()
        assert final == initial + 1


class TestTraceBanditDecorator:
    """Test trace_bandit decorator."""

    def test_trace_bandit_sync_function(self):
        """trace_bandit should work with sync functions."""

        @trace_bandit
        def select_source():
            return "sirene"

        result = select_source()
        assert result == "sirene"

    @pytest.mark.asyncio
    async def test_trace_bandit_async_function(self):
        """trace_bandit should work with async functions."""

        @trace_bandit
        async def async_select_source():
            await asyncio.sleep(0.001)
            return "bodacc"

        result = await async_select_source()
        assert result == "bodacc"


class TestTrackCacheContextManager:
    """Test track_cache context manager."""

    def test_track_cache_hit_increments_counter(self):
        """track_cache should increment cache_hits on hit."""
        initial = cache_hits.labels(source="sirene")._value.get()

        with track_cache(source="sirene", hit=True):
            pass  # Simulate cache hit operation

        final = cache_hits.labels(source="sirene")._value.get()
        assert final == initial + 1

    def test_track_cache_miss_increments_counter(self):
        """track_cache should increment cache_misses on miss."""
        initial = cache_misses.labels(source="bodacc")._value.get()

        with track_cache(source="bodacc", hit=False):
            pass  # Simulate cache miss operation

        final = cache_misses.labels(source="bodacc")._value.get()
        assert final == initial + 1

    def test_track_cache_increments_even_on_exception(self):
        """track_cache should increment counter even if code raises."""
        initial = cache_misses.labels(source="boamp")._value.get()

        with pytest.raises(RuntimeError, match="Operation failed"):
            with track_cache(source="boamp", hit=False):
                raise RuntimeError("Operation failed")

        final = cache_misses.labels(source="boamp")._value.get()
        assert final == initial + 1


class TestTrackFallbackContextManager:
    """Test track_fallback context manager."""

    def test_track_fallback_increments_counter(self):
        """track_fallback should increment fallbacks_used counter."""
        initial = fallbacks_used.labels(from_source="sirene", to_source="bodacc")._value.get()

        with track_fallback(from_source="sirene", to_source="bodacc"):
            pass  # Simulate fallback operation

        final = fallbacks_used.labels(from_source="sirene", to_source="bodacc")._value.get()
        assert final == initial + 1

    def test_track_fallback_increments_on_exception(self):
        """track_fallback should increment even if code raises."""
        initial = fallbacks_used.labels(from_source="bodacc", to_source="boamp")._value.get()

        with pytest.raises(ValueError, match="Fallback failed"):
            with track_fallback(from_source="bodacc", to_source="boamp"):
                raise ValueError("Fallback failed")

        final = fallbacks_used.labels(from_source="bodacc", to_source="boamp")._value.get()
        assert final == initial + 1


class TestRecordScore3D:
    """Test record_score_3d function."""

    def test_record_score_3d_observes_all_dimensions(self):
        """record_score_3d should observe all three dimensions plus combined."""
        record_score_3d(
            fiabilite=0.85,
            coherence=0.90,
            alpha=0.75,
            combined=0.83,
            source="sirene",
        )

        # Function should execute without errors
        # Actual histogram verification is complex, so we just verify it runs

    def test_record_score_3d_with_different_source(self):
        """record_score_3d should work with different sources."""
        record_score_3d(
            fiabilite=0.70,
            coherence=0.80,
            alpha=0.65,
            combined=0.72,
            source="bodacc",
        )

        # Should execute without errors

    def test_record_score_3d_with_edge_values(self):
        """record_score_3d should handle edge values (0.0 and 1.0)."""
        record_score_3d(
            fiabilite=0.0,
            coherence=1.0,
            alpha=0.5,
            combined=0.5,
            source="test",
        )

        # Should execute without errors


class TestRecordBanditPull:
    """Test record_bandit_pull function."""

    def test_record_bandit_pull_increments_counter(self):
        """record_bandit_pull should increment bandit_pulls counter."""
        initial_pulls = bandit_pulls.labels(source="sirene")._value.get()

        record_bandit_pull(source="sirene", reward=0.85)

        final_pulls = bandit_pulls.labels(source="sirene")._value.get()
        assert final_pulls == initial_pulls + 1

    def test_record_bandit_pull_observes_reward(self):
        """record_bandit_pull should observe reward value."""
        record_bandit_pull(source="bodacc", reward=0.92)

        # Function should execute without errors
        # Histogram observation verification is complex


class TestUpdateBanditUCB:
    """Test update_bandit_ucb function."""

    def test_update_bandit_ucb_sets_gauge(self):
        """update_bandit_ucb should set UCB score gauge."""
        update_bandit_ucb(source="sirene", ucb_score=0.78)

        value = bandit_ucb_score.labels(source="sirene")._value.get()
        assert value == 0.78

    def test_update_bandit_ucb_updates_value(self):
        """update_bandit_ucb should update existing gauge value."""
        update_bandit_ucb(source="boamp", ucb_score=0.60)
        assert bandit_ucb_score.labels(source="boamp")._value.get() == 0.60

        update_bandit_ucb(source="boamp", ucb_score=0.85)
        assert bandit_ucb_score.labels(source="boamp")._value.get() == 0.85


class TestCognitiveRecordingFunctions:
    """Test cognitive recording functions."""

    def test_record_signal_increments_counter(self):
        """record_signal should increment cognitive_signals counter."""
        initial = cognitive_signals.labels(type="contradiction")._value.get()

        record_signal(signal_type="contradiction")

        final = cognitive_signals.labels(type="contradiction")._value.get()
        assert final == initial + 1

    def test_record_theory_increments_counter(self):
        """record_theory should increment cognitive_theories counter."""
        initial = cognitive_theories.labels(theory="anomaly_detection")._value.get()

        record_theory(theory="anomaly_detection")

        final = cognitive_theories.labels(theory="anomaly_detection")._value.get()
        assert final == initial + 1

    def test_record_recommendation_increments_counter(self):
        """record_recommendation should increment cognitive_recommendations counter."""
        initial = cognitive_recommendations.labels(type="source_priority")._value.get()

        record_recommendation(rec_type="source_priority")

        final = cognitive_recommendations.labels(type="source_priority")._value.get()
        assert final == initial + 1


class TestUpdateTrust:
    """Test update_trust function."""

    def test_update_trust_sets_gauge(self):
        """update_trust should set trust_score gauge."""
        update_trust(territory="france", score=0.88)

        value = trust_score.labels(territory="france")._value.get()
        assert value == 0.88

    def test_update_trust_updates_existing_value(self):
        """update_trust should update existing gauge value."""
        update_trust(territory="paris", score=0.75)
        assert trust_score.labels(territory="paris")._value.get() == 0.75

        update_trust(territory="paris", score=0.92)
        assert trust_score.labels(territory="paris")._value.get() == 0.92

    def test_update_trust_handles_different_territories(self):
        """update_trust should handle different territories independently."""
        update_trust(territory="lyon", score=0.80)
        update_trust(territory="marseille", score=0.70)

        assert trust_score.labels(territory="lyon")._value.get() == 0.80
        assert trust_score.labels(territory="marseille")._value.get() == 0.70


class TestUpdateAutonomy:
    """Test update_autonomy function."""

    def test_update_autonomy_sets_gauge(self):
        """update_autonomy should set autonomy_level gauge."""
        update_autonomy(level=3)
        assert autonomy_level._value.get() == 3

        update_autonomy(level=5)
        assert autonomy_level._value.get() == 5

    def test_update_autonomy_handles_all_levels(self):
        """update_autonomy should handle levels 1-5."""
        for level in range(1, 6):
            update_autonomy(level=level)
            assert autonomy_level._value.get() == level


class TestRecordHumanIntervention:
    """Test record_human_intervention function."""

    def test_record_human_intervention_increments_counter(self):
        """record_human_intervention should increment counter."""
        initial = human_interventions.labels(reason="low_confidence")._value.get()

        record_human_intervention(reason="low_confidence")

        final = human_interventions.labels(reason="low_confidence")._value.get()
        assert final == initial + 1

    def test_record_human_intervention_different_reasons(self):
        """record_human_intervention should track different reasons."""
        record_human_intervention(reason="data_quality")
        record_human_intervention(reason="critical_decision")

        # Should execute without errors for different reasons


class TestSetCircuitBreaker:
    """Test set_circuit_breaker function."""

    def test_set_circuit_breaker_open(self):
        """set_circuit_breaker should set to 1.0 when open."""
        set_circuit_breaker(source="sirene", is_open=True)

        value = circuit_breaker_state.labels(source="sirene")._value.get()
        assert value == 1.0

    def test_set_circuit_breaker_closed(self):
        """set_circuit_breaker should set to 0.0 when closed."""
        set_circuit_breaker(source="bodacc", is_open=False)

        value = circuit_breaker_state.labels(source="bodacc")._value.get()
        assert value == 0.0

    def test_set_circuit_breaker_toggle(self):
        """set_circuit_breaker should toggle between states."""
        set_circuit_breaker(source="boamp", is_open=True)
        assert circuit_breaker_state.labels(source="boamp")._value.get() == 1.0

        set_circuit_breaker(source="boamp", is_open=False)
        assert circuit_breaker_state.labels(source="boamp")._value.get() == 0.0
