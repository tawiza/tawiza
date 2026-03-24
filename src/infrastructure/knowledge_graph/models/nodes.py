"""Node models for Neo4j property graph."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class BaseNode:
    """Base class for Neo4j nodes."""

    def to_properties(self) -> dict[str, Any]:
        """Convert to Cypher properties dict (exclude None values)."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def merge_query(self) -> str:
        """Generate MERGE Cypher query. Override in subclasses."""
        raise NotImplementedError


@dataclass
class Company(BaseNode):
    """Company node (:Company)."""

    siren: str
    name: str | None = None
    legal_form: str | None = None
    naf_code: str | None = None
    creation_date: str | None = None
    employee_count: str | None = None
    capital: int | None = None

    def merge_query(self) -> str:
        return """
        MERGE (c:Company {siren: $siren})
        SET c += $props
        RETURN c
        """


@dataclass
class Establishment(BaseNode):
    """Establishment node (:Establishment)."""

    siret: str
    siren: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    naf_code: str | None = None
    is_headquarters: bool = False
    creation_date: str | None = None

    def merge_query(self) -> str:
        return """
        MERGE (e:Establishment {siret: $siret})
        SET e += $props
        RETURN e
        """


@dataclass
class Territory(BaseNode):
    """Territory node (:Territory)."""

    code: str
    name: str | None = None
    type: str = "commune"  # commune, departement, region
    population: int | None = None

    def merge_query(self) -> str:
        return """
        MERGE (t:Territory {code: $code})
        SET t += $props
        RETURN t
        """


@dataclass
class Sector(BaseNode):
    """Sector/NAF node (:Sector)."""

    naf_code: str
    label: str | None = None
    level: int = 5  # NAF hierarchy level 1-5

    def merge_query(self) -> str:
        return """
        MERGE (s:Sector {naf_code: $naf_code})
        SET s += $props
        RETURN s
        """
