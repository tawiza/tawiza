"""
Causal inference module for TAJINE cognitive engine.

Provides:
- Temporal correlation analysis
- Causal DAG management with Neo4j
- Graceful degradation when Neo4j unavailable
"""

from src.infrastructure.agents.tajine.cognitive.causal.correlation import (
    assess_temporal_validity,
    compute_causal_confidence,
    compute_lagged_correlation,
)
from src.infrastructure.agents.tajine.cognitive.causal.dag_manager import DAGManager
from src.infrastructure.agents.tajine.cognitive.causal.models import (
    CausalChain,
    CausalHypothesis,
    CausalLink,
)

__all__ = [
    # Models
    "CausalHypothesis",
    "CausalLink",
    "CausalChain",
    # Correlation
    "compute_lagged_correlation",
    "assess_temporal_validity",
    "compute_causal_confidence",
    # DAG
    "DAGManager",
]
