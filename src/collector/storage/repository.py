"""Repository for signals and anomalies storage."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Anomaly, Base, Signal


class SignalRepository:
    """Async repository for signals and anomalies."""

    def __init__(self, database_url: str) -> None:
        """Initialize with async PostgreSQL connection.

        Args:
            database_url: PostgreSQL URL (postgresql+asyncpg://...)
        """
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def init_db(self) -> None:
        """Create tables if they don't exist."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def insert_signal(self, **kwargs: Any) -> Signal:
        """Insert a signal, upsert on conflict."""
        async with self._session_factory() as session:
            try:
                stmt = (
                    pg_insert(Signal)
                    .values(**kwargs)
                    .on_conflict_do_update(
                        constraint="uq_source_url_date",
                        set_={
                            "metric_value": kwargs.get("metric_value"),
                            "raw_data": kwargs.get("raw_data"),
                            "collected_at": datetime.now(),
                        },
                    )
                    .returning(Signal)
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.scalar_one()
            except Exception:
                await session.rollback()
                # Fallback: simple insert (constraint may not exist yet)
                signal = Signal(**kwargs)
                session.add(signal)
                await session.commit()
                await session.refresh(signal)
                return signal

    async def insert_signals_batch(self, signals: list[dict[str, Any]]) -> int:
        """Bulk insert signals, skip duplicates best-effort."""
        if not signals:
            return 0
        async with self._session_factory() as session:
            try:
                stmt = (
                    pg_insert(Signal)
                    .values(signals)
                    .on_conflict_do_nothing(constraint="uq_source_url_date")
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount
            except Exception:
                await session.rollback()
                # Fallback: insert one by one, skip failures
                count = 0
                for sig_data in signals:
                    try:
                        session.add(Signal(**sig_data))
                        await session.flush()
                        count += 1
                    except Exception:
                        await session.rollback()
                await session.commit()
                return count

    async def get_signals(
        self,
        code_commune: str | None = None,
        code_dept: str | None = None,
        source: str | None = None,
        metric_name: str | None = None,
        since: date | None = None,
        limit: int = 100,
    ) -> list[Signal]:
        """Query signals with filters."""
        async with self._session_factory() as session:
            query = select(Signal)
            if code_commune:
                query = query.where(Signal.code_commune == code_commune)
            if code_dept:
                query = query.where(Signal.code_dept == code_dept)
            if source:
                query = query.where(Signal.source == source)
            if metric_name:
                query = query.where(Signal.metric_name == metric_name)
            if since:
                query = query.where(Signal.event_date >= since)
            query = query.order_by(Signal.event_date.desc()).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def insert_anomaly(self, **kwargs: Any) -> Anomaly:
        """Insert a detected anomaly."""
        async with self._session_factory() as session:
            anomaly = Anomaly(**kwargs)
            session.add(anomaly)
            await session.commit()
            await session.refresh(anomaly)
            return anomaly

    async def get_signal_summary(self, code_commune: str, weeks: int = 12) -> list[dict[str, Any]]:
        """Get signal summary for a commune (weekly aggregation)."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT
                        metric_name,
                        date_trunc('week', event_date) AS week,
                        COUNT(*) AS count,
                        AVG(metric_value) AS avg_value,
                        STDDEV(metric_value) AS stddev_value,
                        array_agg(DISTINCT source) AS sources
                    FROM signals
                    WHERE code_commune = :commune
                      AND event_date >= CURRENT_DATE - INTERVAL ':weeks weeks'
                    GROUP BY metric_name, date_trunc('week', event_date)
                    ORDER BY week DESC
                """),
                {"commune": code_commune, "weeks": weeks},
            )
            return [dict(row._mapping) for row in result]

    async def close(self) -> None:
        """Close the engine."""
        await self._engine.dispose()
