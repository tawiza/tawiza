"""Prefect integration for workflow orchestration.

Provides workflow orchestration for ML training pipelines,
retraining automation, and deployment workflows.
"""

from src.infrastructure.ml.prefect.prefect_adapter import PrefectAdapter

__all__ = ["PrefectAdapter"]
