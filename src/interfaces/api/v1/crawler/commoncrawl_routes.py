"""Common Crawl Intelligence API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from src.collector.collectors.api.commoncrawl import CommonCrawlCollector

router = APIRouter(prefix="/commoncrawl", tags=["commoncrawl"])


class CrawlIntelRequest(BaseModel):
    """Request for Common Crawl analysis."""

    code_dept: str | None = None
    max_enterprises: int = 10


class SingleAnalysisRequest(BaseModel):
    """Request for single enterprise analysis."""

    siret: str
    nom: str
    site_web: str
    naf: str = ""
    code_dept: str | None = None
    months_back: int = 12


class CrawlIntelResponse(BaseModel):
    """Response from Common Crawl analysis."""

    success: bool
    signals_count: int
    enterprises_analyzed: int
    signals: list[dict[str, Any]]


@router.post("/analyze", response_model=CrawlIntelResponse)
async def analyze_department(request: CrawlIntelRequest) -> CrawlIntelResponse:
    """Analyze enterprises in a department using Common Crawl archives."""
    collector = CommonCrawlCollector(
        max_enterprises=request.max_enterprises,
    )

    try:
        signals = await collector.run(code_dept=request.code_dept)
        return CrawlIntelResponse(
            success=True,
            signals_count=len(signals),
            enterprises_analyzed=request.max_enterprises,
            signals=[s.to_dict() for s in signals],
        )
    except Exception as e:
        logger.error(f"CrawlIntel analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await collector.close()


@router.post("/analyze/single", response_model=CrawlIntelResponse)
async def analyze_single(request: SingleAnalysisRequest) -> CrawlIntelResponse:
    """Analyze a single enterprise using Common Crawl archives."""
    collector = CommonCrawlCollector(
        months_back=request.months_back,
    )

    try:
        signals = await collector.collect_single(
            siret=request.siret,
            nom=request.nom,
            site_web=request.site_web,
            naf=request.naf,
            code_dept=request.code_dept,
        )
        return CrawlIntelResponse(
            success=True,
            signals_count=len(signals),
            enterprises_analyzed=1,
            signals=[s.to_dict() for s in signals],
        )
    except Exception as e:
        logger.error(f"CrawlIntel single analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await collector.close()


@router.get("/health")
async def crawlintel_health() -> dict[str, Any]:
    """Check Common Crawl adapter health."""
    from src.infrastructure.datasources.adapters.commoncrawl import CommonCrawlAdapter

    adapter = CommonCrawlAdapter()
    try:
        healthy = await adapter.health_check()
        return {
            "status": "healthy" if healthy else "unhealthy",
            "cdx_api": "reachable" if healthy else "unreachable",
        }
    finally:
        await adapter.close()
