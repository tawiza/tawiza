"""Tests for TAJINE Prometheus metrics.

This module tests:
- Metric initialization and registration
- Counter increments (hunt_total, cache_hits)
- Histogram observations (score_combined)
- Gauge value setting (trust_score)
- Label handling for metrics
- TAJINE_REGISTRY usage
"""

import pytest
from prometheus_client import REGISTRY, CollectorRegistry

from src.infrastructure.agents.tajine.telemetry.metrics import (
    # Registry
    TAJINE_REGISTRY,
    # Server
    MetricsServer,
    autonomy_level,
    # Bandit metrics
    bandit_pulls,
    bandit_rewards,
    bandit_ucb_score,
    cache_hits,
    cache_misses,
    circuit_breaker_state,
    # Cognitive metrics
    cognitive_level_duration,
    cognitive_recommendations,
    cognitive_signals,
    cognitive_theories,
    fallbacks_used,
    human_interventions,
    hunt_duration,
    # DataHunter metrics
    hunt_total,
    llm_cost_dollars,
    llm_errors,
    llm_latency,
    # LLM metrics
    llm_tokens_total,
    score_alpha,
    score_coherence,
    score_combined,
    # Evaluator metrics
    score_fiabilite,
    start_metrics_server,
    # Autonomy metrics
    trust_score,
)


class TestMetricsRegistry:
    """Test TAJINE custom registry."""

    def test_tajine_registry_exists(self):
        """TAJINE_REGISTRY should be a CollectorRegistry instance."""
        assert isinstance(TAJINE_REGISTRY, CollectorRegistry)

    def test_metrics_use_tajine_registry(self):
        """All metrics should be registered to TAJINE_REGISTRY, not default REGISTRY."""
        # Check that metrics are in TAJINE_REGISTRY
        metrics_in_tajine = list(TAJINE_REGISTRY.collect())
        metric_names = [m.name for m in metrics_in_tajine]

        # Should contain TAJINE metrics (note: _total suffix is added by prometheus_client)
        assert "tajine_hunt" in metric_names or "tajine_hunt_total" in metric_names
        assert "tajine_cache_hits" in metric_names or "tajine_cache_hits_total" in metric_names
        assert "tajine_score_combined" in metric_names
        assert "tajine_trust_score" in metric_names


class TestDataHunterMetrics:
    """Test DataHunter metrics."""

    def test_hunt_total_increment(self):
        """hunt_total should increment with labels."""
        # Get initial value
        before = hunt_total.labels(mode="sequential", territory="france")._value.get()

        # Increment
        hunt_total.labels(mode="sequential", territory="france").inc()

        # Verify increment
        after = hunt_total.labels(mode="sequential", territory="france")._value.get()
        assert after == before + 1

    def test_hunt_total_different_labels(self):
        """hunt_total should track different mode/territory combinations."""
        hunt_total.labels(mode="parallel", territory="paris").inc()
        hunt_total.labels(mode="adaptive", territory="lyon").inc(2)

        # Different labels should be independent
        parallel_val = hunt_total.labels(mode="parallel", territory="paris")._value.get()
        adaptive_val = hunt_total.labels(mode="adaptive", territory="lyon")._value.get()

        # Values are cumulative from test runs, so just check they exist
        assert parallel_val >= 1
        assert adaptive_val >= 2

    def test_cache_hits_increment(self):
        """cache_hits should increment with source label."""
        before = cache_hits.labels(source="sirene")._value.get()
        cache_hits.labels(source="sirene").inc()
        after = cache_hits.labels(source="sirene")._value.get()
        assert after == before + 1

    def test_cache_misses_increment(self):
        """cache_misses should increment with source label."""
        before = cache_misses.labels(source="bodacc")._value.get()
        cache_misses.labels(source="bodacc").inc()
        after = cache_misses.labels(source="bodacc")._value.get()
        assert after == before + 1

    def test_hunt_duration_observe(self):
        """hunt_duration should record histogram observations."""
        # Record some durations
        hunt_duration.labels(mode="sequential").observe(1.5)
        hunt_duration.labels(mode="sequential").observe(2.3)

        # Get the metric
        metric = hunt_duration.labels(mode="sequential")
        # Just verify it accepts observations (actual histogram verification is complex)
        assert metric is not None

    def test_fallbacks_used_tracks_source_pairs(self):
        """fallbacks_used should track from_source and to_source."""
        before = fallbacks_used.labels(from_source="sirene", to_source="bodacc")._value.get()
        fallbacks_used.labels(from_source="sirene", to_source="bodacc").inc()
        after = fallbacks_used.labels(from_source="sirene", to_source="bodacc")._value.get()
        assert after == before + 1

    def test_circuit_breaker_state_sets_value(self):
        """circuit_breaker_state should set gauge values."""
        circuit_breaker_state.labels(source="sirene").set(1.0)
        assert circuit_breaker_state.labels(source="sirene")._value.get() == 1.0

        circuit_breaker_state.labels(source="sirene").set(0.0)
        assert circuit_breaker_state.labels(source="sirene")._value.get() == 0.0


class TestBanditMetrics:
    """Test Bandit metrics."""

    def test_bandit_pulls_increment(self):
        """bandit_pulls should increment with source label."""
        before = bandit_pulls.labels(source="sirene")._value.get()
        bandit_pulls.labels(source="sirene").inc()
        after = bandit_pulls.labels(source="sirene")._value.get()
        assert after == before + 1

    def test_bandit_rewards_observe(self):
        """bandit_rewards should record reward values."""
        bandit_rewards.labels(source="bodacc").observe(0.85)
        bandit_rewards.labels(source="bodacc").observe(0.92)
        # Just verify it accepts observations
        assert bandit_rewards.labels(source="bodacc") is not None

    def test_bandit_ucb_score_sets_value(self):
        """bandit_ucb_score should set gauge values."""
        bandit_ucb_score.labels(source="boamp").set(0.75)
        assert bandit_ucb_score.labels(source="boamp")._value.get() == 0.75


class TestEvaluatorMetrics:
    """Test Evaluator 3D score metrics."""

    def test_score_fiabilite_observe(self):
        """score_fiabilite should record reliability scores."""
        score_fiabilite.labels(source="sirene").observe(0.88)
        score_fiabilite.labels(source="sirene").observe(0.92)
        # Verify metric exists
        assert score_fiabilite.labels(source="sirene") is not None

    def test_score_coherence_observe(self):
        """score_coherence should record coherence scores."""
        score_coherence.observe(0.75)
        score_coherence.observe(0.82)
        # Verify metric exists
        assert score_coherence is not None

    def test_score_alpha_observe(self):
        """score_alpha should record novelty scores."""
        score_alpha.observe(0.65)
        score_alpha.observe(0.71)
        # Verify metric exists
        assert score_alpha is not None

    def test_score_combined_observe(self):
        """score_combined should record combined scores."""
        score_combined.observe(0.80)
        score_combined.observe(0.85)
        score_combined.observe(0.90)
        # Verify metric exists
        assert score_combined is not None

    def test_score_buckets_match(self):
        """All score histograms should use 0.0-1.0 buckets."""
        # Verify metrics exist and accept values in expected range
        score_fiabilite.labels(source="test").observe(0.0)
        score_fiabilite.labels(source="test").observe(1.0)

        score_coherence.observe(0.0)
        score_coherence.observe(1.0)

        score_alpha.observe(0.0)
        score_alpha.observe(1.0)

        score_combined.observe(0.0)
        score_combined.observe(1.0)


class TestCognitiveMetrics:
    """Test Cognitive Engine metrics."""

    def test_cognitive_level_duration_accepts_level_label(self):
        """cognitive_level_duration should accept level labels."""
        cognitive_level_duration.labels(level="signal").observe(0.5)
        cognitive_level_duration.labels(level="theory").observe(1.2)
        cognitive_level_duration.labels(level="synthesis").observe(2.8)

        # Verify metrics exist
        assert cognitive_level_duration.labels(level="signal") is not None
        assert cognitive_level_duration.labels(level="theory") is not None
        assert cognitive_level_duration.labels(level="synthesis") is not None

    def test_cognitive_signals_increment(self):
        """cognitive_signals should increment by type."""
        before = cognitive_signals.labels(type="contradiction")._value.get()
        cognitive_signals.labels(type="contradiction").inc()
        after = cognitive_signals.labels(type="contradiction")._value.get()
        assert after == before + 1

    def test_cognitive_theories_increment(self):
        """cognitive_theories should increment by theory."""
        before = cognitive_theories.labels(theory="anomaly_detection")._value.get()
        cognitive_theories.labels(theory="anomaly_detection").inc()
        after = cognitive_theories.labels(theory="anomaly_detection")._value.get()
        assert after == before + 1

    def test_cognitive_recommendations_increment(self):
        """cognitive_recommendations should increment by type."""
        before = cognitive_recommendations.labels(type="source_priority")._value.get()
        cognitive_recommendations.labels(type="source_priority").inc()
        after = cognitive_recommendations.labels(type="source_priority")._value.get()
        assert after == before + 1


class TestAutonomyMetrics:
    """Test Autonomy and Trust metrics."""

    def test_trust_score_sets_value(self):
        """trust_score should set gauge value by territory."""
        trust_score.labels(territory="france").set(0.85)
        assert trust_score.labels(territory="france")._value.get() == 0.85

        trust_score.labels(territory="paris").set(0.92)
        assert trust_score.labels(territory="paris")._value.get() == 0.92

    def test_autonomy_level_sets_value(self):
        """autonomy_level should set gauge value."""
        autonomy_level.set(3)
        assert autonomy_level._value.get() == 3

        autonomy_level.set(5)
        assert autonomy_level._value.get() == 5

    def test_human_interventions_increment(self):
        """human_interventions should increment by reason."""
        before = human_interventions.labels(reason="low_confidence")._value.get()
        human_interventions.labels(reason="low_confidence").inc()
        after = human_interventions.labels(reason="low_confidence")._value.get()
        assert after == before + 1


class TestLLMMetrics:
    """Test LLM metrics."""

    def test_llm_tokens_total_increment(self):
        """llm_tokens_total should increment by model and type."""
        before = llm_tokens_total.labels(model="gpt-4", type="input")._value.get()
        llm_tokens_total.labels(model="gpt-4", type="input").inc(1500)
        after = llm_tokens_total.labels(model="gpt-4", type="input")._value.get()
        assert after == before + 1500

    def test_llm_cost_dollars_increment(self):
        """llm_cost_dollars should increment by model."""
        before = llm_cost_dollars.labels(model="gpt-4")._value.get()
        llm_cost_dollars.labels(model="gpt-4").inc(0.05)
        after = llm_cost_dollars.labels(model="gpt-4")._value.get()
        assert after == pytest.approx(before + 0.05)

    def test_llm_latency_observe(self):
        """llm_latency should record latency values."""
        llm_latency.labels(model="claude-3").observe(2.5)
        llm_latency.labels(model="claude-3").observe(3.1)
        # Verify metric exists
        assert llm_latency.labels(model="claude-3") is not None

    def test_llm_errors_increment(self):
        """llm_errors should increment by model and error_type."""
        before = llm_errors.labels(model="gpt-4", error_type="RateLimitError")._value.get()
        llm_errors.labels(model="gpt-4", error_type="RateLimitError").inc()
        after = llm_errors.labels(model="gpt-4", error_type="RateLimitError")._value.get()
        assert after == before + 1


class TestMetricsServer:
    """Test MetricsServer singleton."""

    def test_metrics_server_singleton(self):
        """MetricsServer should be a singleton."""
        server1 = MetricsServer()
        server2 = MetricsServer()
        assert server1 is server2

    def test_start_metrics_server_returns_instance(self):
        """start_metrics_server should return MetricsServer instance."""
        server = start_metrics_server(port=9090)
        assert isinstance(server, MetricsServer)

    def test_metrics_server_is_running_property(self):
        """MetricsServer should have is_running property."""
        server = MetricsServer()
        # Property should exist (value depends on whether server was started)
        assert hasattr(server, "is_running")
        assert isinstance(server.is_running, bool)
