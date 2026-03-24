"""Lightweight ML model for cascade probability prediction.

Replaces heuristic `propagation_factor * confidence * 0.5` with a
logistic regression trained on graph features. Falls back to heuristic
if scikit-learn is unavailable or training data is insufficient.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

MODEL_PATH = Path(__file__).parent / "cascade_model.pkl"

FEATURES = [
    "relation_confidence",
    "source_headcount",
    "target_headcount",
    "depth",
    "source_degree",
    "target_degree",
    "same_sector",
    "relation_weight",
]

_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model

    try:
        from sklearn.linear_model import LogisticRegression  # noqa: F401

        if MODEL_PATH.exists():
            with open(MODEL_PATH, "rb") as f:
                _model = pickle.load(f)  # nosec B301
            logger.info("Cascade model loaded from {}", MODEL_PATH)
        else:
            _model = _bootstrap_model()
            logger.info("Cascade model bootstrapped with synthetic data")
        return _model
    except ImportError:
        logger.warning("scikit-learn not available, cascade model disabled")
        return None


def _bootstrap_model():
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(42)
    n = 2000

    confidence = rng.uniform(0.1, 0.95, n)
    src_hc = rng.uniform(0.01, 1.0, n)
    tgt_hc = rng.uniform(0.01, 1.0, n)
    depth = rng.choice([1, 2, 3], n, p=[0.5, 0.3, 0.2])
    src_deg = rng.integers(1, 50, n).astype(float)
    tgt_deg = rng.integers(1, 30, n).astype(float)
    same_sector = rng.choice([0, 1], n, p=[0.6, 0.4]).astype(float)
    weight = rng.uniform(0.5, 2.0, n)

    X = np.column_stack([confidence, src_hc, tgt_hc, depth, src_deg, tgt_deg, same_sector, weight])

    score = (
        confidence * 0.35
        + (1.0 / depth) * 0.25
        + same_sector * 0.15
        + (1.0 / (1 + src_deg / 10)) * 0.10
        + weight * 0.05
        + (tgt_hc / (src_hc + 0.01)) * 0.10
    )
    noise = rng.normal(0, 0.08, n)
    y = (score + noise > 0.45).astype(int)

    model = LogisticRegression(max_iter=500, C=1.0)
    model.fit(X, y)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    return model


def predict_cascade_probability(
    relation_confidence: float,
    source_headcount: int,
    target_headcount: int,
    depth: int,
    source_degree: int,
    target_degree: int,
    same_sector: bool,
    relation_weight: float,
) -> float:
    """Predict cascade probability using logistic regression.

    Falls back to a depth-decaying heuristic if the model is unavailable.

    Args:
        relation_confidence: Confidence score of the relation [0, 1].
        source_headcount: Estimated employees at source actor.
        target_headcount: Estimated employees at target actor.
        depth: BFS depth (1 = direct neighbor).
        source_degree: Number of relations from the source actor.
        target_degree: Number of relations from the target actor.
        same_sector: Whether source and target share a 2-digit NAF code.
        relation_weight: Weight of the relation edge.

    Returns:
        Cascade probability clipped to [0.01, 0.95].
    """
    model = _get_model()
    if model is None:
        # Fallback heuristic (depth-decaying)
        return relation_confidence * 0.5 * (0.5 ** (depth - 1))

    max_hc = max(source_headcount, target_headcount, 1)
    norm_src = min(source_headcount / max_hc, 1.0)
    norm_tgt = min(target_headcount / max_hc, 1.0)

    features = np.array(
        [
            [
                relation_confidence,
                norm_src,
                norm_tgt,
                depth,
                source_degree,
                target_degree,
                1.0 if same_sector else 0.0,
                relation_weight,
            ]
        ]
    )

    prob = model.predict_proba(features)[0][1]
    return float(np.clip(prob, 0.01, 0.95))


def retrain_from_outcomes(outcomes: list[dict[str, Any]]) -> None:
    """Retrain the model from observed cascade outcomes.

    Each outcome dict must contain:
    - ``features``: dict with keys matching :data:`FEATURES`
    - ``actually_cascaded``: bool indicating whether cascade occurred

    Requires at least 50 outcomes for statistical validity.
    """
    if len(outcomes) < 50:
        logger.warning("Not enough outcomes ({}) for retraining, need 50+", len(outcomes))
        return

    from sklearn.linear_model import LogisticRegression

    X = np.array([[o["features"][f] for f in FEATURES] for o in outcomes])
    y = np.array([1 if o["actually_cascaded"] else 0 for o in outcomes])

    model = LogisticRegression(max_iter=500, C=1.0)
    model.fit(X, y)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    global _model
    _model = model
    logger.info("Cascade model retrained on {} outcomes", len(outcomes))
