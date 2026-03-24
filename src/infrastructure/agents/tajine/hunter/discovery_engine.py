"""Discovery Engine using ScrapeGraphAI for automatic pattern learning.

ScrapeGraphAI enables:
- LLM-powered web scraping with automatic schema inference
- Pattern learning from seed URLs
- Intelligent data extraction without manual selectors

This engine discovers new data sources and extraction patterns
for TAJINE's territorial intelligence pipeline.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

# Optional import with fallback
try:
    from scrapegraphai.graphs import SmartScraperGraph

    SCRAPEGRAPHAI_AVAILABLE = True
except ImportError:
    SCRAPEGRAPHAI_AVAILABLE = False
    logger.warning("scrapegraphai not installed. Discovery engine limited.")


@dataclass
class DiscoveredPattern:
    """A discovered scraping pattern from a seed URL."""

    pattern_id: str
    source_url: str
    domain: str
    extraction_prompt: str
    sample_data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    last_validated: str | None = None
    uses: int = 0
    successes: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate pattern success rate."""
        return self.successes / self.uses if self.uses > 0 else 0.5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "pattern_id": self.pattern_id,
            "source_url": self.source_url,
            "domain": self.domain,
            "extraction_prompt": self.extraction_prompt,
            "sample_data": self.sample_data,
            "confidence": self.confidence,
            "last_validated": self.last_validated,
            "uses": self.uses,
            "successes": self.successes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiscoveredPattern:
        """Create from dictionary."""
        return cls(
            pattern_id=data["pattern_id"],
            source_url=data["source_url"],
            domain=data.get("domain", "general"),
            extraction_prompt=data["extraction_prompt"],
            sample_data=data.get("sample_data", {}),
            confidence=data.get("confidence", 0.5),
            last_validated=data.get("last_validated"),
            uses=data.get("uses", 0),
            successes=data.get("successes", 0),
        )


@dataclass
class DiscoveryResult:
    """Result of a discovery operation."""

    success: bool
    patterns: list[DiscoveredPattern] = field(default_factory=list)
    data: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0


class DiscoveryEngine:
    """LLM-powered discovery engine for finding and learning data patterns.

    Uses ScrapeGraphAI to:
    1. Discover data on new URLs with natural language prompts
    2. Learn extraction patterns that can be reused
    3. Validate and rank patterns by success rate
    """

    def __init__(
        self,
        llm_config: dict[str, Any] | None = None,
        patterns_dir: str | Path | None = None,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen3.5:27b",
    ):
        """Initialize discovery engine.

        Args:
            llm_config: ScrapeGraphAI LLM configuration
            patterns_dir: Directory to persist learned patterns
            ollama_url: Ollama API URL
            model: LLM model to use
        """
        self.ollama_url = ollama_url
        self.model = model

        # Build LLM config for ScrapeGraphAI
        self.llm_config = llm_config or {
            "llm": {
                "model": f"ollama/{model}",
                "temperature": 0.1,
                "base_url": ollama_url,
            }
        }

        # Pattern storage
        self.patterns_dir = Path(patterns_dir) if patterns_dir else None
        self.patterns: dict[str, DiscoveredPattern] = {}

        # Load existing patterns
        if self.patterns_dir and self.patterns_dir.exists():
            self._load_patterns()

    def _load_patterns(self) -> None:
        """Load patterns from disk."""
        patterns_file = self.patterns_dir / "patterns.json"
        if patterns_file.exists():
            try:
                data = json.loads(patterns_file.read_text())
                for p in data.get("patterns", []):
                    pattern = DiscoveredPattern.from_dict(p)
                    self.patterns[pattern.pattern_id] = pattern
                logger.info(f"Loaded {len(self.patterns)} discovery patterns")
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}")

    def _save_patterns(self) -> None:
        """Save patterns to disk."""
        if not self.patterns_dir:
            return

        self.patterns_dir.mkdir(parents=True, exist_ok=True)
        patterns_file = self.patterns_dir / "patterns.json"

        data = {
            "updated": datetime.now().isoformat(),
            "patterns": [p.to_dict() for p in self.patterns.values()],
        }

        patterns_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.debug(f"Saved {len(self.patterns)} patterns")

    def _generate_pattern_id(self, url: str, prompt: str) -> str:
        """Generate unique pattern ID from URL and prompt."""
        content = f"{url}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    async def discover(
        self,
        seed_url: str,
        query: str,
        domain: str = "entreprises",
    ) -> DiscoveryResult:
        """Discover data and patterns from a seed URL.

        Args:
            seed_url: URL to scrape
            query: Natural language query describing what to extract
            domain: Data domain (entreprises, emploi, immobilier, etc.)

        Returns:
            DiscoveryResult with extracted data and learned patterns
        """
        start_time = datetime.now()

        if not SCRAPEGRAPHAI_AVAILABLE:
            return DiscoveryResult(
                success=False,
                error="scrapegraphai not installed",
            )

        try:
            # Build extraction prompt for territorial data
            extraction_prompt = self._build_prompt(query, domain)

            # Run ScrapeGraphAI
            graph = SmartScraperGraph(
                prompt=extraction_prompt,
                source=seed_url,
                config=self.llm_config,
            )

            result = await asyncio.to_thread(graph.run)

            # Extract data
            data = self._normalize_result(result)

            # Learn pattern if successful
            patterns = []
            if data:
                pattern = self._create_pattern(
                    url=seed_url,
                    prompt=extraction_prompt,
                    domain=domain,
                    sample_data=data[0] if data else {},
                )
                self.patterns[pattern.pattern_id] = pattern
                patterns.append(pattern)
                self._save_patterns()

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return DiscoveryResult(
                success=True,
                patterns=patterns,
                data=data,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            logger.error(f"Discovery failed for {seed_url}: {e}")
            return DiscoveryResult(
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    def _build_prompt(self, query: str, domain: str) -> str:
        """Build extraction prompt optimized for territorial data."""
        domain_hints = {
            "entreprises": "Extract company data: SIREN/SIRET, name, address, NAF code, creation date, employee count, legal form",
            "emploi": "Extract job listings: title, company, location, contract type, salary range, required skills",
            "immobilier": "Extract property data: price, surface, location, type (apartment/house), rooms, construction year",
            "subventions": "Extract grant information: title, amount, eligibility criteria, deadline, funding organization",
            "general": "Extract all structured data relevant to the query",
        }

        hint = domain_hints.get(domain, domain_hints["general"])

        return f"""
{hint}

User Query: {query}

Return the data as a JSON list of objects. Each object should have clear field names.
Only extract factual data visible on the page. Do not invent or hallucinate data.
"""

    def _normalize_result(self, result: Any) -> list[dict[str, Any]]:
        """Normalize ScrapeGraphAI result to list of dicts."""
        if result is None:
            return []

        if isinstance(result, list):
            return [r for r in result if isinstance(r, dict)]

        if isinstance(result, dict):
            # Check if it's a wrapper with a data key
            if "data" in result and isinstance(result["data"], list):
                return result["data"]
            return [result]

        return []

    def _create_pattern(
        self,
        url: str,
        prompt: str,
        domain: str,
        sample_data: dict[str, Any],
    ) -> DiscoveredPattern:
        """Create a new discovery pattern."""
        pattern_id = self._generate_pattern_id(url, prompt)

        # Extract domain from URL
        from urllib.parse import urlparse

        urlparse(url)

        return DiscoveredPattern(
            pattern_id=pattern_id,
            source_url=url,
            domain=domain,
            extraction_prompt=prompt,
            sample_data=sample_data,
            confidence=0.7,  # Initial confidence
            last_validated=datetime.now().isoformat(),
            uses=1,
            successes=1,
        )

    async def apply_pattern(
        self,
        pattern_id: str,
        url: str,
    ) -> DiscoveryResult:
        """Apply a learned pattern to a new URL.

        Args:
            pattern_id: ID of pattern to apply
            url: URL to scrape

        Returns:
            DiscoveryResult with extracted data
        """
        if pattern_id not in self.patterns:
            return DiscoveryResult(
                success=False,
                error=f"Pattern not found: {pattern_id}",
            )

        pattern = self.patterns[pattern_id]
        start_time = datetime.now()

        try:
            if not SCRAPEGRAPHAI_AVAILABLE:
                return DiscoveryResult(
                    success=False,
                    error="scrapegraphai not installed",
                )

            # Reuse the learned prompt
            graph = SmartScraperGraph(
                prompt=pattern.extraction_prompt,
                source=url,
                config=self.llm_config,
            )

            result = await asyncio.to_thread(graph.run)
            data = self._normalize_result(result)

            # Update pattern statistics
            pattern.uses += 1
            if data:
                pattern.successes += 1
                pattern.confidence = pattern.success_rate
            self._save_patterns()

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return DiscoveryResult(
                success=bool(data),
                patterns=[pattern],
                data=data,
                duration_ms=duration,
            )

        except Exception as e:
            pattern.uses += 1
            self._save_patterns()

            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            return DiscoveryResult(
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    def find_matching_pattern(
        self,
        url: str | None = None,
        domain: str | None = None,
    ) -> DiscoveredPattern | None:
        """Find a pattern that might work for a URL or domain.

        Args:
            url: URL to match (by domain similarity)
            domain: Data domain to match

        Returns:
            Best matching pattern or None
        """
        candidates = []

        for pattern in self.patterns.values():
            score = 0

            # Domain match
            if domain and pattern.domain == domain:
                score += 0.5

            # URL similarity (same domain)
            if url:
                from urllib.parse import urlparse

                parsed_url = urlparse(url)
                parsed_pattern = urlparse(pattern.source_url)
                if parsed_url.netloc == parsed_pattern.netloc:
                    score += 0.3

            # Success rate
            score += pattern.success_rate * 0.2

            if score > 0:
                candidates.append((score, pattern))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return None

    def get_patterns_by_domain(self, domain: str) -> list[DiscoveredPattern]:
        """Get all patterns for a specific domain."""
        return [p for p in self.patterns.values() if p.domain == domain]

    def get_top_patterns(self, n: int = 10) -> list[DiscoveredPattern]:
        """Get top N patterns by success rate."""
        sorted_patterns = sorted(
            self.patterns.values(),
            key=lambda p: (p.success_rate, p.uses),
            reverse=True,
        )
        return sorted_patterns[:n]


# Convenience function for quick discovery
async def discover_data(
    url: str,
    query: str,
    domain: str = "entreprises",
    ollama_url: str = "http://localhost:11434",
    model: str = "qwen3.5:27b",
) -> list[dict[str, Any]]:
    """Quick data discovery helper.

    Args:
        url: URL to scrape
        query: What data to extract
        domain: Data domain
        ollama_url: Ollama API URL
        model: LLM model to use

    Returns:
        List of extracted data items
    """
    engine = DiscoveryEngine(ollama_url=ollama_url, model=model)
    result = await engine.discover(url, query, domain)
    return result.data if result.success else []
