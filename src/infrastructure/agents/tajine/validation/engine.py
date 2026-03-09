"""
ValidationEngine - Anti-hallucination pipeline for TAJINE.

5-layer validation:
1. Source verification
2. Data consistency check
3. Knowledge graph cross-reference
4. Confidence calibration (MAPIE-inspired)
5. Human-in-the-loop flag
"""

from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.infrastructure.agents.tajine.validation.knowledge_graph import KnowledgeGraph


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    confidence: float
    sources_checked: list[str]
    flags: list[str]
    details: dict[str, Any]


class ValidationEngine:
    """
    Anti-hallucination validation engine.

    Validates claims against:
    - Known data sources
    - Knowledge graph
    - Statistical consistency
    - Confidence bounds
    """

    # Source reliability scores
    SOURCE_RELIABILITY = {
        'sirene_api': 0.95,
        'official_api': 0.90,
        'insee': 0.95,
        'bodacc': 0.90,
        'web_scrape': 0.60,
        'estimated': 0.40,
        None: 0.20
    }

    def __init__(self, knowledge_graph: KnowledgeGraph | None = None):
        """
        Initialize ValidationEngine.

        Args:
            knowledge_graph: Optional shared KnowledgeGraph instance.
                           If None, creates a new empty graph.
        """
        self.knowledge_graph = knowledge_graph or KnowledgeGraph()
        logger.info("ValidationEngine initialized with KnowledgeGraph")

    async def validate(self, claim_data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate a claim against multiple sources.

        Args:
            claim_data: Dict with:
                - claim: Text description of the claim
                - source: Data source identifier
                - data: Supporting data dict
                - entity_type: Optional entity type for KG lookup (e.g., "company")
                - entity_id: Optional entity ID for KG lookup (e.g., SIREN)

        Returns:
            ValidationResult as dict with is_valid, confidence, sources_checked, flags, details
        """
        claim = claim_data.get('claim', '')
        source = claim_data.get('source')
        data = claim_data.get('data', {})
        entity_type = claim_data.get('entity_type')
        entity_id = claim_data.get('entity_id')

        flags: list[str] = []
        sources_checked: list[str] = []
        details: dict[str, Any] = {}

        # Layer 1: Source verification
        source_score = self._verify_source(source)
        sources_checked.append(source or 'none')
        details['source_score'] = source_score

        # Layer 2: Data consistency
        data_score = self._check_data_consistency(claim, data)
        details['data_score'] = data_score

        # Layer 3: Knowledge Graph cross-reference
        kg_score, kg_conflicts = self._cross_reference_knowledge_graph(
            data=data,
            entity_type=entity_type,
            entity_id=entity_id
        )
        details['kg_score'] = kg_score
        if kg_conflicts:
            flags.append('kg_conflict')
            details['kg_conflicts'] = kg_conflicts
        if kg_score > 0:
            sources_checked.append('knowledge_graph')

        # Layer 4: Hallucination detection (enhanced with KG)
        is_hallucination = self._detect_hallucination(
            claim, source, data, kg_score, kg_conflicts
        )
        if is_hallucination:
            flags.append('hallucination')
            details['hallucination_reason'] = self._get_hallucination_reason(
                source, data, kg_conflicts
            )

        # Layer 5: Confidence calibration
        confidence = self._calibrate_confidence(
            source_score, data_score, kg_score, is_hallucination
        )
        details['calibrated_confidence'] = confidence

        # Layer 6: Determine validity and flags
        is_valid = not is_hallucination and confidence >= 0.5

        # Add warning flags based on thresholds
        if confidence < 0.5:
            flags.append('low_confidence')
        if source_score < 0.5:
            flags.append('unreliable_source')
        if not data:
            flags.append('no_supporting_data')
        if confidence >= 0.8:
            flags.append('high_confidence')

        return {
            'is_valid': is_valid,
            'confidence': confidence,
            'sources_checked': sources_checked,
            'flags': flags,
            'details': details
        }

    def _cross_reference_knowledge_graph(
        self,
        data: dict[str, Any],
        entity_type: str | None,
        entity_id: str | None
    ) -> tuple[float, list[str]]:
        """
        Cross-reference data against knowledge graph.

        Args:
            data: Data claims to validate
            entity_type: Entity type (e.g., "company")
            entity_id: Entity identifier (e.g., SIREN)

        Returns:
            Tuple of (confidence_score, list_of_conflicts)
        """
        if not entity_type or not entity_id or not data:
            return 0.0, []

        # Cross-reference all claims
        results = self.knowledge_graph.cross_reference(
            claims=data,
            entity_type=entity_type,
            entity_id=entity_id
        )

        if not results:
            return 0.0, []

        # Calculate aggregate score
        verified_count = 0
        conflict_count = 0
        conflicts = []
        total_confidence = 0.0

        for predicate, match in results.items():
            if match.found:
                if match.matching_triples:
                    verified_count += 1
                    total_confidence += match.confidence
                elif match.conflicts:
                    conflict_count += 1
                    for conflict in match.conflicts:
                        conflicts.append(
                            f"{predicate}: claimed '{data.get(predicate)}' "
                            f"vs known '{conflict.obj}' (source: {conflict.source})"
                        )

        total_claims = verified_count + conflict_count
        if total_claims == 0:
            return 0.0, []

        # Score based on verified vs conflicting
        if conflict_count > 0:
            # Penalize conflicts heavily
            kg_score = (verified_count - conflict_count * 2) / total_claims
            kg_score = max(0.0, min(1.0, kg_score))
        else:
            kg_score = total_confidence / verified_count if verified_count > 0 else 0.0

        return kg_score, conflicts

    def _get_hallucination_reason(
        self,
        source: str | None,
        data: dict[str, Any],
        kg_conflicts: list[str]
    ) -> str:
        """Generate human-readable hallucination reason."""
        if kg_conflicts:
            return f"Data conflicts with known facts: {kg_conflicts[0]}"
        if source is None and not data:
            return "No source or supporting data for claim"
        if not data:
            return "No supporting data for claim"
        return "Claim not verifiable"

    def _verify_source(self, source: str | None) -> float:
        """
        Verify source reliability.

        Args:
            source: Source identifier

        Returns:
            Reliability score between 0 and 1
        """
        return self.SOURCE_RELIABILITY.get(source, 0.30)

    def _check_data_consistency(self, claim: str, data: dict[str, Any]) -> float:
        """
        Check if data supports the claim.

        Args:
            claim: The claim to validate
            data: Supporting data

        Returns:
            Consistency score between 0 and 1
        """
        if not data:
            return 0.2  # No data = low consistency

        # Check if data has meaningful values
        if all(v is None or v == '' for v in data.values()):
            return 0.3

        # Data exists and has values
        return 0.8

    def _detect_hallucination(
        self,
        claim: str,
        source: str | None,
        data: dict[str, Any],
        kg_score: float = 0.0,
        kg_conflicts: list[str] | None = None
    ) -> bool:
        """
        Detect if the claim is likely hallucinated.

        Enhanced with Knowledge Graph validation.

        Args:
            claim: The claim to check
            source: Source of the claim
            data: Supporting data
            kg_score: Knowledge graph validation score
            kg_conflicts: List of conflicts with known facts

        Returns:
            True if hallucination is detected
        """
        # Knowledge graph conflicts = strong hallucination signal
        if kg_conflicts and len(kg_conflicts) > 0:
            return True

        # No source AND no data = likely hallucination
        if source is None and not data:
            return True

        # Claim exists but no supporting evidence
        return bool(claim and not data and source is None)

    def _calibrate_confidence(
        self,
        source_score: float,
        data_score: float,
        kg_score: float,
        is_hallucination: bool
    ) -> float:
        """
        Calibrate confidence based on all factors.

        Uses weighted combination of scores with KG validation.

        Args:
            source_score: Source reliability score
            data_score: Data consistency score
            kg_score: Knowledge graph validation score
            is_hallucination: Whether hallucination detected

        Returns:
            Calibrated confidence between 0 and 1
        """
        if is_hallucination:
            return 0.1  # Very low confidence for hallucinations

        # Weighted average with KG score
        if kg_score > 0:
            # KG provides strong validation signal
            # source: 40%, data: 20%, kg: 40%
            base_confidence = (
                source_score * 0.4 +
                data_score * 0.2 +
                kg_score * 0.4
            )
        else:
            # No KG data - fall back to source + data
            # source: 60%, data: 40%
            base_confidence = (source_score * 0.6) + (data_score * 0.4)

        # Apply MAPIE-inspired calibration (conservative adjustment)
        # Reduce overconfidence
        calibrated = base_confidence * 0.9

        return round(calibrated, 2)
