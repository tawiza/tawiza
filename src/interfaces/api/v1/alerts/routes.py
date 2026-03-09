"""Alerts API routes."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.application.services.alert_service import (
    AlertSeverity,
    AlertStatus,
    AlertType,
    get_alert_service,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertResponse(BaseModel):
    """Alert response model."""
    id: str
    type: str
    severity: str
    title: str
    description: str
    territory: str | None
    sector: str | None
    created_at: str
    status: str


class AlertsListResponse(BaseModel):
    """List of alerts."""
    alerts: list[AlertResponse]
    total: int


class AlertStatsResponse(BaseModel):
    """Alert statistics."""
    total: int
    new: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    rules_count: int


@router.get("/", response_model=AlertsListResponse)
async def list_alerts(
    status: str | None = None,
    alert_type: str | None = None,
    territory: str | None = None,
    limit: int = 100,
) -> AlertsListResponse:
    """List alerts with optional filters."""
    service = get_alert_service()

    status_enum = AlertStatus(status) if status else None
    type_enum = AlertType(alert_type) if alert_type else None

    alerts = service.get_alerts(
        status=status_enum,
        alert_type=type_enum,
        territory=territory,
        limit=limit,
    )

    return AlertsListResponse(
        alerts=[
            AlertResponse(
                id=a.id,
                type=a.type.value,
                severity=a.severity.value,
                title=a.title,
                description=a.description,
                territory=a.territory,
                sector=a.sector,
                created_at=a.created_at.isoformat(),
                status=a.status.value,
            )
            for a in alerts
        ],
        total=len(alerts),
    )


@router.get("/stats", response_model=AlertStatsResponse)
async def get_stats() -> AlertStatsResponse:
    """Get alert statistics."""
    service = get_alert_service()
    stats = service.get_stats()
    return AlertStatsResponse(**stats)


@router.post("/{alert_id}/read")
async def mark_read(alert_id: str) -> dict[str, Any]:
    """Mark an alert as read."""
    service = get_alert_service()
    success = service.mark_read(alert_id)
    return {"success": success}


@router.post("/{alert_id}/archive")
async def archive_alert(alert_id: str) -> dict[str, Any]:
    """Archive an alert."""
    service = get_alert_service()
    success = service.archive(alert_id)
    return {"success": success}


@router.get("/types")
async def list_types() -> list[str]:
    """List available alert types."""
    return [t.value for t in AlertType]


@router.get("/severities")
async def list_severities() -> list[str]:
    """List available severities."""
    return [s.value for s in AlertSeverity]
