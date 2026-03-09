"""API-based collectors for structured data sources."""

from .gdelt import GDELTCollector
from .google_trends import GoogleTrendsCollector
from .banque_france import BanqueFranceCollector

__all__ = [
    "GDELTCollector",
    "GoogleTrendsCollector", 
    "BanqueFranceCollector"
]
