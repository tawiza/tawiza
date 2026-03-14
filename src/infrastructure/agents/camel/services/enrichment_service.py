"""Web enrichment service for company data.

Crawls company websites to extract comprehensive business intelligence data.
"""

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from loguru import logger


@dataclass
class EnrichmentResult:
    """Result of enriching a single company."""

    siret: str
    nom: str
    url_found: str | None = None
    url_source: str = "search"  # search, sirene, manual

    # Extracted data
    description: str | None = None
    services: list[str] = field(default_factory=list)
    clients_references: list[str] = field(default_factory=list)
    team_members: list[dict[str, str]] = field(default_factory=list)
    contact: dict[str, str] = field(default_factory=dict)
    social_media: dict[str, str] = field(default_factory=dict)
    news: list[dict[str, str]] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)

    # Metadata
    enriched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    enrichment_quality: float = 0.0  # 0-1 score
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
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
            "news": self.news,
            "technologies": self.technologies,
            "certifications": self.certifications,
            "enriched_at": self.enriched_at,
            "enrichment_quality": self.enrichment_quality,
            "errors": self.errors,
        }

    def to_jsonl(self) -> str:
        """Convert to JSONL format for annotation/fine-tuning."""
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False)


class EnrichmentService:
    """Service for enriching company data from the web."""

    def __init__(
        self,
        max_concurrent: int = 3,
        timeout_per_site: int = 30,
        headless: bool = True,
    ):
        """Initialize the enrichment service.

        Args:
            max_concurrent: Max concurrent browser sessions
            timeout_per_site: Timeout per website in seconds
            headless: Run browser in headless mode
        """
        self.max_concurrent = max_concurrent
        self.timeout_per_site = timeout_per_site
        self.headless = headless
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def find_company_website(self, company_name: str, city: str = "") -> str | None:
        """Find a company's website using web search.

        Args:
            company_name: Name of the company
            city: Optional city for disambiguation

        Returns:
            URL of the company website or None
        """
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)

        # Build search query
        query = f'"{company_name}"'
        if city:
            query += f" {city}"
        query += " site officiel"

        try:
            result = await registry.execute(
                "browser.search",
                {
                    "query": query,
                },
            )

            results = result.get("results", [])
            if results:
                # Filter out aggregator sites
                excluded_domains = [
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
                ]

                for r in results:
                    url = r.get("url", "")
                    domain = urlparse(url).netloc.lower()

                    # Skip excluded domains
                    if any(excl in domain for excl in excluded_domains):
                        continue

                    # Prefer .fr domains for French companies
                    if ".fr" in domain or company_name.lower().replace(" ", "") in domain:
                        return url

                # Fallback to first non-excluded result
                for r in results:
                    url = r.get("url", "")
                    domain = urlparse(url).netloc.lower()
                    if not any(excl in domain for excl in excluded_domains):
                        return url

            return None

        except Exception as e:
            logger.warning(f"Failed to search for {company_name}: {e}")
            return None

    async def extract_company_data(self, url: str, company_name: str) -> dict[str, Any]:
        """Extract comprehensive data from a company website.

        Args:
            url: URL of the company website
            company_name: Name of the company (for context)

        Returns:
            Dictionary with extracted data
        """
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)

        data = {
            "description": None,
            "services": [],
            "clients_references": [],
            "team_members": [],
            "contact": {},
            "social_media": {},
            "news": [],
            "technologies": [],
            "certifications": [],
        }

        try:
            # Extract main page content using browser.navigate
            result = await registry.execute(
                "browser.navigate",
                {
                    "url": url,
                },
            )

            if not result.get("success"):
                logger.warning(f"Failed to navigate to {url}: {result.get('error')}")
                return data

            page_text = result.get("text_content", "")
            result.get("title", "")
            links = result.get("links", [])

            # Extract description from first paragraphs
            if page_text:
                # Take first 500 chars as description
                data["description"] = page_text[:500].strip()

            # Extract social media links
            social_patterns = {
                "linkedin": r"linkedin\.com/company/[\w-]+",
                "twitter": r"twitter\.com/[\w]+",
                "facebook": r"facebook\.com/[\w.]+",
                "youtube": r"youtube\.com/(?:channel|c)/[\w-]+",
            }

            for platform, pattern in social_patterns.items():
                for link in links:
                    href = link.get("url", "") or link.get("href", "")
                    match = re.search(pattern, href, re.I)
                    if match:
                        data["social_media"][platform] = f"https://{match.group()}"
                        break

            # Extract contact info from text
            email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", page_text)
            if email_match:
                data["contact"]["email"] = email_match.group()

            phone_match = re.search(r"(?:\+33|0)\s*[1-9](?:[\s.-]*\d{2}){4}", page_text)
            if phone_match:
                data["contact"]["phone"] = phone_match.group()

            # Try to find services/about page
            service_keywords = ["services", "solutions", "expertise", "offres", "about", "a-propos"]
            for link in links[:20]:
                href = (link.get("url", "") or link.get("href", "")).lower()
                text = link.get("text", "").lower()

                if any(kw in href or kw in text for kw in service_keywords):
                    try:
                        service_url = (
                            href
                            if href.startswith("http")
                            else f"{url.rstrip('/')}/{href.lstrip('/')}"
                        )
                        service_result = await registry.execute(
                            "browser.navigate",
                            {
                                "url": service_url,
                            },
                        )
                        service_text = service_result.get("text_content", "")

                        # Extract bullet points as services
                        lines = service_text.split("\n")
                        for line in lines:
                            line = line.strip()
                            if len(line) > 10 and len(line) < 100:
                                if line.startswith(("-", "•", "✓", "→")):
                                    data["services"].append(line.lstrip("-•✓→ "))
                                elif any(
                                    kw in line.lower()
                                    for kw in [
                                        "conseil",
                                        "développement",
                                        "audit",
                                        "formation",
                                        "accompagnement",
                                    ]
                                ):
                                    data["services"].append(line)

                        # Limit to 10 services
                        data["services"] = data["services"][:10]
                        break

                    except Exception as e:
                        logger.debug(f"Failed to extract services from {service_url}: {e}")

            # Try to find team/about page for team members
            team_keywords = ["equipe", "team", "qui-sommes-nous", "about"]
            for link in links[:20]:
                href = (link.get("url", "") or link.get("href", "")).lower()
                text = link.get("text", "").lower()

                if any(kw in href or kw in text for kw in team_keywords):
                    try:
                        team_url = (
                            href
                            if href.startswith("http")
                            else f"{url.rstrip('/')}/{href.lstrip('/')}"
                        )
                        team_result = await registry.execute(
                            "browser.navigate",
                            {
                                "url": team_url,
                            },
                        )
                        team_text = team_result.get("text_content", "")

                        # Simple pattern for names with titles
                        name_patterns = [
                            r"([\w\s]+)\s*[-–]\s*(CEO|CTO|Directeur|Fondateur|Manager|Président|DG)",
                            r"(CEO|CTO|Directeur|Fondateur|Manager|Président|DG)\s*[-–:]\s*([\w\s]+)",
                        ]

                        for pattern in name_patterns:
                            matches = re.findall(pattern, team_text, re.I)
                            for match in matches[:5]:
                                if isinstance(match, tuple):
                                    name = (
                                        match[0].strip()
                                        if "CEO" not in match[0]
                                        else match[1].strip()
                                    )
                                    role = (
                                        match[1].strip()
                                        if "CEO" not in match[0]
                                        else match[0].strip()
                                    )
                                    if len(name) < 50 and len(role) < 50:
                                        data["team_members"].append({"name": name, "role": role})
                        break

                    except Exception as e:
                        logger.debug(f"Failed to extract team members from {team_url}: {e}")

            # Try to find clients/references
            ref_keywords = ["clients", "references", "partenaires", "ils-nous-font-confiance"]
            for link in links[:20]:
                href = (link.get("url", "") or link.get("href", "")).lower()
                text = link.get("text", "").lower()

                if any(kw in href or kw in text for kw in ref_keywords):
                    try:
                        ref_url = (
                            href
                            if href.startswith("http")
                            else f"{url.rstrip('/')}/{href.lstrip('/')}"
                        )
                        ref_result = await registry.execute(
                            "browser.navigate",
                            {
                                "url": ref_url,
                            },
                        )
                        ref_text = ref_result.get("text_content", "")

                        # Look for company names (capitalized words)
                        words = ref_text.split()
                        for _i, word in enumerate(words):
                            if word.isupper() and len(word) > 2 and len(word) < 30:
                                data["clients_references"].append(word)

                        data["clients_references"] = list(set(data["clients_references"]))[:10]
                        break

                    except Exception as e:
                        logger.debug(f"Failed to extract references from {ref_url}: {e}")

            return data

        except Exception as e:
            logger.warning(f"Failed to extract data from {url}: {e}")
            return data

    async def enrich_company(self, enterprise: dict[str, Any]) -> EnrichmentResult:
        """Enrich a single company with web data.

        Args:
            enterprise: Company data from Sirene

        Returns:
            EnrichmentResult with extracted data
        """
        async with self._semaphore:
            siret = enterprise.get("siret", "")
            nom = enterprise.get("nom", "")
            city = enterprise.get("adresse", {}).get("commune", "")

            result = EnrichmentResult(siret=siret, nom=nom)

            try:
                # Try to find company website
                url = await asyncio.wait_for(
                    self.find_company_website(nom, city), timeout=self.timeout_per_site
                )

                if url:
                    result.url_found = url
                    result.url_source = "search"

                    # Extract data from website
                    data = await asyncio.wait_for(
                        self.extract_company_data(url, nom), timeout=self.timeout_per_site * 2
                    )

                    result.description = data.get("description")
                    result.services = data.get("services", [])
                    result.clients_references = data.get("clients_references", [])
                    result.team_members = data.get("team_members", [])
                    result.contact = data.get("contact", {})
                    result.social_media = data.get("social_media", {})
                    result.news = data.get("news", [])
                    result.technologies = data.get("technologies", [])
                    result.certifications = data.get("certifications", [])

                    # Calculate quality score
                    score = 0
                    if result.description:
                        score += 0.2
                    if result.services:
                        score += 0.2
                    if result.contact:
                        score += 0.15
                    if result.social_media:
                        score += 0.15
                    if result.clients_references:
                        score += 0.15
                    if result.team_members:
                        score += 0.15
                    result.enrichment_quality = score

                else:
                    result.errors.append("No website found")

            except TimeoutError:
                result.errors.append("Timeout during enrichment")
            except Exception as e:
                result.errors.append(str(e))
                logger.warning(f"Enrichment failed for {nom}: {e}")

            return result

    async def enrich_batch(
        self,
        enterprises: list[dict[str, Any]],
        progress_callback: Callable | None = None,
    ) -> list[EnrichmentResult]:
        """Enrich a batch of companies.

        Args:
            enterprises: List of company data from Sirene
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of EnrichmentResults
        """
        results = []
        total = len(enterprises)

        for i, enterprise in enumerate(enterprises):
            result = await self.enrich_company(enterprise)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, total)

            # Small delay between requests to be polite
            await asyncio.sleep(0.5)

        return results


async def enrich_enterprises(
    enterprises: list[dict[str, Any]],
    max_concurrent: int = 3,
    progress_callback: Callable | None = None,
) -> list[EnrichmentResult]:
    """Convenience function to enrich a list of enterprises.

    Args:
        enterprises: List of company data from Sirene
        max_concurrent: Max concurrent browser sessions
        progress_callback: Optional callback for progress updates

    Returns:
        List of EnrichmentResults
    """
    service = EnrichmentService(max_concurrent=max_concurrent)
    return await service.enrich_batch(enterprises, progress_callback)
