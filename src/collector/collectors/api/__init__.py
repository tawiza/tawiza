"""API-based collectors for structured data sources."""

from .banque_france import BanqueFranceCollector
from .gdelt import GDELTCollector
from .google_trends import GoogleTrendsCollector

__all__ = ["GDELTCollector", "GoogleTrendsCollector", "BanqueFranceCollector"]
