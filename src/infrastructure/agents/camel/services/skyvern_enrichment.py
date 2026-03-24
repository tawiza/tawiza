"""Skyvern-based web enrichment service.

Uses OpenManus/Playwright for robust web automation and data extraction.
Falls back to simple HTTP if Playwright is not available.
"""

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus, urlparse

from loguru import logger


@dataclass
class EnrichmentResult:
    """Result of enriching a single company."""

    siret: str
    nom: str
    url_found: str | None = None
    url_source: str = "search"

    # Extracted data
    description: str | None = None
    services: list[str] = field(default_factory=list)
    clients_references: list[str] = field(default_factory=list)
    team_members: list[dict[str, str]] = field(default_factory=list)
    contact: dict[str, str] = field(default_factory=dict)
    social_media: dict[str, str] = field(default_factory=dict)
    technologies: list[str] = field(default_factory=list)

    # Metadata
    enriched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    enrichment_quality: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "siret": self.siret,
            "nom": self.nom,
            "url_found": self.url_found,
            "url_source": self.url_source,
            "description": self.description,
            "services": self.services,
            "clients_references": self.clients_references,
            "team_members": self.team_members,
            "contact": self.contact,
            "social_media": self.social_media,
            "technologies": self.technologies,
            "enriched_at": self.enriched_at,
            "enrichment_quality": self.enrichment_quality,
            "errors": self.errors,
        }


class SkyvernEnrichmentService:
    """Enrichment service using Skyvern/OpenManus for robust web scraping."""

    # Sites to search for company info
    SEARCH_SOURCES = [
        "pappers.fr",
        "societe.com",
        "verif.com",
    ]

    # Domains to exclude from company website detection
    EXCLUDED_DOMAINS = [
        "societe.com",
        "pappers.fr",
        "infogreffe.fr",
        "verif.com",
        "manageo.fr",
        "linkedin.com",
        "facebook.com",
        "twitter.com",
        "youtube.com",
        "wikipedia.org",
        "pagesjaunes.fr",
        "google.com",
        "bing.com",
        "duckduckgo.com",
    ]

    def __init__(
        self,
        max_concurrent: int = 2,
        timeout_per_site: int = 30,
        use_playwright: bool = True,
    ):
        self.max_concurrent = max_concurrent
        self.timeout_per_site = timeout_per_site
        self.use_playwright = use_playwright
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._browser_agent = None

    async def _get_browser_agent(self):
        """Get or create browser agent (lazy initialization)."""
        if self._browser_agent is None and self.use_playwright:
            try:
                from src.infrastructure.agents.skyvern.skyvern_adapter import SkyvernAdapter

                self._browser_agent = SkyvernAdapter(headless=True)
                logger.info("Initialized Skyvern browser agent")
            except Exception as e:
                logger.warning(f"Could not initialize Skyvern: {e}, falling back to HTTP")
                self.use_playwright = False
        return self._browser_agent

    async def find_company_website(self, company_name: str, city: str = "") -> str | None:
        """Find company website using multiple sources."""

        # Strategy 1: Try to guess URL from company name
        guessed_url = await self._guess_url(company_name)
        if guessed_url:
            return guessed_url

        # Strategy 2: Search on Pappers (has official website links)
        pappers_url = await self._search_pappers(company_name, city)
        if pappers_url:
            return pappers_url

        # Strategy 3: DuckDuckGo search
        ddg_url = await self._search_duckduckgo(company_name, city)
        if ddg_url:
            return ddg_url

        return None

    async def _guess_url(self, company_name: str) -> str | None:
        """Try to guess company URL from name and verify it exists."""
        import httpx

        # Clean company name
        name = company_name.lower()

        # Remove common suffixes
        for suffix in [" sas", " sarl", " sa", " eurl", " group", " france", " services"]:
            name = name.replace(suffix, "")

        # Remove special characters
        name = re.sub(r"[^a-z0-9\s]", "", name)
        name = name.strip()

        # Generate possible domains
        domains = []

        # Single word or join words
        words = name.split()
        if len(words) == 1:
            domains.append(f"{words[0]}.fr")
            domains.append(f"{words[0]}.com")
        else:
            # Try different combinations
            joined = "".join(words)
            hyphenated = "-".join(words)
            first_letters = "".join(w[0] for w in words if w)

            domains.extend(
                [
                    f"{joined}.fr",
                    f"{joined}.com",
                    f"{hyphenated}.fr",
                    f"{words[0]}.fr",
                ]
            )

            # Known company patterns
            if len(first_letters) >= 3:
                domains.append(f"{first_letters}.fr")

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
            for domain in domains[:4]:  # Test max 4 domains
                try:
                    url = f"https://www.{domain}"
                    response = await client.head(url, follow_redirects=True)
                    if response.status_code < 400:
                        logger.info(f"Found website for {company_name}: {url}")
                        return url
                except Exception as e:
                    logger.debug(f"Failed to check domain {domain}: {e}")

        return None

    async def _search_pappers(self, company_name: str, city: str) -> str | None:
        """Search Pappers for company website."""
        try:
            import httpx

            search_url = f"https://www.pappers.fr/recherche?q={quote_plus(company_name)}"

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                response = await client.get(search_url, follow_redirects=True)

                if response.status_code == 200:
                    # Parse for website links
                    text = response.text

                    # Look for website patterns in Pappers results
                    # Pappers shows company website in search results
                    website_pattern = r'href="(https?://(?:www\.)?[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}(?:/[^"]*)?)"'
                    matches = re.findall(website_pattern, text)

                    for url in matches:
                        domain = urlparse(url).netloc.lower()
                        if not any(excl in domain for excl in self.EXCLUDED_DOMAINS):
                            # Check if company name is in domain
                            name_parts = company_name.lower().split()
                            if any(part in domain for part in name_parts if len(part) > 3):
                                return url

            return None

        except Exception as e:
            logger.debug(f"Pappers search failed: {e}")
            return None

    async def _search_duckduckgo(self, company_name: str, city: str) -> str | None:
        """Search DuckDuckGo for company website."""
        try:
            import httpx

            query = f'"{company_name}"'
            if city:
                query += f" {city}"
            query += " site officiel"

            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                response = await client.get(search_url, follow_redirects=True)

                if response.status_code == 200:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(response.text, "html.parser")

                    for result in soup.find_all("a", class_="result__a")[:5]:
                        raw_url = result.get("href", "")

                        # Extract real URL from DuckDuckGo redirect
                        url = self._extract_ddg_url(raw_url)

                        if url:
                            domain = urlparse(url).netloc.lower()
                            if not any(excl in domain for excl in self.EXCLUDED_DOMAINS):
                                return url

            return None

        except Exception as e:
            logger.debug(f"DuckDuckGo search failed: {e}")
            return None

    def _extract_ddg_url(self, ddg_url: str) -> str | None:
        """Extract real URL from DuckDuckGo redirect."""
        from urllib.parse import parse_qs, unquote

        try:
            if ddg_url.startswith("//"):
                ddg_url = "https:" + ddg_url

            parsed = urlparse(ddg_url)

            if "duckduckgo.com" in parsed.netloc and "/l/" in parsed.path:
                params = parse_qs(parsed.query)
                if "uddg" in params:
                    return unquote(params["uddg"][0])

            if ddg_url.startswith("http"):
                return ddg_url

            return None
        except Exception:
            return None

    async def extract_company_data(self, url: str, company_name: str) -> dict[str, Any]:
        """Extract data from company website using Playwright/Skyvern."""
        data = {
            "description": None,
            "services": [],
            "contact": {},
            "social_media": {},
            "technologies": [],
        }

        try:
            agent = await self._get_browser_agent()

            if agent:
                # Use Skyvern/Playwright for extraction
                result = await agent.execute_task(
                    {
                        "url": url,
                        "action": "extract",
                        "data": {
                            "target": f"Extract company description, services, and contact info for {company_name}"
                        },
                    }
                )

                if result.get("status") == "completed":
                    extracted = result.get("result", {}).get("extracted_data", {})
                    if extracted:
                        data.update(extracted)
            else:
                # Fallback to simple HTTP extraction
                data = await self._extract_with_http(url, company_name)

        except Exception as e:
            logger.warning(f"Extraction failed for {url}: {e}")

        return data

    async def _extract_with_http(self, url: str, company_name: str) -> dict[str, Any]:
        """Enhanced HTTP-based extraction with multiple strategies."""
        import json as json_module

        import httpx

        data = {
            "description": None,
            "services": [],
            "contact": {},
            "social_media": {},
            "technologies": [],
        }

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                response = await client.get(url, follow_redirects=True)

                if response.status_code == 200:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(response.text, "html.parser")

                    # Strategy 1: JSON-LD structured data
                    for script in soup.find_all("script", type="application/ld+json"):
                        try:
                            ld_data = json_module.loads(script.string or "")
                            if isinstance(ld_data, list):
                                ld_data = ld_data[0] if ld_data else {}

                            if ld_data.get("@type") in [
                                "Organization",
                                "LocalBusiness",
                                "Corporation",
                            ]:
                                if ld_data.get("description") and not data["description"]:
                                    data["description"] = ld_data["description"][:500]
                                if ld_data.get("telephone"):
                                    data["contact"]["phone"] = ld_data["telephone"]
                                if ld_data.get("email"):
                                    data["contact"]["email"] = ld_data["email"]
                                if ld_data.get("address"):
                                    addr = ld_data["address"]
                                    if isinstance(addr, dict):
                                        data["contact"]["address"] = addr.get("streetAddress", "")
                        except Exception as e:
                            logger.debug(f"Failed to parse JSON-LD data: {e}")

                    # Strategy 2: Meta tags (og:description, meta description)
                    if not data["description"]:
                        og_desc = soup.find("meta", property="og:description")
                        if og_desc and og_desc.get("content"):
                            data["description"] = og_desc["content"][:500]

                    if not data["description"]:
                        meta_desc = soup.find("meta", {"name": "description"})
                        if meta_desc and meta_desc.get("content"):
                            data["description"] = meta_desc["content"][:500]

                    # Strategy 3: Title as fallback
                    if not data["description"]:
                        title = soup.find("title")
                        if title:
                            title_text = title.get_text(strip=True)
                            # Only use if it's descriptive enough
                            if len(title_text) > 20:
                                data["description"] = title_text[:200]

                    # Remove noise for text extraction
                    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                        tag.decompose()

                    text = soup.get_text(separator="\n", strip=True)

                    # Strategy 4: Paragraph extraction (if no description yet)
                    if not data["description"]:
                        for p in soup.find_all("p")[:10]:
                            p_text = p.get_text(strip=True)
                            # Must be substantial and not navigation
                            if len(p_text) > 80 and not any(
                                x in p_text.lower()
                                for x in ["cookie", "cliquez", "accepter", "connexion"]
                            ):
                                data["description"] = p_text[:500]
                                break

                    # Strategy 5: Extract services from headings and lists
                    services = []

                    # Look for services/solutions/offerings sections
                    service_keywords = [
                        "service",
                        "solution",
                        "offre",
                        "expertise",
                        "métier",
                        "activité",
                    ]
                    for h in soup.find_all(["h2", "h3", "h4"]):
                        h_text = h.get_text(strip=True).lower()
                        if any(kw in h_text for kw in service_keywords):
                            # Get next sibling list or paragraphs
                            sibling = h.find_next_sibling()
                            if sibling and sibling.name == "ul":
                                for li in sibling.find_all("li")[:5]:
                                    service = li.get_text(strip=True)
                                    if 3 < len(service) < 100:
                                        services.append(service)

                    # Also look for nav items that might be services
                    nav_services = soup.find_all(
                        "a", href=re.compile(r"/services?/|/solutions?/|/offres?/")
                    )
                    for a in nav_services[:5]:
                        service_name = a.get_text(strip=True)
                        if 3 < len(service_name) < 50 and service_name not in services:
                            services.append(service_name)

                    data["services"] = services[:10]

                    # Strategy 6: Contact extraction
                    if "email" not in data["contact"]:
                        # Look for email in mailto links first
                        mailto = soup.find("a", href=re.compile(r"^mailto:"))
                        if mailto:
                            email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", mailto["href"])
                            if email_match:
                                data["contact"]["email"] = email_match.group()
                        else:
                            # Fallback to regex on text
                            email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
                            if email:
                                data["contact"]["email"] = email.group()

                    if "phone" not in data["contact"]:
                        # French phone numbers
                        phone = re.search(r"(?:\+33|0)\s*[1-9](?:[\s.-]*\d{2}){4}", text)
                        if phone:
                            data["contact"]["phone"] = phone.group()

                    # Strategy 7: Social media links
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if "linkedin.com/company" in href:
                            data["social_media"]["linkedin"] = href
                        elif "twitter.com/" in href or "x.com/" in href:
                            data["social_media"]["twitter"] = href
                        elif "facebook.com/" in href and "/sharer" not in href:
                            data["social_media"]["facebook"] = href
                        elif "instagram.com/" in href:
                            data["social_media"]["instagram"] = href

                    # Strategy 8: Technologies detection
                    html_text = response.text.lower()
                    tech_signatures = {
                        "wordpress": ["wp-content", "wordpress"],
                        "react": ["react", "_reactroot"],
                        "vue": ["vue.js", "vuejs"],
                        "angular": ["ng-", "angular"],
                        "shopify": ["shopify", "cdn.shopify"],
                        "wix": ["wix.com", "wixstatic"],
                        "hubspot": ["hubspot", "hs-scripts"],
                        "salesforce": ["salesforce", "pardot"],
                    }
                    for tech, signatures in tech_signatures.items():
                        if any(sig in html_text for sig in signatures):
                            data["technologies"].append(tech)

        except Exception as e:
            logger.debug(f"HTTP extraction failed: {e}")

        return data

    async def enrich_company(self, enterprise: dict[str, Any]) -> EnrichmentResult:
        """Enrich a single company with web data."""
        async with self._semaphore:
            siret = enterprise.get("siret", "")
            nom = enterprise.get("nom", "")
            city = enterprise.get("adresse", {}).get("commune", "")

            result = EnrichmentResult(siret=siret, nom=nom)

            try:
                # Find website
                url = await asyncio.wait_for(
                    self.find_company_website(nom, city), timeout=self.timeout_per_site
                )

                if url:
                    result.url_found = url
                    result.url_source = "search"

                    # Extract data
                    data = await asyncio.wait_for(
                        self.extract_company_data(url, nom), timeout=self.timeout_per_site
                    )

                    result.description = data.get("description")
                    result.services = data.get("services", [])
                    result.contact = data.get("contact", {})
                    result.social_media = data.get("social_media", {})
                    result.technologies = data.get("technologies", [])

                    # Quality score (0-1, weighted by data value)
                    score = 0.0
                    max_score = 0.0

                    # Description is most important (30%)
                    max_score += 0.30
                    if result.description and len(result.description) > 50:
                        score += 0.30
                    elif result.description:
                        score += 0.15

                    # Services show business offerings (20%)
                    max_score += 0.20
                    if result.services and len(result.services) >= 3:
                        score += 0.20
                    elif result.services:
                        score += 0.10

                    # Contact info enables outreach (25%)
                    max_score += 0.25
                    if result.contact.get("email"):
                        score += 0.15
                    if result.contact.get("phone"):
                        score += 0.10

                    # Social media shows web presence (15%)
                    max_score += 0.15
                    social_count = len(result.social_media)
                    if social_count >= 2:
                        score += 0.15
                    elif social_count >= 1:
                        score += 0.08

                    # Technologies are bonus info (10%)
                    max_score += 0.10
                    if result.technologies:
                        score += 0.10

                    result.enrichment_quality = score

                else:
                    result.errors.append("No website found")

            except TimeoutError:
                result.errors.append("Timeout")
            except Exception as e:
                result.errors.append(str(e))

            return result

    async def enrich_batch(
        self,
        enterprises: list[dict[str, Any]],
        progress_callback: Callable | None = None,
    ) -> list[EnrichmentResult]:
        """Enrich a batch of companies."""
        results = []

        for i, enterprise in enumerate(enterprises):
            result = await self.enrich_company(enterprise)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, len(enterprises))

            # Small delay to be polite
            await asyncio.sleep(0.3)

        return results

    async def close(self):
        """Clean up resources."""
        if self._browser_agent:
            try:
                await self._browser_agent._close_browser()
            except Exception as e:
                logger.debug(f"Failed to close browser agent: {e}")
