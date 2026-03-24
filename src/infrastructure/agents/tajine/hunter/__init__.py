"""TAJINE DataHunter - Proactive information gathering.

DataHunter v2 Architecture:
- Crawler: Crawl4AI + httpx fallback
- Browser: Playwright + nodriver stealth
- Discovery: ScrapeGraphAI pattern learning
- Scheduler: LinUCB contextual bandit
- Parser: Docling + pdfplumber
"""

from src.infrastructure.agents.tajine.hunter.bandit import SourceBandit
from src.infrastructure.agents.tajine.hunter.crawler import (
    CrawlerConfig,
    CrawlResult,
    TAJINECrawler,
)
from src.infrastructure.agents.tajine.hunter.data_hunter import (
    DataHunter,
    HuntResult,
)
from src.infrastructure.agents.tajine.hunter.discovery_engine import (
    DiscoveredPattern,
    DiscoveryEngine,
    DiscoveryResult,
    discover_data,
)
from src.infrastructure.agents.tajine.hunter.graph_expander import (
    GapType,
    GraphExpander,
    KnowledgeGap,
)
from src.infrastructure.agents.tajine.hunter.hypothesis import (
    Hypothesis,
    HypothesisGenerator,
)
from src.infrastructure.agents.tajine.hunter.resilient import (
    FALLBACK_CHAINS,
    AugmentedData,
    DataCache,
    FallbackSourceChain,
    FetchResult,
    PersistentBanditMixin,
    RareDataAugmenter,
    ResilientFetcher,
)
from src.infrastructure.agents.tajine.hunter.resilient_hunter import (
    PersistentSourceBandit,
    ResilientDataHunter,
    ResilientHuntResult,
)

__all__ = [
    # Crawler
    "TAJINECrawler",
    "CrawlResult",
    "CrawlerConfig",
    # Original
    "SourceBandit",
    "HypothesisGenerator",
    "Hypothesis",
    "GraphExpander",
    "KnowledgeGap",
    "GapType",
    "DataHunter",
    "HuntResult",
    # Resilience
    "ResilientFetcher",
    "FallbackSourceChain",
    "DataCache",
    "RareDataAugmenter",
    "PersistentBanditMixin",
    "FetchResult",
    "AugmentedData",
    "FALLBACK_CHAINS",
    # Resilient Hunter
    "ResilientDataHunter",
    "ResilientHuntResult",
    "PersistentSourceBandit",
    # Discovery Engine (v2)
    "DiscoveryEngine",
    "DiscoveredPattern",
    "DiscoveryResult",
    "discover_data",
]
