"""Territorial History Service.

Collects and stores historical territorial data for real trend analysis.
Replaces synthetic trend generation with actual data.
"""

from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.models import TerritorialSnapshot, TerritorialTrend


class TerritorialHistoryService:
    """Service for managing territorial historical data."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_snapshot(
        self,
        territory_code: str,
        data: dict[str, Any],
        source: str = "api"
    ) -> TerritorialSnapshot:
        """Create a new territorial snapshot.

        Args:
            territory_code: Department or territory code
            data: Dictionary with indicator values
            source: Data source identifier

        Returns:
            Created snapshot
        """
        snapshot = TerritorialSnapshot(
            territory_code=territory_code,
            territory_name=data.get("territory_name"),
            snapshot_date=datetime.utcnow(),
            entreprises_count=data.get("entreprises_count"),
            entreprises_created=data.get("entreprises_created"),
            entreprises_closed=data.get("entreprises_closed"),
            population=data.get("population"),
            population_density=data.get("population_density"),
            unemployment_rate=data.get("unemployment_rate"),
            median_income=data.get("median_income"),
            real_estate_price_m2=data.get("real_estate_price_m2"),
            attractiveness_score=data.get("attractiveness_score"),
            infrastructure_score=data.get("infrastructure_score"),
            capital_humain_score=data.get("capital_humain_score"),
            environnement_eco_score=data.get("environnement_eco_score"),
            qualite_vie_score=data.get("qualite_vie_score"),
            accessibilite_score=data.get("accessibilite_score"),
            innovation_score=data.get("innovation_score"),
            extra_data=data.get("extra_data"),
            data_source=source,
        )

        self.session.add(snapshot)
        await self.session.commit()
        await self.session.refresh(snapshot)

        logger.info(f"Created snapshot for {territory_code}")
        return snapshot

    async def get_snapshots(
        self,
        territory_code: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100
    ) -> list[TerritorialSnapshot]:
        """Get historical snapshots for a territory.

        Args:
            territory_code: Territory code
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum results

        Returns:
            List of snapshots
        """
        query = select(TerritorialSnapshot).where(
            TerritorialSnapshot.territory_code == territory_code
        )

        if start_date:
            query = query.where(TerritorialSnapshot.snapshot_date >= start_date)
        if end_date:
            query = query.where(TerritorialSnapshot.snapshot_date <= end_date)

        query = query.order_by(TerritorialSnapshot.snapshot_date.desc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def compute_trends(
        self,
        territory_code: str,
        indicator: str,
        period: str = "12m"
    ) -> dict[str, Any]:
        """Compute trends from historical data.

        Args:
            territory_code: Territory code
            indicator: Indicator name (e.g., "entreprises_count")
            period: Time period (3m, 6m, 12m, 24m)

        Returns:
            Trend data with current, previous, change, and data points
        """
        months = {"3m": 3, "6m": 6, "12m": 12, "24m": 24}.get(period, 12)
        start_date = datetime.utcnow() - timedelta(days=months * 30)

        snapshots = await self.get_snapshots(
            territory_code,
            start_date=start_date,
            limit=months
        )

        if not snapshots:
            logger.warning(f"No historical data for {territory_code}/{indicator}")
            return self._empty_trend()

        # Extract indicator values
        data_points = []
        for snap in reversed(snapshots):  # Oldest first
            value = getattr(snap, indicator, None)
            if value is not None:
                data_points.append({
                    "date": snap.snapshot_date.isoformat(),
                    "value": value
                })

        if len(data_points) < 2:
            return self._empty_trend()

        current = data_points[-1]["value"]
        previous = data_points[0]["value"]
        change = ((current - previous) / previous * 100) if previous else 0

        return {
            "current": current,
            "previous": previous,
            "change": round(change, 2),
            "direction": "up" if change > 1 else "down" if change < -1 else "stable",
            "data_points": data_points,
            "period": period,
            "computed_at": datetime.utcnow().isoformat(),
            "is_real_data": True
        }

    def _empty_trend(self) -> dict[str, Any]:
        """Return empty trend structure."""
        return {
            "current": None,
            "previous": None,
            "change": 0,
            "direction": "unknown",
            "data_points": [],
            "is_real_data": False
        }

    async def get_or_compute_trends(
        self,
        territory_code: str,
        period: str = "12m"
    ) -> dict[str, Any]:
        """Get trends for all main indicators.

        Falls back to synthetic data if no history available,
        but marks it clearly as estimated.

        Args:
            territory_code: Territory code
            period: Time period

        Returns:
            Dict with trends for each indicator
        """
        indicators = [
            "entreprises_count",
            "population",
            "unemployment_rate",
            "real_estate_price_m2",
            "attractiveness_score"
        ]

        trends = {}
        has_real_data = False

        for indicator in indicators:
            trend = await self.compute_trends(territory_code, indicator, period)
            trends[indicator] = trend
            if trend.get("is_real_data"):
                has_real_data = True

        return {
            "territory_code": territory_code,
            "period": period,
            "has_real_data": has_real_data,
            "trends": trends,
            "note": "Données historiques réelles" if has_real_data else "Données estimées - historique insuffisant"
        }


async def collect_territorial_snapshot(
    session: AsyncSession,
    territory_code: str,
    sirene_adapter,
    insee_adapter=None
) -> TerritorialSnapshot | None:
    """Helper to collect and store a snapshot from APIs.

    Call this periodically (e.g., daily cron) to build historical data.
    """
    try:
        data = {}

        # Get enterprise count from SIRENE
        sirene_result = await sirene_adapter.search({
            "departement": territory_code,
            "per_page": 1
        })
        if sirene_result:
            data["entreprises_count"] = sirene_result.get("total_results", 0)

        # Get population from INSEE if available
        if insee_adapter:
            pop_data = await insee_adapter.get_population(territory_code)
            if pop_data:
                data["population"] = pop_data.get("population")
                data["population_density"] = pop_data.get("densite")

        if data:
            service = TerritorialHistoryService(session)
            return await service.create_snapshot(territory_code, data, source="daily_collect")

    except Exception as e:
        logger.error(f"Failed to collect snapshot for {territory_code}: {e}")

    return None
