"""
Knowledge Graph for TAJINE validation.

Lightweight in-memory graph for:
- Storing entity relationships (triples)
- Cross-referencing claims against known facts
- Anti-hallucination validation

Uses subject-predicate-object triples like RDF but simpler.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger


@dataclass
class Triple:
    """RDF-style triple: subject-predicate-object."""

    subject: str
    predicate: str
    obj: Any  # 'object' is reserved in Python
    source: str | None = None
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)

    def __hash__(self):
        return hash((self.subject, self.predicate, str(self.obj)))

    def __eq__(self, other):
        if not isinstance(other, Triple):
            return False
        return (self.subject, self.predicate, self.obj) == (
            other.subject,
            other.predicate,
            other.obj,
        )


@dataclass
class ValidationMatch:
    """Result of KG validation."""

    found: bool
    matching_triples: list[Triple]
    confidence: float
    conflicts: list[Triple]
    message: str


class KnowledgeGraph:
    """
    In-memory knowledge graph for validation.

    Stores facts as triples and allows querying/validation.

    Predicates used for business entities:
    - has_siren: Company SIREN number
    - has_siret: Establishment SIRET number
    - has_name: Legal name
    - has_address: Address
    - has_postal_code: Postal code
    - has_city: City
    - has_naf_code: NAF/APE activity code
    - has_legal_form: Legal form (SARL, SAS, etc.)
    - has_creation_date: Company creation date
    - has_capital: Share capital
    - has_employee_count: Number of employees
    - located_in: Geographic location relationship
    - belongs_to_sector: Industry sector
    - is_subsidiary_of: Parent company relationship
    """

    # Common predicates for normalization
    PREDICATES = {
        "siren": "has_siren",
        "siret": "has_siret",
        "name": "has_name",
        "denomination": "has_name",
        "address": "has_address",
        "adresse": "has_address",
        "postal_code": "has_postal_code",
        "code_postal": "has_postal_code",
        "city": "has_city",
        "ville": "has_city",
        "naf": "has_naf_code",
        "ape": "has_naf_code",
        "legal_form": "has_legal_form",
        "forme_juridique": "has_legal_form",
        "creation_date": "has_creation_date",
        "date_creation": "has_creation_date",
        "capital": "has_capital",
        "employees": "has_employee_count",
        "effectif": "has_employee_count",
    }

    def __init__(self):
        """Initialize empty knowledge graph."""
        # Index by subject for fast lookup
        self._by_subject: dict[str, set[Triple]] = defaultdict(set)
        # Index by predicate
        self._by_predicate: dict[str, set[Triple]] = defaultdict(set)
        # Index by object (for reverse lookups)
        self._by_object: dict[str, set[Triple]] = defaultdict(set)
        # All triples
        self._triples: set[Triple] = set()

        logger.info("KnowledgeGraph initialized")

    def add_triple(
        self,
        subject: str,
        predicate: str,
        obj: Any,
        source: str | None = None,
        confidence: float = 1.0,
    ) -> Triple:
        """
        Add a triple to the graph.

        Args:
            subject: Entity identifier (e.g., "company:123456789")
            predicate: Relationship type (e.g., "has_name")
            obj: Value or related entity
            source: Data source (e.g., "sirene_api")
            confidence: Confidence score 0-1

        Returns:
            The created Triple
        """
        # Normalize predicate
        predicate = self.PREDICATES.get(predicate.lower(), predicate)

        triple = Triple(
            subject=subject, predicate=predicate, obj=obj, source=source, confidence=confidence
        )

        self._triples.add(triple)
        self._by_subject[subject].add(triple)
        self._by_predicate[predicate].add(triple)
        self._by_object[str(obj)].add(triple)

        return triple

    def add_entity(
        self,
        entity_type: str,
        entity_id: str,
        properties: dict[str, Any],
        source: str | None = None,
        confidence: float = 1.0,
    ) -> list[Triple]:
        """
        Add an entity with multiple properties.

        Args:
            entity_type: Type of entity (e.g., "company", "establishment")
            entity_id: Unique identifier
            properties: Dict of property name -> value
            source: Data source
            confidence: Confidence score

        Returns:
            List of created triples
        """
        subject = f"{entity_type}:{entity_id}"
        triples = []

        for prop, value in properties.items():
            if value is not None and value != "":
                triple = self.add_triple(
                    subject=subject, predicate=prop, obj=value, source=source, confidence=confidence
                )
                triples.append(triple)

        logger.debug(f"Added entity {subject} with {len(triples)} properties")
        return triples

    def query(
        self, subject: str | None = None, predicate: str | None = None, obj: Any | None = None
    ) -> list[Triple]:
        """
        Query triples by pattern.

        Args:
            subject: Filter by subject (None = any)
            predicate: Filter by predicate (None = any)
            obj: Filter by object (None = any)

        Returns:
            Matching triples
        """
        # Normalize predicate if provided
        if predicate:
            predicate = self.PREDICATES.get(predicate.lower(), predicate)

        # Start with most specific index
        if subject:
            candidates = self._by_subject.get(subject, set())
        elif predicate:
            candidates = self._by_predicate.get(predicate, set())
        elif obj is not None:
            candidates = self._by_object.get(str(obj), set())
        else:
            candidates = self._triples

        # Filter by remaining criteria
        results = []
        for triple in candidates:
            if subject and triple.subject != subject:
                continue
            if predicate and triple.predicate != predicate:
                continue
            if obj is not None and triple.obj != obj:
                continue
            results.append(triple)

        return results

    def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        """
        Get all properties of an entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity identifier

        Returns:
            Dict of predicate -> value(s)
        """
        subject = f"{entity_type}:{entity_id}"
        triples = self.query(subject=subject)

        result: dict[str, Any] = {}
        for triple in triples:
            pred = triple.predicate
            if pred in result:
                # Multiple values - convert to list
                if not isinstance(result[pred], list):
                    result[pred] = [result[pred]]
                result[pred].append(triple.obj)
            else:
                result[pred] = triple.obj

        return result

    def validate_claim(
        self, subject: str, predicate: str, claimed_value: Any, tolerance: float = 0.0
    ) -> ValidationMatch:
        """
        Validate a claim against stored knowledge.

        Args:
            subject: Entity to validate
            predicate: Property being claimed
            claimed_value: The claimed value
            tolerance: Numeric tolerance for comparison (0-1)

        Returns:
            ValidationMatch with results
        """
        # Normalize predicate
        predicate = self.PREDICATES.get(predicate.lower(), predicate)

        # Find matching triples
        known_triples = self.query(subject=subject, predicate=predicate)

        if not known_triples:
            # No knowledge about this claim
            return ValidationMatch(
                found=False,
                matching_triples=[],
                confidence=0.0,
                conflicts=[],
                message=f"No knowledge about {subject}.{predicate}",
            )

        # Check for matches and conflicts
        matches = []
        conflicts = []

        for triple in known_triples:
            if self._values_match(triple.obj, claimed_value, tolerance):
                matches.append(triple)
            else:
                conflicts.append(triple)

        if matches:
            # Claim matches stored knowledge
            avg_confidence = sum(t.confidence for t in matches) / len(matches)
            return ValidationMatch(
                found=True,
                matching_triples=matches,
                confidence=avg_confidence,
                conflicts=conflicts,
                message=f"Claim verified by {len(matches)} source(s)",
            )
        else:
            # Claim conflicts with stored knowledge
            return ValidationMatch(
                found=True,
                matching_triples=[],
                confidence=0.0,
                conflicts=conflicts,
                message=f"Claim conflicts with {len(conflicts)} known fact(s)",
            )

    def _values_match(self, known: Any, claimed: Any, tolerance: float = 0.0) -> bool:
        """
        Compare two values with optional tolerance.

        Args:
            known: Value from knowledge graph
            claimed: Claimed value
            tolerance: Numeric tolerance (0-1, as percentage)

        Returns:
            True if values match
        """
        # String comparison (case-insensitive, normalized)
        if isinstance(known, str) and isinstance(claimed, str):
            return self._normalize_string(known) == self._normalize_string(claimed)

        # Numeric comparison with tolerance
        if isinstance(known, (int, float)) and isinstance(claimed, (int, float)):
            if tolerance > 0 and known != 0:
                diff = abs(known - claimed) / abs(known)
                return diff <= tolerance
            return known == claimed

        # Direct comparison
        return known == claimed

    def _normalize_string(self, s: str) -> str:
        """Normalize string for comparison."""
        return s.lower().strip().replace("-", " ").replace("_", " ")

    def cross_reference(
        self, claims: dict[str, Any], entity_type: str, entity_id: str
    ) -> dict[str, ValidationMatch]:
        """
        Cross-reference multiple claims against stored knowledge.

        Args:
            claims: Dict of predicate -> claimed value
            entity_type: Type of entity
            entity_id: Entity identifier

        Returns:
            Dict of predicate -> ValidationMatch
        """
        subject = f"{entity_type}:{entity_id}"
        results = {}

        for predicate, value in claims.items():
            if value is not None:
                results[predicate] = self.validate_claim(
                    subject=subject, predicate=predicate, claimed_value=value
                )

        return results

    def get_stats(self) -> dict[str, int]:
        """Get graph statistics."""
        return {
            "total_triples": len(self._triples),
            "unique_subjects": len(self._by_subject),
            "unique_predicates": len(self._by_predicate),
            "unique_objects": len(self._by_object),
        }

    def clear(self):
        """Clear all triples."""
        self._triples.clear()
        self._by_subject.clear()
        self._by_predicate.clear()
        self._by_object.clear()
        logger.info("KnowledgeGraph cleared")

    def populate_from_sirene(self, sirene_data: dict[str, Any]) -> list[Triple]:
        """
        Populate graph from SIRENE API response.

        Args:
            sirene_data: SIRENE API response data

        Returns:
            List of created triples
        """
        triples = []

        # Handle company (unite_legale)
        unite_legale = sirene_data.get("unite_legale", sirene_data)
        siren = unite_legale.get("siren")

        if siren:
            company_props = {
                "siren": siren,
                "name": unite_legale.get("denomination") or unite_legale.get("nom_complet"),
                "legal_form": unite_legale.get("categorie_juridique"),
                "creation_date": unite_legale.get("date_creation"),
                "naf": unite_legale.get("activite_principale"),
                "employees": unite_legale.get("tranche_effectifs"),
            }
            triples.extend(
                self.add_entity(
                    "company", siren, company_props, source="sirene_api", confidence=0.95
                )
            )

        # Handle establishments (etablissements)
        etablissements = sirene_data.get("etablissements", [])
        for etab in etablissements:
            siret = etab.get("siret")
            if siret:
                etab_props = {
                    "siret": siret,
                    "siren": etab.get("siren"),
                    "address": etab.get("adresse", {}).get("libelle_voie"),
                    "postal_code": etab.get("adresse", {}).get("code_postal"),
                    "city": etab.get("adresse", {}).get("libelle_commune"),
                    "naf": etab.get("activite_principale"),
                }
                triples.extend(
                    self.add_entity(
                        "establishment", siret, etab_props, source="sirene_api", confidence=0.95
                    )
                )

        logger.info(f"Populated KG from SIRENE: {len(triples)} triples")
        return triples
