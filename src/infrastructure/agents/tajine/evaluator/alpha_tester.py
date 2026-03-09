"""Alpha Tester - Predictive power evaluation using SHAP-inspired metrics."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.infrastructure.agents.tajine.core.types import RawData

logger = logging.getLogger(__name__)


def _get_content_text(data: RawData) -> str:
    """Extract text content from RawData."""
    if isinstance(data.content, str):
        return data.content
    elif isinstance(data.content, dict):
        parts = []
        for _key, value in data.content.items():
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, (list, tuple)):
                parts.extend(str(v) for v in value)
            else:
                parts.append(str(value))
        return " ".join(parts)
    return str(data.content)


@dataclass
class AlphaResult:
    """Result of alpha (predictive power) testing."""
    score: float  # 0.0 - 1.0
    novelty: float  # How new is this information
    relevance: float  # How relevant to current analysis
    timeliness: float  # How fresh is the information
    details: dict[str, Any]


class AlphaTester:
    """
    Tests the predictive power (alpha) of new data.

    Alpha = Information that provides edge in understanding/prediction.

    Components:
    1. Novelty: Is this genuinely new information?
    2. Relevance: Does it relate to our analysis targets?
    3. Timeliness: How recent/fresh is the information?

    Inspired by SHAP: measures marginal contribution of data to
    reducing uncertainty in our predictions.
    """

    # Freshness decay (days -> score multiplier)
    FRESHNESS_DECAY = {
        0: 1.0,    # Today
        1: 0.95,   # Yesterday
        7: 0.85,   # This week
        30: 0.70,  # This month
        90: 0.50,  # This quarter
        365: 0.30, # This year
    }

    # High-alpha keywords (business intelligence signals)
    ALPHA_SIGNALS = {
        "high": [
            "acquisition", "fusion", "rachat", "levée de fonds",
            "licenciement", "restructuration", "liquidation",
            "nouveau contrat", "expansion", "ouverture",
            "croissance", "augmentation capital",
        ],
        "medium": [
            "nomination", "changement", "mise à jour",
            "modification", "évolution", "ajustement",
        ],
        "low": [
            "confirmation", "maintien", "stable",
            "inchangé", "identique",
        ],
    }

    def __init__(
        self,
        seen_hashes: set[str] | None = None,
        novelty_weight: float = 0.4,
        relevance_weight: float = 0.35,
        timeliness_weight: float = 0.25,
    ):
        """
        Initialize Alpha Tester.

        Args:
            seen_hashes: Set of content hashes already processed
            novelty_weight: Weight for novelty in final score
            relevance_weight: Weight for relevance
            timeliness_weight: Weight for timeliness
        """
        self.seen_hashes = seen_hashes or set()
        self.weights = {
            "novelty": novelty_weight,
            "relevance": relevance_weight,
            "timeliness": timeliness_weight,
        }

    async def test(self, data: RawData) -> float:
        """
        Test data's alpha (predictive power).

        Args:
            data: Raw data to evaluate

        Returns:
            Alpha score between 0.0 and 1.0
        """
        result = await self.analyze(data)
        return result.score

    async def analyze(self, data: RawData) -> AlphaResult:
        """
        Full alpha analysis with detailed breakdown.

        Args:
            data: Raw data to analyze

        Returns:
            AlphaResult with component scores
        """
        # 1. Novelty check
        novelty, novelty_details = self._compute_novelty(data)

        # 2. Relevance check
        relevance, relevance_details = self._compute_relevance(data)

        # 3. Timeliness check
        timeliness, timeliness_details = self._compute_timeliness(data)

        # Weighted combination
        score = (
            novelty * self.weights["novelty"] +
            relevance * self.weights["relevance"] +
            timeliness * self.weights["timeliness"]
        )

        return AlphaResult(
            score=round(score, 3),
            novelty=novelty,
            relevance=relevance,
            timeliness=timeliness,
            details={
                "novelty": novelty_details,
                "relevance": relevance_details,
                "timeliness": timeliness_details,
            },
        )

    def _compute_novelty(self, data: RawData) -> tuple[float, dict]:
        """
        Compute novelty score based on content uniqueness.

        Uses content hashing to detect duplicates and
        near-duplicate detection for similar content.
        """
        content = _get_content_text(data)
        details = {}

        # Hash-based duplicate detection
        content_hash = self._hash_content(content)
        if content_hash in self.seen_hashes:
            details["duplicate"] = True
            return 0.1, details

        # Mark as seen
        self.seen_hashes.add(content_hash)
        details["duplicate"] = False

        # Check for high-alpha signals
        signal_score = self._detect_alpha_signals(content)
        details["signal_score"] = signal_score

        # Combine: new content gets base score, signals add bonus
        novelty = 0.5 + (signal_score * 0.5)

        return round(novelty, 3), details

    def _detect_alpha_signals(self, content: str) -> float:
        """Detect high-value business signals in content."""
        content_lower = content.lower()

        high_count = sum(
            1 for sig in self.ALPHA_SIGNALS["high"]
            if sig in content_lower
        )
        medium_count = sum(
            1 for sig in self.ALPHA_SIGNALS["medium"]
            if sig in content_lower
        )
        low_count = sum(
            1 for sig in self.ALPHA_SIGNALS["low"]
            if sig in content_lower
        )

        # Weight signals: high=1.0, medium=0.5, low=0.2
        weighted = high_count * 1.0 + medium_count * 0.5 + low_count * 0.2
        total_signals = high_count + medium_count + low_count

        if total_signals == 0:
            return 0.3  # No signals, neutral-low

        # Normalize by total signals
        return min(1.0, weighted / max(total_signals, 1))

    def _compute_relevance(self, data: RawData) -> tuple[float, dict]:
        """
        Compute relevance to territorial intelligence context.

        Higher score for data about:
        - Business entities (SIREN, SIRET)
        - Geographic mentions (departments, cities)
        - Economic indicators (CA, effectifs, etc.)
        """
        content = _get_content_text(data)
        details = {}

        scores = []

        # Entity mentions
        siren_count = len(re.findall(r"\b\d{9}\b", content))
        siret_count = len(re.findall(r"\b\d{14}\b", content))
        entity_score = min(1.0, (siren_count + siret_count) * 0.25)
        details["entity_mentions"] = siren_count + siret_count
        scores.append(entity_score)

        # Geographic mentions (French departments)
        dept_pattern = r"\b(0[1-9]|[1-8]\d|9[0-5]|2[AB])\b"
        dept_matches = re.findall(dept_pattern, content)
        geo_score = min(1.0, len(dept_matches) * 0.2)
        details["geo_mentions"] = len(dept_matches)
        scores.append(geo_score)

        # Economic keywords
        economic_keywords = [
            "chiffre d'affaires", "effectif", "salarié",
            "capital", "investissement", "subvention",
            "marché public", "appel d'offres",
        ]
        eco_count = sum(1 for kw in economic_keywords if kw in content.lower())
        eco_score = min(1.0, eco_count * 0.25)
        details["economic_keywords"] = eco_count
        scores.append(eco_score)

        # Average with minimum floor (reduced floor to differentiate)
        relevance = max(0.1, sum(scores) / len(scores))

        return round(relevance, 3), details

    def _compute_timeliness(self, data: RawData) -> tuple[float, dict]:
        """
        Compute timeliness based on data freshness.

        Uses extracted date or fetched_at timestamp.
        """
        details = {}

        # Try to extract date from content
        content = _get_content_text(data)
        extracted_date = self._extract_date(content)

        if extracted_date:
            reference_date = extracted_date
            details["date_source"] = "extracted"
        else:
            reference_date = data.fetched_at
            details["date_source"] = "fetched_at"

        details["reference_date"] = reference_date.isoformat()

        # Compute age in days
        now = datetime.now(UTC)
        if reference_date.tzinfo is None:
            reference_date = reference_date.replace(tzinfo=UTC)

        age_days = (now - reference_date).days
        details["age_days"] = age_days

        # Apply decay curve
        timeliness = self._freshness_score(age_days)

        return round(timeliness, 3), details

    def _extract_date(self, content: str) -> datetime | None:
        """Try to extract a date from content."""
        # Common French date patterns
        patterns = [
            # DD/MM/YYYY
            (r"(\d{1,2})/(\d{1,2})/(\d{4})", lambda m: f"{m.group(3)}-{m.group(2)}-{m.group(1)}"),
            # YYYY-MM-DD
            (r"(\d{4})-(\d{2})-(\d{2})", lambda m: m.group(0)),
            # DD month YYYY
            (r"(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})",
             self._parse_french_date),
        ]

        for pattern, formatter in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    date_str = formatter(match)
                    if date_str:
                        return datetime.fromisoformat(date_str)
                except (ValueError, AttributeError):
                    continue

        return None

    def _parse_french_date(self, match) -> str | None:
        """Parse French month name to ISO date."""
        months = {
            "janvier": "01", "février": "02", "mars": "03",
            "avril": "04", "mai": "05", "juin": "06",
            "juillet": "07", "août": "08", "septembre": "09",
            "octobre": "10", "novembre": "11", "décembre": "12",
        }
        day = match.group(1).zfill(2)
        month = months.get(match.group(2).lower())
        year = match.group(3)

        if month:
            return f"{year}-{month}-{day}"
        return None

    def _freshness_score(self, age_days: int) -> float:
        """Convert age in days to freshness score using decay curve."""
        if age_days < 0:
            return 0.3  # Future dates are suspicious

        # Find appropriate decay bracket
        prev_days = 0
        prev_score = 1.0

        for threshold_days, score in sorted(self.FRESHNESS_DECAY.items()):
            if age_days <= threshold_days:
                # Linear interpolation between brackets
                if threshold_days == prev_days:
                    return score
                ratio = (age_days - prev_days) / (threshold_days - prev_days)
                return prev_score - ratio * (prev_score - score)
            prev_days = threshold_days
            prev_score = score

        # Older than 1 year
        return 0.2

    def _hash_content(self, content: str) -> str:
        """Create hash of content for duplicate detection."""
        # Normalize content
        normalized = content.lower().strip()
        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized)
        # Hash
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def reset_seen(self):
        """Reset the seen hashes for a new analysis session."""
        self.seen_hashes.clear()
