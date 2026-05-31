"""Tests for the anomaly detection module.

This module tests the statistical anomaly detectors used for
territorial signals (issue #161 coverage):

- detect_zscore_anomalies (z-score based detection)
- detect_iqr_anomalies (IQR based, robust to outliers)
- classify_anomaly (spike / drop classification)
- cross_source_detection (multi-source convergence)
- DetectedAnomaly dataclass fields and score bounding
"""

from src.collector.detection.anomaly import (
    DetectedAnomaly,
    classify_anomaly,
    cross_source_detection,
    detect_iqr_anomalies,
    detect_zscore_anomalies,
)


def _make_anomaly(
    anomaly_type: str = "spike",
    metric_name: str = "metric",
    code_commune: str | None = "75056",
    score: float = 0.7,
    sources: list[str] | None = None,
) -> DetectedAnomaly:
    """Factory helper for a DetectedAnomaly with sane defaults."""
    return DetectedAnomaly(
        anomaly_type=anomaly_type,
        metric_name=metric_name,
        code_commune=code_commune,
        score=score,
        description="test anomaly",
        sources=sources or ["source_a"],
        related_values={},
    )


class TestDetectZScoreAnomalies:
    """Tests for detect_zscore_anomalies."""

    def test_flat_series_returns_empty(self):
        """A perfectly flat series has std=0, so no anomalies."""
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]

        assert detect_zscore_anomalies(values) == []

    def test_fewer_than_five_points_returns_empty(self):
        """Series with fewer than 5 points is too short to analyze."""
        values = [1.0, 100.0, 2.0, 3.0]

        assert detect_zscore_anomalies(values) == []

    def test_exactly_five_points_is_analyzed_with_low_threshold(self):
        """Exactly 5 points is the minimum accepted length (not skipped).

        With only 5 points a single outlier's z-score is mathematically
        capped near 2.0, so a lower threshold is needed to flag it. This
        proves the series is analyzed rather than short-circuited by the
        len < 5 guard.
        """
        # 4 stable points + 1 clear outlier
        values = [10.0, 10.0, 10.0, 10.0, 100.0]

        # Below the cap, nothing is flagged...
        assert detect_zscore_anomalies(values, threshold=2.5) == []
        # ...but a lower threshold confirms the series WAS processed.
        assert detect_zscore_anomalies(values, threshold=1.5) == [4]

    def test_single_clear_outlier_detected(self):
        """A single clear outlier should be returned by its index."""
        values = [10.0, 10.0, 11.0, 10.0, 10.0, 10.0, 10.0, 100.0]

        result = detect_zscore_anomalies(values)

        assert result == [7]

    def test_zero_std_returns_empty(self):
        """When standard deviation is zero, no division and no anomalies."""
        values = [5.0, 5.0, 5.0, 5.0, 5.0]

        assert detect_zscore_anomalies(values) == []

    def test_no_anomaly_in_stable_noisy_series(self):
        """Small variations under the threshold yield no anomalies."""
        values = [10.0, 11.0, 9.0, 10.0, 11.0, 9.0, 10.0]

        assert detect_zscore_anomalies(values) == []

    def test_threshold_controls_sensitivity(self):
        """A lower threshold detects an outlier a higher threshold misses."""
        values = [10.0, 10.0, 11.0, 10.0, 10.0, 10.0, 10.0, 100.0]

        # z-score of the outlier here is ~2.65: above 2.5, below 3.0
        assert detect_zscore_anomalies(values, threshold=3.0) == []
        assert detect_zscore_anomalies(values, threshold=2.5) == [7]

    def test_labels_argument_accepted(self):
        """Passing labels must not change the index-based result."""
        # 8 points so the outlier z-score (~2.65) clears the default 2.5.
        values = [10.0, 10.0, 11.0, 10.0, 10.0, 10.0, 10.0, 100.0]
        labels = ["a", "b", "c", "d", "e", "f", "g", "h"]

        assert detect_zscore_anomalies(values, labels=labels) == [7]


class TestDetectIQRAnomalies:
    """Tests for detect_iqr_anomalies."""

    def test_value_outside_iqr_fence_detected(self):
        """A value beyond 1.5*IQR above the upper fence is flagged."""
        values = [10.0, 11.0, 10.0, 12.0, 11.0, 10.0, 11.0, 10.0, 11.0, 200.0]

        result = detect_iqr_anomalies(values)

        assert result == [9]

    def test_fewer_than_five_points_returns_empty(self):
        """Series with fewer than 5 points returns empty."""
        values = [1.0, 2.0, 3.0, 100.0]

        assert detect_iqr_anomalies(values) == []

    def test_zero_iqr_returns_empty(self):
        """When IQR is zero (flat distribution), no anomalies."""
        values = [7.0, 7.0, 7.0, 7.0, 7.0, 7.0]

        assert detect_iqr_anomalies(values) == []

    def test_no_anomaly_in_tight_series(self):
        """A tight series with no outliers returns empty."""
        values = [10.0, 11.0, 12.0, 11.0, 10.0, 12.0, 11.0]

        assert detect_iqr_anomalies(values) == []

    def test_low_outlier_detected(self):
        """A value far below the lower fence is flagged."""
        values = [100.0, 101.0, 99.0, 102.0, 100.0, 101.0, 1.0]

        result = detect_iqr_anomalies(values)

        assert 6 in result

    def test_extreme_multiplier_reduces_detections(self):
        """A larger multiplier (3.0) widens the fence, flagging fewer points."""
        values = [10.0, 11.0, 10.0, 12.0, 11.0, 10.0, 11.0, 10.0, 11.0, 30.0]

        detected_standard = detect_iqr_anomalies(values, multiplier=1.5)
        detected_extreme = detect_iqr_anomalies(values, multiplier=3.0)

        assert 9 in detected_standard
        assert len(detected_extreme) <= len(detected_standard)


class TestClassifyAnomaly:
    """Tests for classify_anomaly."""

    def test_spike_above_mean(self):
        """A value above the mean is classified as a spike."""
        values = [10.0, 10.0, 10.0, 10.0, 100.0]

        assert classify_anomaly(values, anomaly_idx=4) == "spike"

    def test_drop_below_mean(self):
        """A value below the mean is classified as a drop."""
        values = [100.0, 100.0, 100.0, 100.0, 1.0]

        assert classify_anomaly(values, anomaly_idx=4) == "drop"

    def test_index_out_of_range_returns_unknown(self):
        """An out-of-range index returns 'unknown'."""
        values = [1.0, 2.0, 3.0]

        assert classify_anomaly(values, anomaly_idx=10) == "unknown"

    def test_value_equal_to_mean_is_drop(self):
        """A value equal to the mean is not strictly greater, so 'drop'."""
        values = [10.0, 10.0, 10.0]

        # mean == 10.0, val == 10.0 -> not (val > mean) -> drop
        assert classify_anomaly(values, anomaly_idx=0) == "drop"


class TestCrossSourceDetection:
    """Tests for cross_source_detection (multi-source convergence)."""

    def test_agreement_across_sources_yields_signal(self):
        """Two sources flagging the same commune produce a micro-signal."""
        source_anomalies = {
            "source_a": [_make_anomaly(code_commune="75056", score=0.6)],
            "source_b": [_make_anomaly(code_commune="75056", score=0.8)],
        }

        signals = cross_source_detection(source_anomalies, min_sources=2)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.code_commune == "75056"
        assert signal.metric_name == "micro_signal"
        assert set(signal.sources) == {"source_a", "source_b"}
        assert signal.related_values["source_count"] == 2
        assert signal.related_values["anomaly_count"] == 2

    def test_disagreement_single_source_yields_nothing(self):
        """A single source per commune does not reach min_sources."""
        source_anomalies = {
            "source_a": [_make_anomaly(code_commune="75056")],
            "source_b": [_make_anomaly(code_commune="13055")],
        }

        signals = cross_source_detection(source_anomalies, min_sources=2)

        assert signals == []

    def test_spike_majority_is_dynamisme(self):
        """When spikes outnumber drops, type is dynamisme_territorial."""
        source_anomalies = {
            "source_a": [_make_anomaly(anomaly_type="spike", code_commune="75056")],
            "source_b": [_make_anomaly(anomaly_type="spike", code_commune="75056")],
            "source_c": [_make_anomaly(anomaly_type="drop", code_commune="75056")],
        }

        signals = cross_source_detection(source_anomalies, min_sources=2)

        assert len(signals) == 1
        assert signals[0].anomaly_type == "dynamisme_territorial"

    def test_drop_majority_is_declin(self):
        """When drops are not outnumbered by spikes, type is declin_territorial."""
        source_anomalies = {
            "source_a": [_make_anomaly(anomaly_type="drop", code_commune="75056")],
            "source_b": [_make_anomaly(anomaly_type="drop", code_commune="75056")],
        }

        signals = cross_source_detection(source_anomalies, min_sources=2)

        assert len(signals) == 1
        assert signals[0].anomaly_type == "declin_territorial"

    def test_national_anomaly_maps_to_none_commune(self):
        """Anomalies with no commune are grouped under 'national' -> None."""
        source_anomalies = {
            "source_a": [_make_anomaly(code_commune=None)],
            "source_b": [_make_anomaly(code_commune=None)],
        }

        signals = cross_source_detection(source_anomalies, min_sources=2)

        assert len(signals) == 1
        assert signals[0].code_commune is None

    def test_empty_input_returns_empty(self):
        """No sources at all returns an empty list."""
        assert cross_source_detection({}, min_sources=2) == []

    def test_min_sources_three_not_met(self):
        """Requiring 3 sources with only 2 present yields nothing."""
        source_anomalies = {
            "source_a": [_make_anomaly(code_commune="75056")],
            "source_b": [_make_anomaly(code_commune="75056")],
        }

        assert cross_source_detection(source_anomalies, min_sources=3) == []

    def test_results_sorted_by_score_descending(self):
        """Multiple signals are returned sorted by score (highest first)."""
        source_anomalies = {
            "source_a": [
                _make_anomaly(code_commune="75056", score=0.2),
                _make_anomaly(code_commune="13055", score=0.9),
            ],
            "source_b": [
                _make_anomaly(code_commune="75056", score=0.2),
                _make_anomaly(code_commune="13055", score=0.9),
            ],
        }

        signals = cross_source_detection(source_anomalies, min_sources=2)

        assert len(signals) == 2
        assert signals[0].score >= signals[1].score
        assert signals[0].code_commune == "13055"

    def test_score_is_bounded_to_one(self):
        """Convergence bonus must never push the score above 1.0."""
        source_anomalies = {
            "source_a": [_make_anomaly(code_commune="75056", score=1.0)],
            "source_b": [_make_anomaly(code_commune="75056", score=1.0)],
            "source_c": [_make_anomaly(code_commune="75056", score=1.0)],
        }

        signals = cross_source_detection(source_anomalies, min_sources=2)

        assert len(signals) == 1
        assert signals[0].score <= 1.0


class TestDetectedAnomalyDataclass:
    """Tests for the DetectedAnomaly dataclass fields and bounds."""

    def test_fields_assigned(self):
        """All declared fields are stored verbatim on the instance."""
        anomaly = DetectedAnomaly(
            anomaly_type="spike",
            metric_name="emploi",
            code_commune="75056",
            score=0.42,
            description="hausse soudaine",
            sources=["bodacc", "presse"],
            related_values={"delta": 12},
        )

        assert anomaly.anomaly_type == "spike"
        assert anomaly.metric_name == "emploi"
        assert anomaly.code_commune == "75056"
        assert anomaly.score == 0.42
        assert anomaly.description == "hausse soudaine"
        assert anomaly.sources == ["bodacc", "presse"]
        assert anomaly.related_values == {"delta": 12}

    def test_code_commune_can_be_none(self):
        """code_commune is optional and may be None (national signal)."""
        anomaly = _make_anomaly(code_commune=None)

        assert anomaly.code_commune is None

    def test_score_within_zero_one_bounds(self):
        """Scores produced by the detectors are expected within [0, 1]."""
        anomaly = _make_anomaly(score=0.5)

        assert 0.0 <= anomaly.score <= 1.0
