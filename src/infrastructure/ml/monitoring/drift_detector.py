"""
Data drift detector for monitoring distribution changes.
"""

from typing import Any

import numpy as np
from loguru import logger


class DriftDetector:
    """Detects data drift in predictions."""

    def __init__(self, baseline_window_days: int = 30):
        """
        Initialize drift detector.

        Args:
            baseline_window_days: Days of data for baseline
        """
        self.baseline_window_days = baseline_window_days
        self.baseline_distribution: dict[str, Any] | None = None

    def set_baseline(self, samples: list[dict[str, Any]]) -> None:
        """
        Set baseline distribution.

        Args:
            samples: Baseline samples
        """
        # Extract features
        features = self._extract_features(samples)

        # Calculate distribution statistics
        self.baseline_distribution = {
            "mean": np.mean(features, axis=0).tolist(),
            "std": np.std(features, axis=0).tolist(),
            "count": len(samples),
        }

        logger.info(
            f"Set baseline distribution with {len(samples)} samples"
        )

    def detect_drift(
        self,
        current_samples: list[dict[str, Any]],
        threshold: float = 0.1,
    ) -> dict[str, Any]:
        """
        Detect drift in current samples.

        Args:
            current_samples: Current samples to compare
            threshold: Drift detection threshold

        Returns:
            Drift detection result
        """
        if self.baseline_distribution is None:
            return {
                "drift_detected": False,
                "reason": "No baseline set",
            }

        # Extract features from current samples
        current_features = self._extract_features(current_samples)

        # Calculate current distribution
        current_mean = np.mean(current_features, axis=0)
        _current_std = np.std(current_features, axis=0)

        baseline_mean = np.array(self.baseline_distribution["mean"])
        baseline_std = np.array(self.baseline_distribution["std"])

        # Calculate drift score using Kullback-Leibler-like metric
        # Simplified: mean squared difference normalized by std
        mean_diff = np.mean(
            np.abs(current_mean - baseline_mean) / (baseline_std + 1e-6)
        )

        drift_detected = mean_diff > threshold

        result = {
            "drift_detected": drift_detected,
            "drift_score": float(mean_diff),
            "threshold": threshold,
            "baseline_samples": self.baseline_distribution["count"],
            "current_samples": len(current_samples),
        }

        if drift_detected:
            logger.warning(
                f"Data drift detected: score={mean_diff:.4f} > {threshold}"
            )

        return result

    def _extract_features(
        self,
        samples: list[dict[str, Any]],
    ) -> np.ndarray:
        """
        Extract numeric features from samples.

        Args:
            samples: Input samples

        Returns:
            Numpy array of features
        """
        # Simple feature extraction
        # Assumes samples have numeric features
        features = []

        for sample in samples:
            feature_vector = []

            # Extract numeric values
            for _key, value in sample.items():
                if isinstance(value, (int, float)):
                    feature_vector.append(value)

            if feature_vector:
                features.append(feature_vector)

        if not features:
            # Return dummy features if none found
            return np.zeros((len(samples), 1))

        return np.array(features)
