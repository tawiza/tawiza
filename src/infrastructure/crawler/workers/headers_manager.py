"""HTTP Headers Manager for stealth crawling.

Provides realistic browser headers using fake-useragent library.
Includes:
- User-Agent rotation
- Complete browser header sets
- Anti-fingerprinting headers
"""

import random
from dataclasses import dataclass, field

from loguru import logger

# Lazy imports for optional dependencies
_fake_ua = None
_fake_header = None


def _get_fake_ua():
    """Lazy load fake_useragent."""
    global _fake_ua
    if _fake_ua is None:
        try:
            from fake_useragent import UserAgent
            _fake_ua = UserAgent(
                browsers=["chrome", "firefox", "edge"],
                min_percentage=5.0,
            )
        except ImportError:
            logger.warning("fake-useragent not installed. Run: pip install fake-useragent")
    return _fake_ua


def _get_fake_header():
    """Lazy load fake_http_header."""
    global _fake_header
    if _fake_header is None:
        try:
            from fake_http_header import FakeHttpHeader
            _fake_header = FakeHttpHeader
        except ImportError:
            logger.warning("fake-http-header not installed. Run: pip install fake-http-header")
    return _fake_header


@dataclass
class HeadersConfig:
    """Configuration for headers generation."""

    # Browsers to emulate
    browsers: list[str] = field(default_factory=lambda: ["chrome", "firefox", "edge"])

    # Languages to use
    languages: list[str] = field(default_factory=lambda: ["fr-FR", "en-US", "en"])

    # Accept header variations
    accept_types: list[str] = field(default_factory=lambda: [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    ])

    # Include DNT header
    include_dnt: bool = True

    # Include Upgrade-Insecure-Requests header
    include_upgrade_insecure: bool = True


# Fallback user agents if fake-useragent fails
FALLBACK_USER_AGENTS = [
    # Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Sec-CH-UA variations for Chrome
SEC_CH_UA_VARIANTS = [
    '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    '"Not_A Brand";v="8", "Chromium";v="119", "Google Chrome";v="119"',
    '"Chromium";v="120", "Not-A.Brand";v="24", "Google Chrome";v="120"',
]

# Common referers for French territorial sites
FRENCH_REFERERS = [
    "https://www.google.fr/",
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    None,  # Sometimes no referer is more natural
]


class HeadersManager:
    """Manages HTTP headers for stealth crawling.

    Generates realistic browser headers to avoid detection.
    Supports rotation and per-domain customization.
    """

    def __init__(self, config: HeadersConfig | None = None) -> None:
        """Initialize headers manager.

        Args:
            config: Headers generation configuration
        """
        self.config = config or HeadersConfig()
        self._ua = _get_fake_ua()
        self._header_generator = _get_fake_header()

    def get_user_agent(self, browser: str | None = None) -> str:
        """Get a random user agent string.

        Args:
            browser: Specific browser type (chrome, firefox, edge) or None for random

        Returns:
            User agent string
        """
        if self._ua:
            try:
                if browser:
                    return getattr(self._ua, browser, self._ua.random)
                return self._ua.random
            except Exception:
                pass

        return random.choice(FALLBACK_USER_AGENTS)

    def get_headers(
        self,
        domain: str | None = None,
        include_referer: bool = True,
        custom_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Get a complete set of realistic browser headers.

        Args:
            domain: Target domain for domain-specific headers
            include_referer: Whether to include a referer header
            custom_headers: Additional headers to merge

        Returns:
            Dictionary of HTTP headers
        """
        # Try to use fake_http_header if available
        if self._header_generator and domain:
            try:
                generator = self._header_generator(domain=domain)
                headers = generator.as_header_dict()
                if custom_headers:
                    headers.update(custom_headers)
                return headers
            except Exception as e:
                logger.debug(f"fake_http_header failed, using fallback: {e}")

        # Build headers manually
        ua = self.get_user_agent()
        is_chrome = "Chrome" in ua and "Edg" not in ua

        headers = {
            "User-Agent": ua,
            "Accept": random.choice(self.config.accept_types),
            "Accept-Language": ",".join(self.config.languages) + ";q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        # Chrome-specific headers
        if is_chrome:
            headers.update({
                "Sec-Ch-Ua": random.choice(SEC_CH_UA_VARIANTS),
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"' if "Windows" in ua else '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none" if not include_referer else "cross-site",
                "Sec-Fetch-User": "?1",
            })

        # Optional headers
        if self.config.include_dnt:
            headers["DNT"] = "1"

        if self.config.include_upgrade_insecure:
            headers["Upgrade-Insecure-Requests"] = "1"

        # Referer
        if include_referer:
            referer = random.choice(FRENCH_REFERERS)
            if referer:
                headers["Referer"] = referer

        # Merge custom headers
        if custom_headers:
            headers.update(custom_headers)

        return headers

    def get_api_headers(
        self,
        api_key: str | None = None,
        content_type: str = "application/json",
    ) -> dict[str, str]:
        """Get headers suitable for API requests.

        Args:
            api_key: Optional API key
            content_type: Content type for request body

        Returns:
            API request headers
        """
        headers = {
            "User-Agent": f"Tawiza-TerritorialAnalysis/2.0 ({self.get_user_agent()})",
            "Accept": "application/json",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Content-Type": content_type,
        }

        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        return headers

    def get_headers_for_site(self, site: str) -> dict[str, str]:
        """Get optimized headers for specific French data sites.

        Args:
            site: Site identifier (sirene, bodacc, insee, etc.)

        Returns:
            Optimized headers for the site
        """
        base_headers = self.get_headers(include_referer=False)

        # Site-specific customizations
        site_configs = {
            "sirene": {
                "Accept": "application/json",
                "Referer": "https://api.insee.fr/",
            },
            "bodacc": {
                "Accept": "application/json, text/html",
                "Referer": "https://www.bodacc.fr/",
            },
            "insee": {
                "Accept": "application/json",
                "Referer": "https://api.insee.fr/",
            },
            "boamp": {
                "Accept": "application/json, application/xml",
                "Referer": "https://www.boamp.fr/",
            },
            "data_gouv": {
                "Accept": "application/json",
                "Referer": "https://www.data.gouv.fr/",
            },
            "ofgl": {
                "Accept": "application/json",
                "Referer": "https://data.ofgl.fr/",
            },
            "france_travail": {
                "Accept": "application/json",
                "Referer": "https://francetravail.io/",
            },
        }

        if site.lower() in site_configs:
            base_headers.update(site_configs[site.lower()])

        return base_headers


# Singleton instance
_global_headers_manager: HeadersManager | None = None


def get_headers_manager() -> HeadersManager:
    """Get or create the global headers manager instance."""
    global _global_headers_manager
    if _global_headers_manager is None:
        _global_headers_manager = HeadersManager()
    return _global_headers_manager


def get_random_headers(domain: str | None = None) -> dict[str, str]:
    """Convenience function to get random headers.

    Args:
        domain: Optional target domain

    Returns:
        Dictionary of HTTP headers
    """
    return get_headers_manager().get_headers(domain)


def get_random_user_agent() -> str:
    """Convenience function to get a random user agent.

    Returns:
        User agent string
    """
    return get_headers_manager().get_user_agent()
