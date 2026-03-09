"""
QLib DataHandler adaptation for territorial intelligence.

This module adapts Microsoft QLib's DataHandler concepts for territorial analysis.
Key differences from QLib:
- "instruments" become "territories" (departments)
- Financial metrics become territorial indicators
- Cross-sectional analysis across territories instead of stocks
"""

from .ops import *
from .processor import *
from .handler import TerritorialDataHandler
from .dataset import TerritorialDataset
from .expressions import ALPHA_EXPRESSIONS

__version__ = "1.0.0"
__all__ = [
    "TerritorialDataHandler",
    "TerritorialDataset", 
    "ALPHA_EXPRESSIONS",
]