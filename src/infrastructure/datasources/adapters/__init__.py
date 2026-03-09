"""Data source adapters."""

from src.infrastructure.datasources.adapters.ban import BanAdapter
from src.infrastructure.datasources.adapters.boamp import BoampAdapter
from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter

# Weak signal / macroeconomic adapters (Phase 3)
from src.infrastructure.datasources.adapters.dbnomics import DBnomicsAdapter
from src.infrastructure.datasources.adapters.dvf import DVFAdapter
from src.infrastructure.datasources.adapters.france_travail import FranceTravailAdapter
from src.infrastructure.datasources.adapters.gdelt import GdeltAdapter

# New territorial analysis adapters (Phase 2)
from src.infrastructure.datasources.adapters.geo import GeoAdapter
from src.infrastructure.datasources.adapters.google_news import GoogleNewsAdapter
from src.infrastructure.datasources.adapters.insee_local import INSEELocalAdapter
from src.infrastructure.datasources.adapters.melodi import MelodiAdapter
from src.infrastructure.datasources.adapters.ofgl import OFGLAdapter
from src.infrastructure.datasources.adapters.pytrends_adapter import PyTrendsAdapter
from src.infrastructure.datasources.adapters.rna import RnaAdapter
from src.infrastructure.datasources.adapters.rss import RssAdapter
from src.infrastructure.datasources.adapters.rss_enhanced import RssEnhancedAdapter
from src.infrastructure.datasources.adapters.sirene import SireneAdapter
from src.infrastructure.datasources.adapters.subventions import SubventionsAdapter
from src.infrastructure.datasources.adapters.wikipedia_pageviews import WikipediaPageviewsAdapter

__all__ = [
    # Original adapters
    "BodaccAdapter",
    "BoampAdapter",
    "RssAdapter",
    "SireneAdapter",
    "BanAdapter",
    "GdeltAdapter",
    "GoogleNewsAdapter",
    "SubventionsAdapter",
    # New territorial adapters
    "GeoAdapter",
    "DVFAdapter",
    "OFGLAdapter",
    "FranceTravailAdapter",
    "INSEELocalAdapter",
    "MelodiAdapter",
    # Enhanced RSS (65+ feeds, circuit breaker, dedup)
    "RssEnhancedAdapter",
    # RNA (associations)
    "RnaAdapter",
    # Weak signal / macroeconomic adapters
    "DBnomicsAdapter",
    "WikipediaPageviewsAdapter",
    "PyTrendsAdapter",
]
