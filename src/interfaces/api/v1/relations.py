"""Relations API -- graph exploration, coverage analysis, gap detection, what-if simulation."""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response
from loguru import logger

from src.application.services.ecosystem_score_service import compute_ecosystem_score
from src.application.services.network_analytics_service import (
    compute_network_analytics,
    get_timeline,
)
from src.application.services.relation_service import RelationService
from src.interfaces.api.v1.relations_schemas import (
    CoverageScore,
    DiscoverRequest,
    EcosystemScoreResponse,
    GapsReport,
    NetworkAnalyticsResponse,
    RelationGraphResponse,
    TimelineResponse,
    WhatIfRequest,
    WhatIfResponse,
)

router = APIRouter(prefix="/api/v1/investigation/relations", tags=["Relations"])

_service = RelationService()


# -----------------------------------------------------------------------
# IMPORTANT: Static paths MUST come before dynamic catch-all paths.
# FastAPI matches routes in declaration order; /{department_code} would
# swallow /coverage, /gaps, /discover if it appeared first.
# -----------------------------------------------------------------------


@router.get("/all", response_model=RelationGraphResponse)
async def get_all_relations(
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    types: str | None = Query(None, description="Comma-separated actor types"),
):
    """Get the full relation graph across ALL departments (cross-department view)."""
    actor_types = types.split(",") if types else None
    return await _service.get_graph(None, min_confidence, actor_types)


@router.get("/analytics/cross-dept", response_model=NetworkAnalyticsResponse)
async def get_cross_dept_analytics():
    """Compute cross-department network analytics."""
    logger.info("Computing cross-department network analytics")
    result = await compute_network_analytics(None)
    if "error" in result:
        return JSONResponse(status_code=404, content={"detail": result["error"]})
    return result


@router.get("/coverage/{department_code}", response_model=CoverageScore)
async def get_coverage_score(department_code: str):
    """Get the coverage breakdown: % structural, % inferred, % hypothetical."""
    return await _service.get_coverage(department_code)


@router.get("/gaps/{department_code}", response_model=GapsReport)
async def get_gaps_report(department_code: str):
    """Get the gap report -- what we SHOULD detect but cannot yet."""
    return await _service.get_gaps(department_code)


@router.post("/discover")
async def discover_relations(req: DiscoverRequest):
    """Launch full relation discovery (L1 extractors + L2 inferrers + L3 predictors)."""
    logger.info(
        "Discovering relations for dept {} with sources {}",
        req.department_code,
        req.sources,
    )
    return await _service.discover(req.department_code, req.sources)


@router.post("/what-if", response_model=WhatIfResponse)
async def simulate_whatif(req: WhatIfRequest):
    """Simulate what happens if an enterprise fails (cascade analysis)."""
    logger.info(
        "What-if simulation: {} in dept {}",
        req.actor_external_id,
        req.department_code,
    )
    result = await _service.whatif(req.actor_external_id, req.department_code, req.max_depth)
    if "error" in result:
        return JSONResponse(status_code=404, content={"detail": result["error"]})
    return result


@router.get("/ecosystem/{department_code}", response_model=EcosystemScoreResponse)
async def get_ecosystem_score(department_code: str):
    """Compute ecosystem maturity score for a department (6 dimensions)."""
    logger.info("Ecosystem score requested for dept {}", department_code)
    result = await compute_ecosystem_score(department_code)
    return result


@router.get("/export/{department_code}")
async def export_relations(
    department_code: str,
    format: str = Query("json", description="Export format: json, csv, or graphml"),
):
    """Export the full relation graph for download."""
    result = await _service.export_graph(department_code, format)
    if format == "graphml":
        return Response(
            content=result,
            media_type="application/xml",
            headers={
                "Content-Disposition": f"attachment; filename=relations-{department_code}.graphml"
            },
        )
    return result


@router.get("/analytics/{department_code}/timeline", response_model=TimelineResponse)
async def get_analytics_timeline(
    department_code: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Get historical network snapshots for trend analysis."""
    return await get_timeline(department_code, limit)


@router.get("/analytics/{department_code}", response_model=NetworkAnalyticsResponse)
async def get_network_analytics(department_code: str):
    """Compute network analytics: centrality, communities, resilience, structural holes."""
    logger.info("Computing network analytics for dept {}", department_code)
    result = await compute_network_analytics(department_code)
    if "error" in result:
        return JSONResponse(status_code=404, content={"detail": result["error"]})
    return result


@router.get("/actor/{actor_id}")
async def get_actor_relations(
    actor_id: str,
    depth: int = Query(1, ge=1, le=3),
):
    """Get relations centered on a specific actor (ego-graph)."""
    return {
        "actor_id": actor_id,
        "depth": depth,
        "nodes": [],
        "links": [],
        "message": "Ego-graph: disponible via what-if",
    }


@router.get("/{department_code}", response_model=RelationGraphResponse)
async def get_relation_graph(
    department_code: str,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    types: str | None = Query(None, description="Comma-separated actor types"),
    max_links: int = Query(1500, ge=100, le=10000, description="Max edges returned"),
):
    """Get the full relation graph for a department, formatted for D3.js."""
    actor_types = types.split(",") if types else None
    return await _service.get_graph(department_code, min_confidence, actor_types, max_links)
