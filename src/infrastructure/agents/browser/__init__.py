"""Browser automation agents for TAJINE.

Three stealth browser backends available:
- UnifiedBrowserAgent: Playwright-based, good for most sites, CAPTCHA solving
- NodriverBrowserAgent: Chrome/nodriver stealth (CDP-based, no WebDriver fingerprint)
- CamoufoxBrowserAgent: Firefox/Camoufox stealth (C++ level fingerprint spoofing)
- StealthBrowserPool: Automatic selection between nodriver and Camoufox

Recommended usage:
- StealthBrowserPool for automatic browser selection with fallback
- NodriverBrowserAgent for Chrome-specific needs
- CamoufoxBrowserAgent for Firefox-specific needs (French gov sites)
"""

from .camoufox_agent import (
    CAMOUFOX_AVAILABLE,
    FRENCH_GEOLOCATIONS,
    CamoufoxAction,
    CamoufoxBrowserAgent,
    CamoufoxResult,
    FingerprintConfig,
    stealth_fetch_firefox,
)
from .nodriver_agent import (
    NODRIVER_AVAILABLE,
    NodriverBrowserAgent,
    StealthAction,
    StealthActionRequest,
    StealthResult,
    stealth_scrape,
)
from .stealth_pool import (
    KNOWN_DOMAIN_PREFERENCES,
    BrowserType,
    DomainPreference,
    StealthBrowserPool,
    StealthFetchResult,
    stealth_fetch,
)
from .unified_browser_agent import (
    ActionResult,
    BrowserAction,
    BrowserActionType,
    CaptchaSolver,
    UnifiedBrowserAgent,
)

__all__ = [
    # Playwright-based (default)
    "UnifiedBrowserAgent",
    "BrowserAction",
    "BrowserActionType",
    "ActionResult",
    "CaptchaSolver",
    # nodriver-based (Chrome stealth)
    "NodriverBrowserAgent",
    "StealthAction",
    "StealthActionRequest",
    "StealthResult",
    "stealth_scrape",
    "NODRIVER_AVAILABLE",
    # Camoufox-based (Firefox stealth)
    "CamoufoxBrowserAgent",
    "CamoufoxAction",
    "CamoufoxResult",
    "FingerprintConfig",
    "stealth_fetch_firefox",
    "CAMOUFOX_AVAILABLE",
    "FRENCH_GEOLOCATIONS",
    # Unified stealth pool
    "StealthBrowserPool",
    "StealthFetchResult",
    "BrowserType",
    "DomainPreference",
    "stealth_fetch",
    "KNOWN_DOMAIN_PREFERENCES",
]
