"""Pydantic schemas for the Relations API.

Defines request/response models for the actor-relation graph:
- Actor and Relation CRUD responses (ORM-backed)
- D3.js force-graph payloads (GraphNode / GraphLink)
- Coverage scoring and gap analysis reports
- Discovery request for triggering relation extraction
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# ORM-backed response models
# ---------------------------------------------------------------------------


class ActorResponse(BaseModel):
    """Single actor (enterprise, institution, person, etc.)."""

    id: UUID
    type: str = Field(..., description="Actor type (enterprise, institution, person, ...)")
    external_id: str = Field(..., description="External identifier (SIREN, SIRET, RNA, ...)")
    name: str = Field(..., description="Display name")
    department_code: str | None = None
    metadata: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class RelationSourceResponse(BaseModel):
    """Provenance of a single relation (which extractor contributed)."""

    source_type: str = Field(
        ..., description="Extractor that produced this link (sirene, bodacc, ...)"
    )
    source_ref: str | None = Field(
        default=None, description="Reference within the source (e.g. BODACC announcement id)"
    )
    contributed_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence contributed by this source"
    )

    model_config = ConfigDict(from_attributes=True)


class RelationResponse(BaseModel):
    """Full relation between two actors, with nested source provenance."""

    id: UUID
    source_actor: ActorResponse
    target_actor: ActorResponse
    relation_type: str = Field(
        ..., description="Relation category (structural, inferred, hypothetical)"
    )
    subtype: str = Field(
        ..., description="Relation subtype (subsidiary, supplier, competitor, ...)"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Aggregated confidence score")
    weight: float | None = Field(default=None, description="Optional weight for graph layout")
    evidence: dict | None = Field(default=None, description="Raw evidence payload from extractors")
    sources: list[RelationSourceResponse] = Field(
        default_factory=list, description="List of sources that contributed to this relation"
    )
    detected_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# D3.js force-graph payloads
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    """Node for D3 force graph rendering."""

    id: str = Field(..., description="Unique node identifier (actor UUID as string)")
    label: str = Field(..., description="Display label")
    type: str = Field(..., description="Actor type for color coding")
    external_id: str = Field(..., description="External identifier for tooltip")
    department_code: str | None = None
    size: float = Field(
        default=10.0, ge=1.0, description="Node radius (proportional to connections)"
    )
    metadata: dict | None = None


class GraphLink(BaseModel):
    """Link (edge) for D3 force graph rendering."""

    source: str = Field(..., description="Source node id")
    target: str = Field(..., description="Target node id")
    relation_type: str = Field(..., description="Relation category")
    subtype: str = Field(..., description="Relation subtype")
    confidence: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, description="Edge thickness / force weight")


class RelationGraphResponse(BaseModel):
    """Full graph response ready for D3.js rendering."""

    nodes: list[GraphNode]
    links: list[GraphLink]
    total_actors: int = Field(..., ge=0)
    total_relations: int = Field(..., ge=0)
    total_relations_unfiltered: int | None = Field(
        default=None,
        ge=0,
        description="Total relation count before max_links cap (None if no cap applied)",
    )


# ---------------------------------------------------------------------------
# Coverage scoring
# ---------------------------------------------------------------------------


class CoverageScore(BaseModel):
    """Breakdown of relation confidence levels for a territory."""

    total_relations: int = Field(..., ge=0)
    structural_count: int = Field(
        ..., ge=0, description="High-confidence (SIRENE/BODACC) relations"
    )
    structural_pct: float = Field(..., ge=0.0, le=100.0)
    inferred_count: int = Field(..., ge=0, description="ML/NLP inferred relations")
    inferred_pct: float = Field(..., ge=0.0, le=100.0)
    hypothetical_count: int = Field(
        ..., ge=0, description="Hypothetical / low-confidence relations"
    )
    hypothetical_pct: float = Field(..., ge=0.0, le=100.0)
    coverage_score: float = Field(
        ..., ge=0.0, le=1.0, description="Weighted coverage score (0 = blind, 1 = fully mapped)"
    )


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------


class GapItem(BaseModel):
    """A single detected gap in territorial relation coverage."""

    gap_type: str = Field(
        ..., description="Gap category (missing_source, low_coverage, stale_data, ...)"
    )
    description: str = Field(..., description="Human-readable explanation")
    affected_actors: int = Field(..., ge=0, description="Number of actors affected by this gap")
    potential_source: str = Field(..., description="Data source that could fill this gap")
    priority: str = Field(..., description="Priority level (high, medium, low)")


class AlgorithmicHonestyItem(BaseModel):
    """Transparency record for a single relation subtype."""

    relation_subtype: str = Field(..., description="Relation subtype (e.g., headquarter_in)")
    relation_type: str = Field(..., description="Level (structural, inferred, hypothetical)")
    count: int = Field(..., ge=0, description="Number of relations of this subtype")
    avg_confidence: float = Field(..., ge=0.0, le=1.0)
    min_confidence: float = Field(..., ge=0.0, le=1.0)
    max_confidence: float = Field(..., ge=0.0, le=1.0)
    method: str = Field(..., description="Detection method used")
    limitation: str = Field(..., description="Known limitations of this method")
    data_source: str = Field(..., description="Data source or model used")


class GapsReport(BaseModel):
    """Report of what we cannot yet detect for a given territory."""

    department_code: str
    total_gaps: int = Field(..., ge=0)
    gaps: list[GapItem]
    capability_matrix: list[dict] = Field(
        default_factory=list,
        description="Matrix of extractor capabilities vs. detected relation types",
    )
    algorithmic_honesty: list[AlgorithmicHonestyItem] = Field(
        default_factory=list,
        description="Transparency table: for each detected relation type, explains method, confidence, and limitations",
    )


# ---------------------------------------------------------------------------
# Discovery request
# ---------------------------------------------------------------------------


class DiscoverRequest(BaseModel):
    """Request to trigger relation discovery for a department."""

    department_code: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="French department code (e.g. '75', '2A', '974')",
    )
    sources: list[str] = Field(
        default=[
            "sirene",
            "bodacc",
            "boamp",
            "rna",
            "subventions",
            "ademe",
            "qualiopi",
            "ofgl",
            "dvf",
            "france_travail",
            "insee_local",
            "nature_juridique",
            "epci",
            "incubator",
            "poles",
            "territorial",
            "sirene_enrich",
            "sirene_dirigeants",
            "urssaf",
        ],
        description="Extractors to run (sirene, bodacc, boamp, rna, subventions, ademe, qualiopi, ofgl, dvf, france_travail, insee_local, nature_juridique, epci, incubator, poles, territorial, sirene_enrich, sirene_dirigeants, urssaf)",
    )
    depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Traversal depth (1 = direct relations only, 5 = deep graph)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"department_code": "75", "sources": ["sirene", "bodacc"], "depth": 2}
        }
    )


# ---------------------------------------------------------------------------
# What-If simulation
# ---------------------------------------------------------------------------


class WhatIfRequest(BaseModel):
    """Request for a what-if cascade simulation."""

    actor_external_id: str = Field(
        ...,
        description="External ID of the enterprise to simulate failure for (e.g. 'SIREN:123456789')",
    )
    department_code: str = Field(
        ..., min_length=1, max_length=10, description="Department code for context"
    )
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum cascade propagation depth")


class CascadePathItem(BaseModel):
    """Single affected actor in a cascade simulation."""

    actor_external_id: str
    actor_name: str
    actor_type: str
    depth: int = Field(..., ge=1, description="Cascade hop distance from source")
    cascade_probability: float = Field(..., ge=0.0, le=1.0)
    impact_score: float = Field(..., ge=0.0)
    estimated_headcount: int = Field(..., ge=0)
    via_relation: str = Field(..., description="Relation subtype that propagated the cascade")
    via_confidence: float = Field(..., ge=0.0, le=1.0)


class WhatIfResponse(BaseModel):
    """Result of a what-if cascade simulation."""

    source_actor: dict = Field(..., description="The failing enterprise details")
    department_code: str
    cascade_depth: int
    affected_actors: int = Field(..., ge=0)
    cascade_paths: list[CascadePathItem]
    total_impact_score: float = Field(..., ge=0.0)
    employment_at_risk: int = Field(..., ge=0, description="Estimated jobs at risk")


# ---------------------------------------------------------------------------
# Network Analytics
# ---------------------------------------------------------------------------


class GraphSummary(BaseModel):
    """Summary statistics for the network graph."""

    total_nodes: int
    total_edges: int
    density: float
    avg_clustering: float
    connected_components: int
    type_distribution: dict[str, int]


class ResilienceScore(BaseModel):
    """Composite resilience score with breakdown dimensions."""

    score: float = Field(..., ge=0.0, le=1.0, description="Composite resilience score")
    diversity: float = Field(..., description="Actor type diversity (Shannon entropy)")
    clustering: float = Field(..., description="Average clustering coefficient")
    density: float = Field(..., description="Graph density")
    robustness: float = Field(..., description="Robustness to hub removal")
    components_after_removal: int
    removed_hubs: list[str]


class CommunityDetail(BaseModel):
    """Detail of a single detected community (Louvain)."""

    id: int
    size: int
    composition: dict[str, int]
    dominant_type: str


class CriticalActor(BaseModel):
    """An actor identified as critical bridge in the network."""

    actor_external_id: str
    actor_name: str
    actor_type: str
    betweenness: float
    pagerank: float
    degree: int


class StructuralHole(BaseModel):
    """An actor occupying a structural hole (brokerage position)."""

    actor_external_id: str
    actor_name: str
    actor_type: str
    constraint: float
    brokerage_potential: float


class ShapleyEntry(BaseModel):
    """An actor with its Shapley value contribution to network cohesion."""

    actor_external_id: str
    actor_name: str
    actor_type: str
    shapley_value: float = Field(..., ge=0.0, le=1.0)


class RiskEntry(BaseModel):
    """An actor with its composite risk score."""

    actor_external_id: str
    actor_name: str
    actor_type: str
    risk_score: float = Field(..., ge=0.0, le=1.0)


class NetworkAnalyticsResponse(BaseModel):
    """Full network analytics response for a department."""

    department_code: str
    graph_summary: GraphSummary
    resilience: ResilienceScore
    communities: list[CommunityDetail]
    critical_actors: list[CriticalActor]
    structural_holes: list[StructuralHole]
    node_metrics: dict[str, dict]
    shapley_top: list[dict] = Field(
        default_factory=list,
        description="Top 10 actors by Shapley value (contribution to network cohesion)",
    )
    risk_ranking: list[dict] = Field(
        default_factory=list,
        description="Top 10 highest risk actors (composite BODACC + isolation + dependency score)",
    )


# ---------------------------------------------------------------------------
# Ecosystem maturity score
# ---------------------------------------------------------------------------


class EcosystemDimensionIndicators(BaseModel):
    """Free-form indicators for a single ecosystem dimension."""

    model_config = ConfigDict(extra="allow")


class EcosystemDimension(BaseModel):
    """A single dimension of the ecosystem maturity score."""

    name: str = Field(..., description="Machine name (e.g. tissu_economique)")
    label: str = Field(..., description="Human-readable label")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight in overall score")
    score: float = Field(..., ge=0.0, le=100.0, description="Score out of 100")
    max_score: float = Field(default=100.0, description="Maximum possible score")
    indicators: dict = Field(
        default_factory=dict, description="Dimension-specific indicator counts"
    )


class EcosystemScoreResponse(BaseModel):
    """Full ecosystem maturity score for a department."""

    department_code: str
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Composite score (0-100)")
    dimensions: list[EcosystemDimension]
    actor_counts: dict[str, int] = Field(default_factory=dict, description="Actor type -> count")
    relation_counts: dict[str, int] = Field(
        default_factory=dict, description="Relation subtype -> count"
    )
    total_actors: int = Field(..., ge=0)
    total_relations: int = Field(..., ge=0)
    recommendations: list[str] = Field(
        default_factory=list, description="Actionable recommendations"
    )


# ---------------------------------------------------------------------------
# Timeline snapshots
# ---------------------------------------------------------------------------


class TimelinePoint(BaseModel):
    """A single historical snapshot of network metrics."""

    timestamp: str = Field(..., description="ISO 8601 timestamp of the snapshot")
    total_actors: int
    total_relations: int
    l1_count: int = Field(..., description="Structural (L1) relations at snapshot time")
    l2_count: int = Field(..., description="Inferred (L2) relations at snapshot time")
    l3_count: int = Field(..., description="Hypothetical (L3) relations at snapshot time")
    coverage_score: float
    resilience_score: float
    density: float
    communities_count: int


class TimelineResponse(BaseModel):
    """Historical snapshots for trend analysis."""

    department_code: str
    total_snapshots: int
    points: list[TimelinePoint]
