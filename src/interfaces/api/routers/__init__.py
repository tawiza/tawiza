"""API routers package for Tawiza-V2 API."""

from . import (
    active_learning,
    annotations,
    browser,
    code_execution,
    datasets,
    ecocartographe,
    fine_tuning,
    health,
    model_storage,
    models,
    ollama,
    progress,
    prompts,
    retraining,
    training,
    uaa,
    vectors,
)

# Main routers (v2 versions)
from . import feedback_v2 as feedback
from . import predictions_v2 as predictions

__all__ = [
    "active_learning",
    "annotations",
    "browser",
    "code_execution",
    "datasets",
    "ecocartographe",
    "feedback",
    "fine_tuning",
    "health",
    "models",
    "model_storage",
    "ollama",
    "predictions",
    "prompts",
    "progress",
    "retraining",
    "training",
    "uaa",
    "vectors",
]
