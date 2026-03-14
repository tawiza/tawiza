"""MAB scheduler for source selection.

Two algorithms available:
- MABScheduler: UCB1 (non-contextual) - simple, effective baseline
- LinUCBScheduler: LinUCB (contextual) - territory-aware source selection
"""

from .linucb_scheduler import ContextFeatures, LinUCBArm, LinUCBScheduler
from .mab_scheduler import MABScheduler
from .source_arm import SourceArm, SourceType

__all__ = [
    # Data models
    "SourceArm",
    "SourceType",
    # UCB1 (non-contextual)
    "MABScheduler",
    # LinUCB (contextual)
    "LinUCBScheduler",
    "LinUCBArm",
    "ContextFeatures",
]
