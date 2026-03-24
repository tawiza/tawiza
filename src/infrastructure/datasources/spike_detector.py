"""Welford's streaming algorithm for real-time spike detection.

Inspired by World Monitor's trending-keywords.ts implementation.
Detects anomalous spikes in data flow rates using streaming statistics.

Algorithm:
    - Maintains running mean/variance with O(1) memory per stream
    - Compares rolling window count against baseline using z-scores
    - Tracks multiple streams independently (by feed, category, keyword, etc.)

Usage:
    detector = SpikeDetector()

    # Feed data points as they arrive
    detector.record("bodacc_creations", count=15)
    detector.record("bodacc_creations", count=12)
    detector.record("bodacc_creations", count=45)  # spike!

    # Check for spikes
    spikes = detector.detect_spikes()
    # [{"stream": "bodacc_creations", "current": 45, "mean": 13.5, "z_score": 4.2, "severity": "high"}]
"""

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SpikeSeverity(StrEnum):
    """Spike severity levels based on z-score thresholds."""

    NONE = "none"
    LOW = "low"  # z >= 1.5  -  unusual
    MEDIUM = "medium"  # z >= 2.0  -  notable
    HIGH = "high"  # z >= 3.0  -  significant spike
    CRITICAL = "critical"  # z >= 4.0  -  extreme anomaly


# Z-score thresholds (from World Monitor's trending-keywords.ts)
Z_THRESHOLDS = {
    SpikeSeverity.LOW: 1.5,
    SpikeSeverity.MEDIUM: 2.0,
    SpikeSeverity.HIGH: 3.0,
    SpikeSeverity.CRITICAL: 4.0,
}


@dataclass
class WelfordState:
    """Welford's online algorithm state  -  only 3 scalars needed.

    Maintains running statistics for a single stream.
    """

    mean: float = 0.0
    m2: float = 0.0  # sum of squared deviations
    count: int = 0
    last_value: float = 0.0
    last_update: float = 0.0  # unix timestamp

    def update(self, value: float) -> None:
        """Update running statistics with a new observation.

        Welford's formula:
            delta = value - mean
            mean += delta / count
            delta2 = value - mean  (new mean)
            m2 += delta * delta2
        """
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2
        self.last_value = value
        self.last_update = time.time()

    @property
    def variance(self) -> float:
        """Population variance."""
        if self.count < 2:
            return 0.0
        return self.m2 / self.count

    @property
    def std_dev(self) -> float:
        """Population standard deviation."""
        return self.variance**0.5

    @property
    def z_score(self) -> float:
        """Z-score of the last observed value."""
        if self.std_dev < 0.001 or self.count < 5:
            return 0.0
        return (self.last_value - self.mean) / self.std_dev


@dataclass
class SpikeEvent:
    """A detected spike event."""

    stream: str
    current_value: float
    mean: float
    std_dev: float
    z_score: float
    severity: SpikeSeverity
    sample_count: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream": self.stream,
            "current": self.current_value,
            "mean": round(self.mean, 2),
            "std_dev": round(self.std_dev, 2),
            "z_score": round(self.z_score, 2),
            "severity": self.severity.value,
            "sample_count": self.sample_count,
            "timestamp": self.timestamp,
        }


class SpikeDetector:
    """Multi-stream spike detector using Welford's algorithm.

    Tracks multiple independent streams and detects anomalous spikes.
    Each stream has its own running mean/variance.
    """

    # Minimum observations before spike detection activates
    MIN_SAMPLES = 10

    # Cooldown period between spike alerts for the same stream (seconds)
    COOLDOWN_SECONDS = 1800  # 30 minutes

    # Minimum absolute count to trigger a spike (avoid noise on low-volume streams)
    MIN_SPIKE_COUNT = 3

    def __init__(self):
        self._streams: dict[str, WelfordState] = {}
        self._last_spike: dict[str, float] = {}  # stream -> last spike timestamp

    def record(self, stream: str, count: float) -> SpikeEvent | None:
        """Record an observation for a stream and check for spikes.

        Args:
            stream: Stream identifier (e.g., "rss_eco_national", "bodacc_creations")
            count: Observed count/rate for this time window

        Returns:
            SpikeEvent if a spike is detected, None otherwise
        """
        if stream not in self._streams:
            self._streams[stream] = WelfordState()

        state = self._streams[stream]
        state.update(count)

        # Check for spike
        if state.count < self.MIN_SAMPLES:
            return None

        if count < self.MIN_SPIKE_COUNT:
            return None

        severity = self._classify(state.z_score)
        if severity == SpikeSeverity.NONE:
            return None

        # Check cooldown
        now = time.time()
        last = self._last_spike.get(stream, 0)
        if now - last < self.COOLDOWN_SECONDS:
            return None

        self._last_spike[stream] = now

        return SpikeEvent(
            stream=stream,
            current_value=count,
            mean=state.mean,
            std_dev=state.std_dev,
            z_score=state.z_score,
            severity=severity,
            sample_count=state.count,
        )

    def detect_spikes(self, min_severity: SpikeSeverity = SpikeSeverity.LOW) -> list[SpikeEvent]:
        """Check all streams for current spikes.

        Returns list of streams currently in spike state.
        """
        min_z = Z_THRESHOLDS.get(min_severity, 1.5)
        spikes = []

        for stream, state in self._streams.items():
            if state.count < self.MIN_SAMPLES:
                continue
            if state.z_score >= min_z and state.last_value >= self.MIN_SPIKE_COUNT:
                severity = self._classify(state.z_score)
                spikes.append(
                    SpikeEvent(
                        stream=stream,
                        current_value=state.last_value,
                        mean=state.mean,
                        std_dev=state.std_dev,
                        z_score=state.z_score,
                        severity=severity,
                        sample_count=state.count,
                    )
                )

        spikes.sort(key=lambda s: s.z_score, reverse=True)
        return spikes

    def get_stream_stats(self, stream: str) -> dict[str, Any] | None:
        """Get current statistics for a stream."""
        state = self._streams.get(stream)
        if not state:
            return None
        return {
            "stream": stream,
            "mean": round(state.mean, 2),
            "std_dev": round(state.std_dev, 2),
            "variance": round(state.variance, 2),
            "count": state.count,
            "last_value": state.last_value,
            "z_score": round(state.z_score, 2),
            "last_update": state.last_update,
        }

    def all_stats(self) -> list[dict[str, Any]]:
        """Get stats for all tracked streams."""
        return [self.get_stream_stats(s) for s in sorted(self._streams.keys())]

    def reset_stream(self, stream: str) -> None:
        """Reset a stream's statistics."""
        self._streams.pop(stream, None)
        self._last_spike.pop(stream, None)

    @staticmethod
    def _classify(z_score: float) -> SpikeSeverity:
        """Classify z-score into severity level."""
        if z_score >= Z_THRESHOLDS[SpikeSeverity.CRITICAL]:
            return SpikeSeverity.CRITICAL
        elif z_score >= Z_THRESHOLDS[SpikeSeverity.HIGH]:
            return SpikeSeverity.HIGH
        elif z_score >= Z_THRESHOLDS[SpikeSeverity.MEDIUM]:
            return SpikeSeverity.MEDIUM
        elif z_score >= Z_THRESHOLDS[SpikeSeverity.LOW]:
            return SpikeSeverity.LOW
        return SpikeSeverity.NONE


# Global singleton for cross-service spike detection
spike_detector = SpikeDetector()
