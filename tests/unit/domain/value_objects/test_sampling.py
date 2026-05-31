"""Tests for active learning sampling value objects.

This module tests the value objects defined in
``src.domain.value_objects.sampling``:

- SamplingStrategyType enum
- SamplingConfig value object (validation + invariants)
- SampleScore value object (validation + invariants)
- SamplingResult value object (validation + helper methods)
- DriftMetric value object (validation + computed metrics)

Tests cover valid construction, invariant validation (out-of-bounds ->
ValueError), helper/transition methods, equality/hashing/immutability,
serialization (to_dict from the ValueObject base), and edge cases (empty
collections, None optionals, boundary values).
"""

import pytest

from src.domain.value_objects.sampling import (
    DriftMetric,
    SampleScore,
    SamplingConfig,
    SamplingResult,
    SamplingStrategyType,
)


class TestSamplingStrategyType:
    """Tests for SamplingStrategyType enum."""

    def test_strategy_type_values(self):
        """SamplingStrategyType should have correct string values."""
        assert SamplingStrategyType.UNCERTAINTY.value == "uncertainty"
        assert SamplingStrategyType.MARGIN.value == "margin"
        assert SamplingStrategyType.ENTROPY.value == "entropy"
        assert SamplingStrategyType.DIVERSITY.value == "diversity"
        assert SamplingStrategyType.RANDOM.value == "random"

    def test_strategy_type_is_str_enum(self):
        """SamplingStrategyType members should behave as strings (StrEnum)."""
        assert SamplingStrategyType.UNCERTAINTY == "uncertainty"
        assert str(SamplingStrategyType.RANDOM) == "random"

    def test_strategy_type_membership(self):
        """All expected members should be present and no more."""
        values = {member.value for member in SamplingStrategyType}
        assert values == {
            "uncertainty",
            "margin",
            "entropy",
            "diversity",
            "random",
        }

    def test_strategy_type_from_value(self):
        """SamplingStrategyType should be constructible from its value."""
        assert SamplingStrategyType("entropy") is SamplingStrategyType.ENTROPY


class TestSamplingConfig:
    """Tests for SamplingConfig value object."""

    def test_config_creation_minimal(self):
        """SamplingConfig should be created with required fields only."""
        config = SamplingConfig(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            sample_count=10,
        )

        assert config.strategy_type == SamplingStrategyType.UNCERTAINTY
        assert config.sample_count == 10
        assert config.threshold is None
        assert config.diversity_metric is None
        assert config.min_samples_per_cluster is None
        assert config.filters is None

    def test_config_creation_full(self):
        """SamplingConfig should accept all optional fields."""
        filters = {"label": "positive", "min_score": 0.5}
        config = SamplingConfig(
            strategy_type=SamplingStrategyType.DIVERSITY,
            sample_count=25,
            threshold=0.7,
            diversity_metric="cosine",
            min_samples_per_cluster=3,
            filters=filters,
        )

        assert config.strategy_type == SamplingStrategyType.DIVERSITY
        assert config.sample_count == 25
        assert config.threshold == 0.7
        assert config.diversity_metric == "cosine"
        assert config.min_samples_per_cluster == 3
        assert config.filters == filters

    def test_config_sample_count_zero_rejected(self):
        """sample_count of 0 should raise ValueError."""
        with pytest.raises(ValueError, match="sample_count must be positive"):
            SamplingConfig(
                strategy_type=SamplingStrategyType.RANDOM,
                sample_count=0,
            )

    def test_config_sample_count_negative_rejected(self):
        """Negative sample_count should raise ValueError."""
        with pytest.raises(ValueError, match="sample_count must be positive"):
            SamplingConfig(
                strategy_type=SamplingStrategyType.RANDOM,
                sample_count=-5,
            )

    def test_config_sample_count_one_accepted(self):
        """sample_count of 1 is the smallest valid value."""
        config = SamplingConfig(
            strategy_type=SamplingStrategyType.MARGIN,
            sample_count=1,
        )

        assert config.sample_count == 1

    def test_config_threshold_below_range_rejected(self):
        """threshold below 0 should raise ValueError."""
        with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
            SamplingConfig(
                strategy_type=SamplingStrategyType.ENTROPY,
                sample_count=5,
                threshold=-0.1,
            )

    def test_config_threshold_above_range_rejected(self):
        """threshold above 1 should raise ValueError."""
        with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
            SamplingConfig(
                strategy_type=SamplingStrategyType.ENTROPY,
                sample_count=5,
                threshold=1.5,
            )

    def test_config_threshold_boundary_values_accepted(self):
        """threshold of exactly 0 and 1 should be valid."""
        config_low = SamplingConfig(
            strategy_type=SamplingStrategyType.ENTROPY,
            sample_count=5,
            threshold=0.0,
        )
        config_high = SamplingConfig(
            strategy_type=SamplingStrategyType.ENTROPY,
            sample_count=5,
            threshold=1.0,
        )

        assert config_low.threshold == 0.0
        assert config_high.threshold == 1.0

    def test_config_min_samples_per_cluster_zero_rejected(self):
        """min_samples_per_cluster of 0 should raise ValueError."""
        with pytest.raises(
            ValueError, match="min_samples_per_cluster must be positive"
        ):
            SamplingConfig(
                strategy_type=SamplingStrategyType.DIVERSITY,
                sample_count=5,
                min_samples_per_cluster=0,
            )

    def test_config_min_samples_per_cluster_negative_rejected(self):
        """Negative min_samples_per_cluster should raise ValueError."""
        with pytest.raises(
            ValueError, match="min_samples_per_cluster must be positive"
        ):
            SamplingConfig(
                strategy_type=SamplingStrategyType.DIVERSITY,
                sample_count=5,
                min_samples_per_cluster=-2,
            )

    def test_config_min_samples_per_cluster_one_accepted(self):
        """min_samples_per_cluster of 1 is the smallest valid value."""
        config = SamplingConfig(
            strategy_type=SamplingStrategyType.DIVERSITY,
            sample_count=5,
            min_samples_per_cluster=1,
        )

        assert config.min_samples_per_cluster == 1

    def test_config_is_frozen(self):
        """SamplingConfig should be immutable."""
        config = SamplingConfig(
            strategy_type=SamplingStrategyType.RANDOM,
            sample_count=5,
        )

        with pytest.raises(AttributeError):
            config.sample_count = 10

    def test_config_equality(self):
        """Two configs with the same values should be equal and share a hash."""
        config1 = SamplingConfig(
            strategy_type=SamplingStrategyType.MARGIN,
            sample_count=10,
            threshold=0.5,
        )
        config2 = SamplingConfig(
            strategy_type=SamplingStrategyType.MARGIN,
            sample_count=10,
            threshold=0.5,
        )

        assert config1 == config2
        assert hash(config1) == hash(config2)

    def test_config_inequality(self):
        """Configs with differing values should not be equal."""
        config1 = SamplingConfig(
            strategy_type=SamplingStrategyType.MARGIN,
            sample_count=10,
        )
        config2 = SamplingConfig(
            strategy_type=SamplingStrategyType.MARGIN,
            sample_count=20,
        )

        assert config1 != config2

    def test_config_inequality_with_other_type(self):
        """A config should never equal a non-config object."""
        config = SamplingConfig(
            strategy_type=SamplingStrategyType.RANDOM,
            sample_count=5,
        )

        assert config != "not a config"
        assert config != 123

    def test_config_to_dict(self):
        """to_dict should expose all dataclass fields."""
        config = SamplingConfig(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            sample_count=10,
            threshold=0.8,
            diversity_metric="euclidean",
            min_samples_per_cluster=2,
            filters={"k": "v"},
        )

        data = config.to_dict()

        assert data["strategy_type"] == SamplingStrategyType.UNCERTAINTY
        assert data["sample_count"] == 10
        assert data["threshold"] == 0.8
        assert data["diversity_metric"] == "euclidean"
        assert data["min_samples_per_cluster"] == 2
        assert data["filters"] == {"k": "v"}


class TestSampleScore:
    """Tests for SampleScore value object."""

    def test_score_creation_minimal(self):
        """SampleScore should be created with required fields only."""
        score = SampleScore(sample_id="pred-1", score=0.42)

        assert score.sample_id == "pred-1"
        assert score.score == 0.42
        assert score.confidence is None
        assert score.entropy is None
        assert score.margin is None
        assert score.metadata is None

    def test_score_creation_full(self):
        """SampleScore should accept all optional fields."""
        score = SampleScore(
            sample_id="pred-2",
            score=0.9,
            confidence=0.6,
            entropy=1.3,
            margin=0.2,
            metadata={"label": "A"},
        )

        assert score.confidence == 0.6
        assert score.entropy == 1.3
        assert score.margin == 0.2
        assert score.metadata == {"label": "A"}

    def test_score_negative_score_allowed(self):
        """The raw score has no bounds and may be negative."""
        score = SampleScore(sample_id="pred-3", score=-5.0)

        assert score.score == -5.0

    def test_score_confidence_below_range_rejected(self):
        """confidence below 0 should raise ValueError."""
        with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
            SampleScore(sample_id="x", score=0.5, confidence=-0.01)

    def test_score_confidence_above_range_rejected(self):
        """confidence above 1 should raise ValueError."""
        with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
            SampleScore(sample_id="x", score=0.5, confidence=1.01)

    def test_score_confidence_boundary_values_accepted(self):
        """confidence of exactly 0 and 1 should be valid."""
        low = SampleScore(sample_id="x", score=0.5, confidence=0.0)
        high = SampleScore(sample_id="y", score=0.5, confidence=1.0)

        assert low.confidence == 0.0
        assert high.confidence == 1.0

    def test_score_entropy_negative_rejected(self):
        """Negative entropy should raise ValueError."""
        with pytest.raises(ValueError, match="entropy must be non-negative"):
            SampleScore(sample_id="x", score=0.5, entropy=-0.001)

    def test_score_entropy_zero_accepted(self):
        """entropy of 0 should be valid."""
        score = SampleScore(sample_id="x", score=0.5, entropy=0.0)

        assert score.entropy == 0.0

    def test_score_entropy_large_value_accepted(self):
        """entropy has no upper bound."""
        score = SampleScore(sample_id="x", score=0.5, entropy=12.5)

        assert score.entropy == 12.5

    def test_score_margin_below_range_rejected(self):
        """margin below 0 should raise ValueError."""
        with pytest.raises(ValueError, match="margin must be between 0 and 1"):
            SampleScore(sample_id="x", score=0.5, margin=-0.2)

    def test_score_margin_above_range_rejected(self):
        """margin above 1 should raise ValueError."""
        with pytest.raises(ValueError, match="margin must be between 0 and 1"):
            SampleScore(sample_id="x", score=0.5, margin=1.2)

    def test_score_margin_boundary_values_accepted(self):
        """margin of exactly 0 and 1 should be valid."""
        low = SampleScore(sample_id="x", score=0.5, margin=0.0)
        high = SampleScore(sample_id="y", score=0.5, margin=1.0)

        assert low.margin == 0.0
        assert high.margin == 1.0

    def test_score_is_frozen(self):
        """SampleScore should be immutable."""
        score = SampleScore(sample_id="x", score=0.5)

        with pytest.raises(AttributeError):
            score.score = 0.9

    def test_score_equality_and_hash(self):
        """Two scores with same values should be equal and hashable to same value."""
        score1 = SampleScore(sample_id="x", score=0.5, confidence=0.3)
        score2 = SampleScore(sample_id="x", score=0.5, confidence=0.3)

        assert score1 == score2
        assert hash(score1) == hash(score2)

    def test_score_inequality(self):
        """Scores differing in any field should not be equal."""
        score1 = SampleScore(sample_id="x", score=0.5)
        score2 = SampleScore(sample_id="y", score=0.5)

        assert score1 != score2

    def test_score_to_dict(self):
        """to_dict should expose all dataclass fields."""
        score = SampleScore(
            sample_id="pred-9",
            score=0.7,
            confidence=0.55,
            entropy=0.9,
            margin=0.1,
            metadata={"src": "test"},
        )

        data = score.to_dict()

        assert data["sample_id"] == "pred-9"
        assert data["score"] == 0.7
        assert data["confidence"] == 0.55
        assert data["entropy"] == 0.9
        assert data["margin"] == 0.1
        assert data["metadata"] == {"src": "test"}


class TestSamplingResult:
    """Tests for SamplingResult value object."""

    @staticmethod
    def _config() -> SamplingConfig:
        return SamplingConfig(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            sample_count=3,
        )

    def test_result_creation(self):
        """SamplingResult should be created with valid fields."""
        config = self._config()
        samples = [
            SampleScore(sample_id="a", score=0.9),
            SampleScore(sample_id="b", score=0.5),
        ]
        result = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=10,
            config=config,
            execution_time_ms=12.5,
            metadata={"run": 1},
        )

        assert result.strategy_type == SamplingStrategyType.UNCERTAINTY
        assert result.selected_samples == samples
        assert result.total_candidates == 10
        assert result.config == config
        assert result.execution_time_ms == 12.5
        assert result.metadata == {"run": 1}

    def test_result_creation_minimal(self):
        """Optional fields default to None."""
        config = self._config()
        result = SamplingResult(
            strategy_type=SamplingStrategyType.RANDOM,
            selected_samples=[],
            total_candidates=0,
            config=config,
        )

        assert result.execution_time_ms is None
        assert result.metadata is None

    def test_result_negative_total_candidates_rejected(self):
        """total_candidates below 0 should raise ValueError."""
        with pytest.raises(ValueError, match="total_candidates must be non-negative"):
            SamplingResult(
                strategy_type=SamplingStrategyType.RANDOM,
                selected_samples=[],
                total_candidates=-1,
                config=self._config(),
            )

    def test_result_total_candidates_zero_accepted(self):
        """total_candidates of 0 with no samples should be valid."""
        result = SamplingResult(
            strategy_type=SamplingStrategyType.RANDOM,
            selected_samples=[],
            total_candidates=0,
            config=self._config(),
        )

        assert result.total_candidates == 0

    def test_result_selected_exceeds_candidates_rejected(self):
        """selected_samples count exceeding total_candidates should raise."""
        samples = [
            SampleScore(sample_id="a", score=0.1),
            SampleScore(sample_id="b", score=0.2),
        ]
        with pytest.raises(
            ValueError, match="selected_samples cannot exceed total_candidates"
        ):
            SamplingResult(
                strategy_type=SamplingStrategyType.RANDOM,
                selected_samples=samples,
                total_candidates=1,
                config=self._config(),
            )

    def test_result_selected_equal_to_candidates_accepted(self):
        """selected_samples count equal to total_candidates is the boundary."""
        samples = [
            SampleScore(sample_id="a", score=0.1),
            SampleScore(sample_id="b", score=0.2),
        ]
        result = SamplingResult(
            strategy_type=SamplingStrategyType.RANDOM,
            selected_samples=samples,
            total_candidates=2,
            config=self._config(),
        )

        assert len(result.selected_samples) == result.total_candidates

    def test_result_negative_execution_time_rejected(self):
        """Negative execution_time_ms should raise ValueError."""
        with pytest.raises(ValueError, match="execution_time_ms must be non-negative"):
            SamplingResult(
                strategy_type=SamplingStrategyType.RANDOM,
                selected_samples=[],
                total_candidates=0,
                config=self._config(),
                execution_time_ms=-0.5,
            )

    def test_result_execution_time_zero_accepted(self):
        """execution_time_ms of 0 should be valid."""
        result = SamplingResult(
            strategy_type=SamplingStrategyType.RANDOM,
            selected_samples=[],
            total_candidates=0,
            config=self._config(),
            execution_time_ms=0.0,
        )

        assert result.execution_time_ms == 0.0

    def test_get_sample_ids(self):
        """get_sample_ids should preserve selection order."""
        samples = [
            SampleScore(sample_id="first", score=0.9),
            SampleScore(sample_id="second", score=0.5),
            SampleScore(sample_id="third", score=0.7),
        ]
        result = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=10,
            config=self._config(),
        )

        assert result.get_sample_ids() == ["first", "second", "third"]

    def test_get_sample_ids_empty(self):
        """get_sample_ids should return an empty list when no samples."""
        result = SamplingResult(
            strategy_type=SamplingStrategyType.RANDOM,
            selected_samples=[],
            total_candidates=0,
            config=self._config(),
        )

        assert result.get_sample_ids() == []

    def test_get_average_score(self):
        """get_average_score should compute the arithmetic mean of scores."""
        samples = [
            SampleScore(sample_id="a", score=0.2),
            SampleScore(sample_id="b", score=0.4),
            SampleScore(sample_id="c", score=0.6),
        ]
        result = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=10,
            config=self._config(),
        )

        assert result.get_average_score() == pytest.approx(0.4)

    def test_get_average_score_empty_returns_zero(self):
        """get_average_score should return 0.0 for an empty selection."""
        result = SamplingResult(
            strategy_type=SamplingStrategyType.RANDOM,
            selected_samples=[],
            total_candidates=0,
            config=self._config(),
        )

        assert result.get_average_score() == 0.0

    def test_get_top_n(self):
        """get_top_n should return the highest-scoring samples in descending order."""
        samples = [
            SampleScore(sample_id="low", score=0.1),
            SampleScore(sample_id="high", score=0.9),
            SampleScore(sample_id="mid", score=0.5),
        ]
        result = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=10,
            config=self._config(),
        )

        top = result.get_top_n(2)

        assert [s.sample_id for s in top] == ["high", "mid"]

    def test_get_top_n_more_than_available(self):
        """get_top_n should return all samples when n exceeds the count."""
        samples = [
            SampleScore(sample_id="a", score=0.1),
            SampleScore(sample_id="b", score=0.9),
        ]
        result = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=10,
            config=self._config(),
        )

        top = result.get_top_n(10)

        assert len(top) == 2
        assert [s.sample_id for s in top] == ["b", "a"]

    def test_get_top_n_zero(self):
        """get_top_n(0) should return an empty list."""
        samples = [SampleScore(sample_id="a", score=0.1)]
        result = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=10,
            config=self._config(),
        )

        assert result.get_top_n(0) == []

    def test_get_top_n_empty_selection(self):
        """get_top_n on an empty selection should return an empty list."""
        result = SamplingResult(
            strategy_type=SamplingStrategyType.RANDOM,
            selected_samples=[],
            total_candidates=0,
            config=self._config(),
        )

        assert result.get_top_n(5) == []

    def test_result_equality(self):
        """Two results with identical values should be equal."""
        config = self._config()
        samples = [SampleScore(sample_id="a", score=0.5)]
        result1 = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=5,
            config=config,
        )
        result2 = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=5,
            config=config,
        )

        assert result1 == result2

    def test_result_to_dict(self):
        """to_dict should expose all dataclass fields."""
        config = self._config()
        samples = [SampleScore(sample_id="a", score=0.5)]
        result = SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=samples,
            total_candidates=5,
            config=config,
            execution_time_ms=3.3,
            metadata={"k": "v"},
        )

        data = result.to_dict()

        assert data["strategy_type"] == SamplingStrategyType.UNCERTAINTY
        assert data["selected_samples"] == samples
        assert data["total_candidates"] == 5
        assert data["config"] == config
        assert data["execution_time_ms"] == 3.3
        assert data["metadata"] == {"k": "v"}


class TestDriftMetric:
    """Tests for DriftMetric value object."""

    def test_drift_metric_creation(self):
        """DriftMetric should be created with valid fields."""
        metric = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=0.9,
            threshold=0.05,
            is_drifted=True,
        )

        assert metric.metric_name == "accuracy"
        assert metric.current_value == 0.8
        assert metric.baseline_value == 0.9
        assert metric.threshold == 0.05
        assert metric.is_drifted is True

    def test_drift_metric_negative_threshold_rejected(self):
        """Negative threshold should raise ValueError."""
        with pytest.raises(ValueError, match="threshold must be non-negative"):
            DriftMetric(
                metric_name="accuracy",
                current_value=0.8,
                baseline_value=0.9,
                threshold=-0.01,
                is_drifted=False,
            )

    def test_drift_metric_zero_threshold_accepted(self):
        """threshold of 0 should be valid."""
        metric = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=0.8,
            threshold=0.0,
            is_drifted=False,
        )

        assert metric.threshold == 0.0

    def test_get_deviation(self):
        """get_deviation should return the absolute difference."""
        metric = DriftMetric(
            metric_name="loss",
            current_value=0.5,
            baseline_value=0.2,
            threshold=0.1,
            is_drifted=True,
        )

        assert metric.get_deviation() == pytest.approx(0.3)

    def test_get_deviation_is_absolute(self):
        """get_deviation should be non-negative even when current < baseline."""
        metric = DriftMetric(
            metric_name="loss",
            current_value=0.2,
            baseline_value=0.5,
            threshold=0.1,
            is_drifted=True,
        )

        assert metric.get_deviation() == pytest.approx(0.3)

    def test_get_deviation_percentage(self):
        """get_deviation_percentage should be relative to the baseline magnitude."""
        metric = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=1.0,
            threshold=0.1,
            is_drifted=True,
        )

        assert metric.get_deviation_percentage() == pytest.approx(20.0)

    def test_get_deviation_percentage_uses_absolute_baseline(self):
        """A negative baseline should still produce a positive percentage."""
        metric = DriftMetric(
            metric_name="signed_metric",
            current_value=-2.0,
            baseline_value=-4.0,
            threshold=1.0,
            is_drifted=True,
        )

        # deviation = |-2 - -4| = 2, baseline magnitude = 4 -> 50%
        assert metric.get_deviation_percentage() == pytest.approx(50.0)

    def test_get_deviation_percentage_zero_baseline_returns_zero(self):
        """A zero baseline should yield 0.0 to avoid division by zero."""
        metric = DriftMetric(
            metric_name="counter",
            current_value=5.0,
            baseline_value=0.0,
            threshold=1.0,
            is_drifted=True,
        )

        assert metric.get_deviation_percentage() == 0.0

    def test_calculate_drift_score_partial(self):
        """drift score should be deviation/threshold when below threshold."""
        metric = DriftMetric(
            metric_name="accuracy",
            current_value=0.85,
            baseline_value=0.9,
            threshold=0.1,
            is_drifted=False,
        )

        # deviation = 0.05, threshold = 0.1 -> 0.5
        assert metric.calculate_drift_score() == pytest.approx(0.5)

    def test_calculate_drift_score_capped_at_one(self):
        """drift score should be capped at 1.0 when deviation exceeds threshold."""
        metric = DriftMetric(
            metric_name="accuracy",
            current_value=0.5,
            baseline_value=0.9,
            threshold=0.1,
            is_drifted=True,
        )

        # deviation = 0.4 >> threshold 0.1 -> capped at 1.0
        assert metric.calculate_drift_score() == 1.0

    def test_calculate_drift_score_zero_threshold_with_deviation(self):
        """With a zero threshold and any deviation, drift score should be 1.0."""
        metric = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=0.9,
            threshold=0.0,
            is_drifted=True,
        )

        assert metric.calculate_drift_score() == 1.0

    def test_calculate_drift_score_zero_threshold_no_deviation(self):
        """With a zero threshold and no deviation, drift score should be 0.0."""
        metric = DriftMetric(
            metric_name="accuracy",
            current_value=0.9,
            baseline_value=0.9,
            threshold=0.0,
            is_drifted=False,
        )

        assert metric.calculate_drift_score() == 0.0

    def test_drift_metric_is_frozen(self):
        """DriftMetric should be immutable."""
        metric = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=0.9,
            threshold=0.1,
            is_drifted=True,
        )

        with pytest.raises(AttributeError):
            metric.current_value = 0.5

    def test_drift_metric_equality_and_hash(self):
        """Two drift metrics with identical values should be equal and hash equal."""
        metric1 = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=0.9,
            threshold=0.1,
            is_drifted=True,
        )
        metric2 = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=0.9,
            threshold=0.1,
            is_drifted=True,
        )

        assert metric1 == metric2
        assert hash(metric1) == hash(metric2)

    def test_drift_metric_inequality(self):
        """Drift metrics differing in any field should not be equal."""
        metric1 = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=0.9,
            threshold=0.1,
            is_drifted=True,
        )
        metric2 = DriftMetric(
            metric_name="accuracy",
            current_value=0.8,
            baseline_value=0.9,
            threshold=0.1,
            is_drifted=False,
        )

        assert metric1 != metric2

    def test_drift_metric_to_dict(self):
        """to_dict should expose all dataclass fields."""
        metric = DriftMetric(
            metric_name="f1",
            current_value=0.7,
            baseline_value=0.85,
            threshold=0.1,
            is_drifted=True,
        )

        data = metric.to_dict()

        assert data["metric_name"] == "f1"
        assert data["current_value"] == 0.7
        assert data["baseline_value"] == 0.85
        assert data["threshold"] == 0.1
        assert data["is_drifted"] is True
