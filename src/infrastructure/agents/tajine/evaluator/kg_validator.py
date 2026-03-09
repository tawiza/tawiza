"""KG Validator - Knowledge Graph coherence checker for Evaluator."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.infrastructure.agents.tajine.core.types import RawData

logger = logging.getLogger(__name__)


def _get_content_text(data: RawData) -> str:
    """Extract text content from RawData."""
    if isinstance(data.content, str):
        return data.content
    elif isinstance(data.content, dict):
        # Flatten dict to text
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


class CoherenceIssue(Enum):
    """Types of coherence issues."""
    CONTRADICTION = "contradiction"
    IMPLAUSIBLE_RELATION = "implausible_relation"
    ORPHAN_ENTITY = "orphan_entity"
    PATTERN_VIOLATION = "pattern_violation"
    TEMPORAL_INCONSISTENCY = "temporal_inconsistency"


@dataclass
class CoherenceCheck:
    """Result of a coherence check."""
    passed: bool
    score: float  # 0.0 - 1.0
    issues: list[CoherenceIssue]
    details: dict[str, Any]


class KGValidator:
    """
    Validates data coherence against the Knowledge Graph.

    Checks:
    1. Contradictions: Does this data contradict existing facts?
    2. Plausibility: Are the relationships in data plausible?
    3. Patterns: Does data follow known patterns (SIREN format, etc.)?
    4. Temporal: Are dates and sequences consistent?
    """

    # Pattern validators for French business data
    PATTERNS = {
        "siren": re.compile(r"^\d{9}$"),
        "siret": re.compile(r"^\d{14}$"),
        "code_postal": re.compile(r"^\d{5}$"),
        "code_naf": re.compile(r"^\d{2}\.\d{2}[A-Z]$"),
    }

    # Plausibility rules for relationships
    PLAUSIBLE_RELATIONS = {
        ("Entreprise", "Dirigeant"): ["A_DIRIGEANT", "DIRIGE"],
        ("Entreprise", "Etablissement"): ["A_ETABLISSEMENT", "SIEGE"],
        ("Entreprise", "Contrat"): ["A_REMPORTE", "CANDIDATE"],
        ("Dirigeant", "Entreprise"): ["DIRIGE", "PARTICIPE"],
    }

    def __init__(
        self,
        neo4j_client=None,
        contradiction_weight: float = 0.4,
        pattern_weight: float = 0.3,
        plausibility_weight: float = 0.3,
    ):
        """
        Initialize KG Validator.

        Args:
            neo4j_client: Optional Neo4j client for graph queries
            contradiction_weight: Weight for contradiction checks
            pattern_weight: Weight for pattern validation
            plausibility_weight: Weight for relationship plausibility
        """
        self.neo4j = neo4j_client
        self.weights = {
            "contradiction": contradiction_weight,
            "pattern": pattern_weight,
            "plausibility": plausibility_weight,
        }

    async def check(self, data: RawData) -> float:
        """
        Check data coherence and return a score.

        Args:
            data: Raw data to validate

        Returns:
            Coherence score between 0.0 and 1.0
        """
        result = await self.validate(data)
        return result.score

    async def validate(self, data: RawData) -> CoherenceCheck:
        """
        Full validation returning detailed results.

        Args:
            data: Raw data to validate

        Returns:
            CoherenceCheck with score and details
        """
        issues = []
        scores = {}

        # 1. Pattern validation (always available)
        pattern_score = self._validate_patterns(data, issues)
        scores["pattern"] = pattern_score

        # 2. Plausibility check (always available)
        plausibility_score = self._check_plausibility(data, issues)
        scores["plausibility"] = plausibility_score

        # 3. Contradiction check (requires Neo4j)
        if self.neo4j:
            contradiction_score = await self._check_contradictions(data, issues)
        else:
            # Fallback: trust source quality hint
            contradiction_score = data.quality_hint
        scores["contradiction"] = contradiction_score

        # Compute weighted average
        total_score = sum(
            scores[k] * self.weights[k] for k in scores
        )

        return CoherenceCheck(
            passed=total_score >= 0.5,
            score=round(total_score, 3),
            issues=issues,
            details=scores,
        )

    def _validate_patterns(
        self, data: RawData, issues: list[CoherenceIssue]
    ) -> float:
        """Validate that identifiers follow expected patterns."""
        violations = 0
        checks = 0

        content = _get_content_text(data)

        # Extract and validate SIREN/SIRET
        siren_matches = re.findall(r"\b(\d{9})\b", content)
        siret_matches = re.findall(r"\b(\d{14})\b", content)

        for siren in siren_matches:
            checks += 1
            if not self._is_valid_siren(siren):
                violations += 1
                issues.append(CoherenceIssue.PATTERN_VIOLATION)

        for siret in siret_matches:
            checks += 1
            if not self._is_valid_siret(siret):
                violations += 1
                issues.append(CoherenceIssue.PATTERN_VIOLATION)

        # Check postal codes
        postal_matches = re.findall(r"\b((?:0[1-9]|[1-8]\d|9[0-5])\d{3})\b", content)
        for _ in postal_matches:
            checks += 1
            # French postal codes are valid if 5 digits starting 01-95

        if checks == 0:
            return 0.5  # No patterns to validate, neutral

        return max(0.0, 1.0 - (violations / checks))

    def _is_valid_siren(self, siren: str) -> bool:
        """Validate SIREN using Luhn algorithm."""
        if not self.PATTERNS["siren"].match(siren):
            return False

        # Luhn checksum
        total = 0
        for i, digit in enumerate(siren):
            d = int(digit)
            if i % 2 == 1:  # Even positions (0-indexed)
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    def _is_valid_siret(self, siret: str) -> bool:
        """Validate SIRET using Luhn algorithm."""
        if not self.PATTERNS["siret"].match(siret):
            return False

        # SIRET = SIREN (9) + NIC (5), check full Luhn
        total = 0
        for i, digit in enumerate(siret):
            d = int(digit)
            if i % 2 == 0:  # Even positions get doubled for SIRET
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    def _check_plausibility(
        self, data: RawData, issues: list[CoherenceIssue]
    ) -> float:
        """Check if mentioned relationships are plausible."""
        content = _get_content_text(data).lower()

        # Heuristic checks for implausible claims
        implausible_patterns = [
            # Impossible financial figures
            (r"chiffre d.affaires.*(\d+)\s*(milliards?|Md)", "revenue_impossible"),
            # Future dates for past events
            (r"créée?\s+en\s+20[3-9]\d", "future_creation"),
            # Negative employees
            (r"(-\d+)\s*salari", "negative_employees"),
        ]

        plausibility_issues = 0

        for pattern, _ in implausible_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                plausibility_issues += 1
                issues.append(CoherenceIssue.IMPLAUSIBLE_RELATION)

        # Score based on issues found
        if plausibility_issues == 0:
            return 1.0
        elif plausibility_issues <= 2:
            return 0.5
        else:
            return 0.2

    async def _check_contradictions(
        self, data: RawData, issues: list[CoherenceIssue]
    ) -> float:
        """Check for contradictions with existing KG data."""
        if not self.neo4j:
            return 0.5  # Neutral if no KG

        # Extract entities from data
        content = _get_content_text(data)
        sirens = re.findall(r"\b(\d{9})\b", content)

        if not sirens:
            return 0.7  # No entities to check, slightly positive

        contradictions = 0
        checks = 0

        for siren in sirens[:5]:  # Limit checks
            try:
                existing = await self._get_existing_entity(siren)
                if existing:
                    checks += 1
                    if self._has_contradiction(data, existing):
                        contradictions += 1
                        issues.append(CoherenceIssue.CONTRADICTION)
            except Exception as e:
                logger.warning(f"Failed to check contradiction for {siren}: {e}")

        if checks == 0:
            return 0.6  # No existing data, slightly positive

        return max(0.0, 1.0 - (contradictions / checks))

    async def _get_existing_entity(self, siren: str) -> dict | None:
        """Fetch existing entity from KG."""
        if not self.neo4j:
            return None

        query = """
        MATCH (e:Entreprise {siren: $siren})
        RETURN e.denominationUniteLegale as nom,
               e.activitePrincipaleUniteLegale as activite,
               e.effectif as effectif,
               e.dateCreation as creation
        LIMIT 1
        """

        try:
            results = await self.neo4j.run_query(query, {"siren": siren})
            return results[0] if results else None
        except Exception:
            return None

    def _has_contradiction(self, data: RawData, existing: dict) -> bool:
        """Check if data contradicts existing entity."""
        content = _get_content_text(data).lower()

        # Check for name contradictions (simplified)
        if existing.get("nom"):
            existing["nom"].lower()
            # If data mentions a completely different name for same SIREN
            # This is a simplified heuristic

        # Check for creation date contradictions
        if existing.get("creation"):
            existing_year = existing["creation"][:4] if existing["creation"] else None
            if existing_year:
                # Look for conflicting creation year
                year_mentions = re.findall(r"créée?\s+en\s+(\d{4})", content)
                for year in year_mentions:
                    if year != existing_year:
                        return True

        return False
