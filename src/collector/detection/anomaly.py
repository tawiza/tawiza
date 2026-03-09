"""Anomaly detection for territorial signals.

Uses statistical methods (z-score, IQR) as baseline,
with PyOD for advanced multivariate detection.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from loguru import logger


@dataclass
class DetectedAnomaly:
    """A detected anomaly in signal data."""

    anomaly_type: str  # 'spike', 'drop', 'trend_change'
    metric_name: str
    code_commune: str | None
    score: float  # 0-1, higher = more significant
    description: str
    sources: list[str]
    related_values: dict[str, Any]


def detect_zscore_anomalies(
    values: list[float],
    labels: list[str] | None = None,
    threshold: float = 2.5,
) -> list[int]:
    """Detect anomalies using z-score method.

    Args:
        values: Time series values.
        labels: Optional labels for each value.
        threshold: Z-score threshold (default 2.5 = ~1.2% false positive).

    Returns:
        Indices of anomalous values.
    """
    if len(values) < 5:
        return []

    arr = np.array(values, dtype=float)
    mean = np.mean(arr)
    std = np.std(arr)

    if std == 0:
        return []

    z_scores = np.abs((arr - mean) / std)
    return [i for i, z in enumerate(z_scores) if z > threshold]


def detect_iqr_anomalies(
    values: list[float],
    multiplier: float = 1.5,
) -> list[int]:
    """Detect anomalies using IQR method (more robust to outliers).

    Args:
        values: Time series values.
        multiplier: IQR multiplier (1.5 = standard, 3.0 = extreme only).

    Returns:
        Indices of anomalous values.
    """
    if len(values) < 5:
        return []

    arr = np.array(values, dtype=float)
    q1 = np.percentile(arr, 25)
    q3 = np.percentile(arr, 75)
    iqr = q3 - q1

    if iqr == 0:
        return []

    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    return [i for i, v in enumerate(arr) if v < lower or v > upper]


def classify_anomaly(
    values: list[float],
    anomaly_idx: int,
) -> str:
    """Classify an anomaly as spike, drop, or trend_change."""
    if anomaly_idx >= len(values):
        return "unknown"

    val = values[anomaly_idx]
    mean = np.mean(values)

    if val > mean:
        return "spike"
    else:
        return "drop"


def cross_source_detection(
    source_anomalies: dict[str, list[DetectedAnomaly]],
    min_sources: int = 2,
) -> list[DetectedAnomaly]:
    """Detect micro-signals by crossing anomalies from multiple sources.

    A micro-signal = anomaly detected in 2+ sources for same commune.

    Args:
        source_anomalies: Dict of source -> anomalies.
        min_sources: Minimum number of sources required for cross-detection.

    Returns:
        List of cross-source anomalies.
    """
    # Group by commune
    commune_anomalies: dict[str, list[tuple[str, DetectedAnomaly]]] = {}

    for source, anomalies in source_anomalies.items():
        for anomaly in anomalies:
            commune = anomaly.code_commune or "national"
            if commune not in commune_anomalies:
                commune_anomalies[commune] = []
            commune_anomalies[commune].append((source, anomaly))

    # Find communes with anomalies from multiple sources
    micro_signals = []
    for commune, entries in commune_anomalies.items():
        sources = list(set(src for src, _ in entries))
        if len(sources) >= min_sources:
            # Calculate convergence score
            avg_score = np.mean([a.score for _, a in entries])
            convergence_bonus = min(len(sources) * 0.1, 0.3)

            # Determine overall type
            types = [a.anomaly_type for _, a in entries]
            if types.count("spike") > types.count("drop"):
                overall_type = "dynamisme_territorial"
                signal_desc = "Signaux de dynamisme"
            else:
                overall_type = "declin_territorial"
                signal_desc = "Signaux de déclin"

            micro_signals.append(
                DetectedAnomaly(
                    anomaly_type=overall_type,
                    metric_name="micro_signal",
                    code_commune=commune if commune != "national" else None,
                    score=min(avg_score + convergence_bonus, 1.0),
                    description=(
                        f"{signal_desc} détectés sur {len(sources)} sources "
                        f"({', '.join(sources)}) pour la commune {commune}"
                    ),
                    sources=sources,
                    related_values={
                        "anomaly_count": len(entries),
                        "source_count": len(sources),
                        "details": [
                            {"source": src, "type": a.anomaly_type, "score": a.score}
                            for src, a in entries
                        ],
                    },
                )
            )

    logger.info(
        f"[detection] Cross-source: {len(micro_signals)} micro-signals "
        f"from {sum(len(a) for a in source_anomalies.values())} anomalies"
    )

    return sorted(micro_signals, key=lambda x: -x.score)
