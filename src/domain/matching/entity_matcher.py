"""Entity matcher with SIRET and fuzzy name matching."""

from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from rapidfuzz import fuzz


@dataclass
class MatchResult:
    """Result of entity matching."""

    is_match: bool
    confidence: float  # 0-100 score
    match_reasons: list[str] = field(default_factory=list)
    entity_a: dict[str, Any] = field(default_factory=dict)
    entity_b: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"MatchResult(is_match={self.is_match}, confidence={self.confidence:.1f}, reasons={self.match_reasons})"


class EntityMatcher:
    """Match entities across data sources using SIRET and fuzzy name matching.

    Matching Strategy:
    1. Exact SIRET match → 100% confidence
    2. Partial SIRET match (SIREN only) → 85% confidence
    3. Fuzzy name match → 0-80% confidence based on similarity
    4. Combined signals boost confidence

    Example:
        matcher = EntityMatcher()
        result = matcher.match(
            {"siret": "12345678901234", "name": "ACME Corp"},
            {"siret": "12345678901234", "name": "Acme Corporation"}
        )
        # result.confidence == 100, result.is_match == True
    """

    # Confidence thresholds
    SIRET_MATCH_CONFIDENCE = 100
    SIREN_MATCH_CONFIDENCE = 85
    NAME_MATCH_THRESHOLD = 70  # Minimum fuzzy score to consider a name match

    def __init__(
        self,
        siret_weight: float = 0.7,
        name_weight: float = 0.3,
        match_threshold: float = 60,
    ):
        """Initialize matcher with weights.

        Args:
            siret_weight: Weight for SIRET matching (0-1)
            name_weight: Weight for name matching (0-1)
            match_threshold: Minimum confidence to consider a match
        """
        self.siret_weight = siret_weight
        self.name_weight = name_weight
        self.match_threshold = match_threshold

    def match(
        self,
        entity_a: dict[str, Any],
        entity_b: dict[str, Any],
    ) -> MatchResult:
        """Match two entities and return confidence score.

        Args:
            entity_a: First entity with optional siret, siren, name fields
            entity_b: Second entity with optional siret, siren, name fields

        Returns:
            MatchResult with confidence score and match reasons
        """
        confidence = 0.0
        reasons = []

        # 1. Check exact SIRET match
        siret_score = self._match_siret(entity_a, entity_b)
        if siret_score == self.SIRET_MATCH_CONFIDENCE:
            reasons.append("siret")
        elif siret_score == self.SIREN_MATCH_CONFIDENCE:
            reasons.append("siren")

        # 2. Check fuzzy name match
        name_score = self._match_name(entity_a, entity_b)
        if name_score >= self.NAME_MATCH_THRESHOLD:
            reasons.append(f"name({name_score:.0f}%)")

        # 3. Calculate combined confidence
        if siret_score == self.SIRET_MATCH_CONFIDENCE:
            # Perfect SIRET match dominates
            confidence = self.SIRET_MATCH_CONFIDENCE
        elif siret_score > 0 and name_score > 0:
            # Combine signals with weights
            confidence = (siret_score * self.siret_weight) + (name_score * self.name_weight)
            # Boost for multiple matching criteria
            confidence = min(confidence * 1.1, 100)
        elif siret_score > 0:
            confidence = siret_score * self.siret_weight
        elif name_score > 0:
            confidence = name_score * self.name_weight
        else:
            confidence = 0

        is_match = confidence >= self.match_threshold

        return MatchResult(
            is_match=is_match,
            confidence=confidence,
            match_reasons=reasons,
            entity_a=entity_a,
            entity_b=entity_b,
        )

    def _match_siret(self, entity_a: dict, entity_b: dict) -> float:
        """Match by SIRET or SIREN.

        Returns:
            100 for exact SIRET match, 85 for SIREN match, 0 otherwise
        """
        siret_a = self._normalize_siret(entity_a.get("siret", ""))
        siret_b = self._normalize_siret(entity_b.get("siret", ""))

        # Exact SIRET match (14 digits)
        if siret_a and siret_b and siret_a == siret_b:
            return self.SIRET_MATCH_CONFIDENCE

        # Extract SIREN (first 9 digits)
        siren_a = siret_a[:9] if len(siret_a) >= 9 else entity_a.get("siren", "")
        siren_b = siret_b[:9] if len(siret_b) >= 9 else entity_b.get("siren", "")

        if siren_a and siren_b and siren_a == siren_b:
            return self.SIREN_MATCH_CONFIDENCE

        return 0

    def _match_name(self, entity_a: dict, entity_b: dict) -> float:
        """Match by fuzzy name comparison.

        Returns:
            Similarity score 0-100
        """
        name_a = self._normalize_name(entity_a.get("name", ""))
        name_b = self._normalize_name(entity_b.get("name", ""))

        if not name_a or not name_b:
            return 0

        # Use multiple fuzzy algorithms and take the best
        scores = [
            fuzz.ratio(name_a, name_b),
            fuzz.partial_ratio(name_a, name_b),
            fuzz.token_sort_ratio(name_a, name_b),
            fuzz.token_set_ratio(name_a, name_b),
        ]

        return max(scores)

    def _normalize_siret(self, siret: str) -> str:
        """Normalize SIRET by removing spaces and non-digits."""
        return "".join(c for c in str(siret) if c.isdigit())

    def _normalize_name(self, name: str) -> str:
        """Normalize company name for comparison."""
        if not name:
            return ""

        name = name.upper()

        # Remove common suffixes that don't affect identity
        suffixes = [
            "SAS", "SARL", "SA", "EURL", "SNC", "SASU",
            "SOCIETE", "SOCIÉTÉ", "ENTREPRISE",
            "FRANCE", "EUROPE", "INTERNATIONAL",
        ]
        for suffix in suffixes:
            name = name.replace(f" {suffix}", "")

        # Remove punctuation and extra spaces
        name = "".join(c if c.isalnum() or c.isspace() else " " for c in name)
        name = " ".join(name.split())

        return name

    def find_matches(
        self,
        target: dict[str, Any],
        candidates: list[dict[str, Any]],
        min_confidence: float | None = None,
    ) -> list[MatchResult]:
        """Find all matching entities in a collection.

        Args:
            target: Entity to match
            candidates: List of candidate entities
            min_confidence: Minimum confidence (default: self.match_threshold)

        Returns:
            List of MatchResults sorted by confidence (descending)
        """
        threshold = min_confidence or self.match_threshold
        results = []

        for candidate in candidates:
            result = self.match(target, candidate)
            if result.confidence >= threshold:
                results.append(result)

        # Sort by confidence descending
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def deduplicate(
        self,
        entities: list[dict[str, Any]],
    ) -> list[list[dict[str, Any]]]:
        """Group entities that likely refer to the same real-world entity.

        Args:
            entities: List of entities to deduplicate

        Returns:
            List of groups, where each group contains matching entities
        """
        if not entities:
            return []

        groups: list[list[dict[str, Any]]] = []
        used = set()

        for i, entity in enumerate(entities):
            if i in used:
                continue

            group = [entity]
            used.add(i)

            # Find all matches for this entity
            for j, candidate in enumerate(entities):
                if j in used or j == i:
                    continue

                result = self.match(entity, candidate)
                if result.is_match:
                    group.append(candidate)
                    used.add(j)

            groups.append(group)

        logger.debug(f"Deduplicated {len(entities)} entities into {len(groups)} groups")
        return groups
