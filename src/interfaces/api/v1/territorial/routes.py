"""
Territorial Analysis API Routes.

Provides endpoints for territorial economic metrics and signal detection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/territorial", tags=["territorial"])


# ============================================================================
# Response Models
# ============================================================================


class TerritoryMetricsResponse(BaseModel):
    """Response model for territory metrics."""

    territory_code: str
    territory_name: str
    period_days: int
    metrics: dict[str, Any]
    computed: dict[str, Any]  # Includes vitality_breakdown dict


class TerritoryComparisonResponse(BaseModel):
    """Response model for territory comparison."""

    territories: list[dict[str, Any]]
    generated_at: str


class SignalResponse(BaseModel):
    """Response model for detected signals."""

    territory_code: str
    territory_name: str
    signals: list[dict[str, Any]]
    total_signals: int


# ============================================================================
# Dependencies
# ============================================================================


def get_metrics_collector():
    """Get or create the metrics collector instance."""
    from src.infrastructure.agents.tajine.territorial.metrics_collector import (
        TerritorialMetricsCollector,
    )
    from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter
    from src.infrastructure.datasources.adapters.sirene import SireneAdapter

    # France Travail est optionnel (nécessite OAuth2 credentials)
    france_travail_adapter = None
    try:
        from src.infrastructure.datasources.adapters.france_travail import FranceTravailAdapter

        adapter = FranceTravailAdapter()
        if adapter.has_credentials:
            france_travail_adapter = adapter
    except Exception:
        pass  # France Travail non disponible

    # INSEE est optionnel (nécessite OAuth2 credentials)
    insee_adapter = None
    try:
        from src.infrastructure.datasources.adapters.insee_local import INSEELocalAdapter

        adapter = INSEELocalAdapter()
        if adapter._client_id and adapter._client_secret:
            insee_adapter = adapter
    except Exception:
        pass  # INSEE non disponible

    # DVF est gratuit (pas d'auth)
    dvf_adapter = None
    try:
        from src.infrastructure.datasources.adapters.dvf import DVFAdapter

        dvf_adapter = DVFAdapter()
    except Exception:
        pass  # DVF non disponible

    return TerritorialMetricsCollector(
        sirene_adapter=SireneAdapter(),
        bodacc_adapter=BodaccAdapter(),
        france_travail_adapter=france_travail_adapter,
        dvf_adapter=dvf_adapter,
        insee_adapter=insee_adapter,
    )


def get_signal_detector():
    """Get or create the signal detector instance."""
    from src.infrastructure.agents.tajine.territorial.signal_detector import create_signal_detector

    return create_signal_detector()


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/metrics/{territory_code}",
    response_model=TerritoryMetricsResponse,
    summary="Get territory economic metrics",
    description="Returns economic metrics (creations, closures, vitality index) for a territory",
)
async def get_territory_metrics(
    territory_code: str,
    territory_name: str = Query(None, description="Territory name (optional)"),
    period_months: int = Query(1, ge=1, le=12, description="Analysis period in months"),
) -> TerritoryMetricsResponse:
    """
    Get economic metrics for a specific territory.

    Args:
        territory_code: INSEE code (department: 2 digits, commune: 5 digits)
        territory_name: Human-readable name
        period_months: Analysis period (1-12 months)
    """
    try:
        collector = get_metrics_collector()
        name = territory_name or f"Territory {territory_code}"

        metrics = await collector.collect_metrics(
            territory_code=territory_code,
            territory_name=name,
            period_months=period_months,
        )

        return TerritoryMetricsResponse(
            territory_code=territory_code,
            territory_name=name,
            period_days=period_months * 30,
            metrics={
                "creations": metrics.creations_count,
                "closures": metrics.closures_count,
                "collective_procedures": metrics.collective_procedures_count,
                "modifications": metrics.modifications_count,
                "sales": metrics.sales_count,
                "total_establishments": metrics.total_establishments,
                "job_offers": metrics.job_offers_count,
                "job_seekers": metrics.job_seekers_count,
                "population": metrics.population,
                "unemployment_rate": metrics.unemployment_rate,
                "real_estate_transactions": metrics.real_estate_transactions,
                "avg_price_sqm": metrics.avg_price_sqm,
            },
            computed={
                "creation_rate": round(metrics.creation_rate * 100, 2),
                "closure_rate": round(metrics.closure_rate * 100, 2),
                "creation_variation": round(metrics.creation_variation * 100, 2),
                "net_creation": float(metrics.net_creation),
                "vitality_index": round(metrics.vitality_index, 1),
                "vitality_breakdown": metrics.vitality_breakdown,
                "job_offers_variation": round(metrics.job_offers_variation * 100, 2),
                "tension_ratio": round(metrics.tension_ratio, 2),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/compare",
    response_model=TerritoryComparisonResponse,
    summary="Compare multiple territories",
    description="Returns comparative metrics for multiple departments",
)
async def compare_territories(
    departments: str = Query(
        "75,69,13,33,59",
        description="Comma-separated department codes",
    ),
    period_months: int = Query(1, ge=1, le=12),
) -> TerritoryComparisonResponse:
    """
    Compare economic metrics across multiple territories.
    """
    from datetime import datetime

    # Mapping des noms de départements
    dept_names = {
        "01": "Ain",
        "02": "Aisne",
        "03": "Allier",
        "04": "Alpes-de-Haute-Provence",
        "05": "Hautes-Alpes",
        "06": "Alpes-Maritimes",
        "07": "Ardèche",
        "08": "Ardennes",
        "09": "Ariège",
        "10": "Aube",
        "11": "Aude",
        "12": "Aveyron",
        "13": "Bouches-du-Rhône",
        "14": "Calvados",
        "15": "Cantal",
        "16": "Charente",
        "17": "Charente-Maritime",
        "18": "Cher",
        "19": "Corrèze",
        "21": "Côte-d'Or",
        "22": "Côtes-d'Armor",
        "23": "Creuse",
        "24": "Dordogne",
        "25": "Doubs",
        "26": "Drôme",
        "27": "Eure",
        "28": "Eure-et-Loir",
        "29": "Finistère",
        "30": "Gard",
        "31": "Haute-Garonne",
        "32": "Gers",
        "33": "Gironde",
        "34": "Hérault",
        "35": "Ille-et-Vilaine",
        "36": "Indre",
        "37": "Indre-et-Loire",
        "38": "Isère",
        "39": "Jura",
        "40": "Landes",
        "41": "Loir-et-Cher",
        "42": "Loire",
        "43": "Haute-Loire",
        "44": "Loire-Atlantique",
        "45": "Loiret",
        "46": "Lot",
        "47": "Lot-et-Garonne",
        "48": "Lozère",
        "49": "Maine-et-Loire",
        "50": "Manche",
        "51": "Marne",
        "52": "Haute-Marne",
        "53": "Mayenne",
        "54": "Meurthe-et-Moselle",
        "55": "Meuse",
        "56": "Morbihan",
        "57": "Moselle",
        "58": "Nièvre",
        "59": "Nord",
        "60": "Oise",
        "61": "Orne",
        "62": "Pas-de-Calais",
        "63": "Puy-de-Dôme",
        "64": "Pyrénées-Atlantiques",
        "65": "Hautes-Pyrénées",
        "66": "Pyrénées-Orientales",
        "67": "Bas-Rhin",
        "68": "Haut-Rhin",
        "69": "Rhône",
        "70": "Haute-Saône",
        "71": "Saône-et-Loire",
        "72": "Sarthe",
        "73": "Savoie",
        "74": "Haute-Savoie",
        "75": "Paris",
        "76": "Seine-Maritime",
        "77": "Seine-et-Marne",
        "78": "Yvelines",
        "79": "Deux-Sèvres",
        "80": "Somme",
        "81": "Tarn",
        "82": "Tarn-et-Garonne",
        "83": "Var",
        "84": "Vaucluse",
        "85": "Vendée",
        "86": "Vienne",
        "87": "Haute-Vienne",
        "88": "Vosges",
        "89": "Yonne",
        "90": "Territoire de Belfort",
        "91": "Essonne",
        "92": "Hauts-de-Seine",
        "93": "Seine-Saint-Denis",
        "94": "Val-de-Marne",
        "95": "Val-d'Oise",
    }

    collector = get_metrics_collector()
    codes = [c.strip() for c in departments.split(",")]

    results = []
    for code in codes:
        try:
            name = dept_names.get(code, f"Département {code}")
            metrics = await collector.collect_metrics(code, name, period_months)
            results.append(
                {
                    "code": code,
                    "name": name,
                    "creations": metrics.creations_count,
                    "closures": metrics.closures_count,
                    "procedures": metrics.collective_procedures_count,
                    "net_creation": metrics.net_creation,
                    "vitality_index": round(metrics.vitality_index, 1),
                    "job_offers": metrics.job_offers_count,
                    "unemployment_rate": metrics.unemployment_rate,
                    "real_estate_tx": metrics.real_estate_transactions,
                    "avg_price_sqm": round(metrics.avg_price_sqm, 0),
                }
            )
        except Exception as e:
            results.append(
                {
                    "code": code,
                    "name": dept_names.get(code, f"Département {code}"),
                    "error": str(e),
                }
            )

    # Trier par vitalité décroissante
    results.sort(key=lambda x: x.get("vitality_index", 0), reverse=True)

    return TerritoryComparisonResponse(
        territories=results,
        generated_at=datetime.utcnow().isoformat(),
    )


@router.get(
    "/signals/{territory_code}",
    response_model=SignalResponse,
    summary="Detect economic signals",
    description="Detects micro-signals (crisis, growth, mutation) for a territory",
)
async def detect_signals(
    territory_code: str,
    territory_name: str = Query(None),
    period_months: int = Query(12, ge=1, le=24),
) -> SignalResponse:
    """
    Detect economic micro-signals for a territory.
    """
    try:
        detector = get_signal_detector()
        name = territory_name or f"Territory {territory_code}"

        signals = await detector.detect_signals(
            territory_code=territory_code,
            territory_name=name,
            period_months=period_months,
        )

        return SignalResponse(
            territory_code=territory_code,
            territory_name=name,
            signals=[s.to_dict() for s in signals],
            total_signals=len(signals),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/history/{territory_code}",
    summary="Get historical metrics",
    description="Returns historical metrics for trend analysis",
)
async def get_history(
    territory_code: str,
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
) -> dict[str, Any]:
    """Get historical metrics for a territory."""
    from src.infrastructure.persistence.territorial_history import get_history_store

    store = get_history_store()
    history = store.get_history(territory_code, days=days)

    return {
        "territory_code": territory_code,
        "days": days,
        "records": len(history),
        "history": [h.to_dict() for h in history],
    }


@router.get(
    "/trends/{territory_code}",
    summary="Get trends",
    description="Returns vitality trends over different periods",
)
async def get_trends(
    territory_code: str,
) -> dict[str, Any]:
    """Get vitality trends for a territory."""
    from src.infrastructure.persistence.territorial_history import get_history_store

    store = get_history_store()
    latest = store.get_latest(territory_code)
    trends = store.get_trends(territory_code, periods=[7, 30, 90])

    return {
        "territory_code": territory_code,
        "current_vitality": latest.vitality_index if latest else None,
        "last_updated": latest.collected_at.isoformat() if latest else None,
        "trends": trends,
    }


@router.get(
    "/ranking",
    summary="Get national ranking",
    description="Returns all territories ranked by vitality",
)
async def get_ranking(
    limit: int = Query(20, ge=1, le=101),
) -> dict[str, Any]:
    """Get national ranking of territories by vitality."""
    from datetime import datetime

    from src.infrastructure.persistence.territorial_history import get_history_store

    store = get_history_store()
    all_latest = store.get_all_latest()

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total_territories": len(all_latest),
        "ranking": [
            {
                "rank": i + 1,
                "code": m.territory_code,
                "name": m.territory_name,
                "vitality_index": round(m.vitality_index, 1),
                "net_creation": m.net_creation,
                "unemployment_rate": m.unemployment_rate,
            }
            for i, m in enumerate(all_latest[:limit])
        ],
    }


@router.post(
    "/collect",
    summary="Trigger data collection",
    description="Manually trigger collection for specific departments",
)
async def trigger_collection(
    departments: str = Query("75,69,13,33,59", description="Comma-separated department codes"),
) -> dict[str, Any]:
    """Trigger manual collection for specified departments."""
    from src.application.jobs.territorial_collector import collect_selected_departments

    codes = [c.strip() for c in departments.split(",")]
    results = await collect_selected_departments(codes)

    return {
        "status": "completed",
        "departments_requested": len(codes),
        **results,
    }


@router.get(
    "/signals/{territory_code}",
    summary="Predictive signals",
    description="Detects early warning signals and opportunities for a territory",
)
async def get_predictive_signals(
    territory_code: str,
    territory_name: str = Query(None),
    include_sectors: bool = Query(True, description="Include sector analysis"),
) -> dict[str, Any]:
    """Detect predictive signals for a territory."""
    from src.infrastructure.agents.tajine.territorial.metrics_collector import (
        TerritorialMetricsCollector,
    )
    from src.infrastructure.agents.tajine.territorial.predictive_signals import get_signal_detector
    from src.infrastructure.agents.tajine.territorial.sector_analyzer import get_sector_analyzer
    from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter
    from src.infrastructure.datasources.adapters.sirene import SireneAdapter

    name = territory_name or f"Département {territory_code}"

    # Collecter les métriques actuelles
    collector = TerritorialMetricsCollector(
        sirene_adapter=SireneAdapter(),
        bodacc_adapter=BodaccAdapter(),
    )
    metrics = await collector.collect_metrics(territory_code, name, period_months=1)

    # Analyse sectorielle si demandée
    sector_analysis = None
    if include_sectors:
        analyzer = get_sector_analyzer()
        bodacc = BodaccAdapter()
        sector_result = await analyzer.analyze_territory(territory_code, name, bodacc, limit=200)
        sector_analysis = sector_result.to_dict()

    # Détecter les signaux
    detector = get_signal_detector()
    signals = await detector.detect_signals(
        territory_code=territory_code,
        territory_name=name,
        current_metrics={
            "creations_count": metrics.creations_count,
            "closures_count": metrics.closures_count,
            "modifications_count": metrics.modifications_count,
            "procedures": metrics.collective_procedures_count,
            "unemployment_rate": metrics.unemployment_rate,
            "vitality_index": metrics.vitality_index,
        },
        sector_analysis=sector_analysis,
    )

    # Grouper par sévérité
    by_severity = {"critical": [], "alert": [], "warning": [], "info": []}
    for s in signals:
        by_severity[s.severity.value].append(s.to_dict())

    return {
        "territory_code": territory_code,
        "territory_name": name,
        "vitality_index": round(metrics.vitality_index, 1),
        "total_signals": len(signals),
        "signals_by_severity": by_severity,
        "signals": [s.to_dict() for s in signals],
        "analyzed_at": datetime.utcnow().isoformat(),
    }


@router.get(
    "/alerts",
    summary="National alerts",
    description="Returns active alerts across all monitored territories",
)
async def get_national_alerts(
    min_severity: str = Query(
        "warning", description="Minimum severity: info, warning, alert, critical"
    ),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get national-level alerts from all territories."""
    from src.infrastructure.agents.tajine.territorial.predictive_signals import (
        SignalSeverity,
        get_signal_detector,
    )
    from src.infrastructure.persistence.territorial_history import get_history_store

    store = get_history_store()
    detector = get_signal_detector()

    # Récupérer tous les territoires avec historique
    all_latest = store.get_all_latest()

    all_signals = []
    severity_filter = {
        "info": [
            SignalSeverity.INFO,
            SignalSeverity.WARNING,
            SignalSeverity.ALERT,
            SignalSeverity.CRITICAL,
        ],
        "warning": [SignalSeverity.WARNING, SignalSeverity.ALERT, SignalSeverity.CRITICAL],
        "alert": [SignalSeverity.ALERT, SignalSeverity.CRITICAL],
        "critical": [SignalSeverity.CRITICAL],
    }.get(min_severity, [SignalSeverity.WARNING, SignalSeverity.ALERT, SignalSeverity.CRITICAL])

    for metrics in all_latest:
        signals = await detector.detect_signals(
            territory_code=metrics.territory_code,
            territory_name=metrics.territory_name,
            current_metrics={
                "creations_count": metrics.creations,
                "closures_count": metrics.closures,
                "modifications_count": metrics.modifications,
                "procedures": metrics.procedures,
                "unemployment_rate": metrics.unemployment_rate,
                "vitality_index": metrics.vitality_index,
            },
        )

        # Filtrer par sévérité
        for s in signals:
            if s.severity in severity_filter:
                all_signals.append(s)

    # Trier par sévérité puis par date
    severity_order = {
        SignalSeverity.CRITICAL: 0,
        SignalSeverity.ALERT: 1,
        SignalSeverity.WARNING: 2,
        SignalSeverity.INFO: 3,
    }
    all_signals.sort(key=lambda s: (severity_order[s.severity], s.detected_at), reverse=False)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "territories_analyzed": len(all_latest),
        "total_alerts": len(all_signals),
        "min_severity": min_severity,
        "alerts": [s.to_dict() for s in all_signals[:limit]],
    }


@router.get(
    "/sectors/{territory_code}",
    summary="Sector analysis",
    description="Returns sector breakdown (NAF) for a territory",
)
async def get_sectors(
    territory_code: str,
    territory_name: str = Query(None),
    limit: int = Query(200, ge=50, le=1000),
) -> dict[str, Any]:
    """Get sector analysis for a territory."""
    from src.infrastructure.agents.tajine.territorial.sector_analyzer import get_sector_analyzer
    from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter

    analyzer = get_sector_analyzer()
    bodacc = BodaccAdapter()

    name = territory_name or f"Département {territory_code}"
    analysis = await analyzer.analyze_territory(
        territory_code=territory_code,
        territory_name=name,
        bodacc_adapter=bodacc,
        limit=limit,
    )

    return analysis.to_dict()


@router.get(
    "/analyze/{territory_code}",
    summary="TAJINE narrative analysis",
    description="Generates AI-powered narrative analysis of a territory",
)
async def get_narrative_analysis(
    territory_code: str,
    territory_name: str = Query(None),
    use_llm: bool = Query(True, description="Use LLM for analysis (requires Ollama)"),
) -> dict[str, Any]:
    """Generate TAJINE narrative analysis."""
    from src.infrastructure.agents.tajine.territorial.metrics_collector import (
        TerritorialMetricsCollector,
    )
    from src.infrastructure.agents.tajine.territorial.narrative_analyzer import (
        get_narrative_analyzer,
    )
    from src.infrastructure.agents.tajine.territorial.predictive_signals import get_signal_detector
    from src.infrastructure.agents.tajine.territorial.sector_analyzer import get_sector_analyzer
    from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter
    from src.infrastructure.datasources.adapters.sirene import SireneAdapter

    name = territory_name or f"Département {territory_code}"

    # Collecter les métriques
    collector = TerritorialMetricsCollector(
        sirene_adapter=SireneAdapter(),
        bodacc_adapter=BodaccAdapter(),
    )
    metrics = await collector.collect_metrics(territory_code, name, period_months=1)

    # Détecter les signaux
    detector = get_signal_detector()
    signals = await detector.detect_signals(
        territory_code,
        name,
        {
            "creations_count": metrics.creations_count,
            "closures_count": metrics.closures_count,
            "modifications_count": metrics.modifications_count,
            "unemployment_rate": metrics.unemployment_rate,
            "vitality_index": metrics.vitality_index,
        },
    )

    # Analyse sectorielle
    sector_analyzer = get_sector_analyzer()
    bodacc = BodaccAdapter()
    sectors = await sector_analyzer.analyze_territory(territory_code, name, bodacc, limit=100)

    # Générer l'analyse narrative
    analyzer = get_narrative_analyzer()
    if not use_llm:
        analyzer._ollama_client = False  # Force rule-based

    analysis = await analyzer.analyze(
        territory_code=territory_code,
        territory_name=name,
        metrics={
            "vitality_index": metrics.vitality_index,
            "creations": metrics.creations_count,
            "closures": metrics.closures_count,
            "net_creation": metrics.net_creation,
            "unemployment_rate": metrics.unemployment_rate,
            "job_offers": metrics.job_offers_count,
            "procedures": metrics.collective_procedures_count,
        },
        signals=[s.to_dict() for s in signals],
        sectors=sectors.to_dict(),
    )

    return {
        **analysis.to_dict(),
        "metrics_summary": {
            "vitality_index": round(metrics.vitality_index, 1),
            "net_creation": metrics.net_creation,
            "unemployment_rate": metrics.unemployment_rate,
        },
    }


@router.get(
    "/reports/daily",
    summary="Daily flash report",
    description="Generates daily territorial flash report",
)
async def get_daily_report(
    format: str = Query("json", description="Output format: json or markdown"),
) -> dict[str, Any]:
    """Generate daily flash report."""
    from src.application.services.territorial_reports import get_report_generator

    generator = get_report_generator()
    report = await generator.generate_daily_flash()

    if format == "markdown":
        return {"markdown": report.to_markdown()}
    return report.to_dict()


@router.get(
    "/reports/weekly",
    summary="Weekly summary report",
    description="Generates weekly territorial summary",
)
async def get_weekly_report(
    format: str = Query("json", description="Output format: json or markdown"),
) -> dict[str, Any]:
    """Generate weekly summary report."""
    from src.application.services.territorial_reports import get_report_generator

    generator = get_report_generator()
    report = await generator.generate_weekly_summary()

    if format == "markdown":
        return {"markdown": report.to_markdown()}
    return report.to_dict()


@router.get(
    "/health",
    summary="Check territorial API health",
)
async def health_check() -> dict[str, str]:
    """Health check for territorial API."""
    return {"status": "healthy", "service": "territorial-api"}
