"""TAJINE Scheduler Service.

Manages scheduled TAJINE analyses using APScheduler with PostgreSQL job store.
"""

from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.database import get_session
from src.infrastructure.persistence.models.scheduled_analysis_model import (
    ScheduledAnalysisDB,
    ScheduleFrequency,
)


class TAJINEScheduler:
    """Scheduler for TAJINE analyses.

    Provides:
    - CRUD operations for scheduled analyses
    - APScheduler integration for job execution
    - Automatic job persistence in PostgreSQL
    """

    _instance: Optional["TAJINEScheduler"] = None

    def __init__(self):
        """Initialize the scheduler."""
        self._scheduler: AsyncIOScheduler | None = None
        self._is_running = False

    @classmethod
    def get_instance(cls) -> "TAJINEScheduler":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = TAJINEScheduler()
        return cls._instance

    async def start(self) -> None:
        """Start the scheduler and load existing jobs."""
        if self._is_running:
            return

        self._scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Paris"))
        self._scheduler.start()
        self._is_running = True

        # Load active scheduled analyses from database
        await self._load_scheduled_jobs()

        logger.info("TAJINE Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler and self._is_running:
            self._scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("TAJINE Scheduler stopped")

    async def _load_scheduled_jobs(self) -> None:
        """Load all active scheduled analyses from database."""
        async with get_session() as session:
            stmt = select(ScheduledAnalysisDB).where(
                ScheduledAnalysisDB.is_active == True  # noqa: E712
            )
            result = await session.execute(stmt)
            analyses = result.scalars().all()

            for analysis in analyses:
                await self._add_job_for_analysis(analysis)

            logger.info(f"Loaded {len(analyses)} scheduled analyses")

    async def _add_job_for_analysis(self, analysis: ScheduledAnalysisDB) -> None:
        """Add an APScheduler job for a scheduled analysis."""
        if not self._scheduler:
            return

        job_id = f"tajine_analysis_{analysis.id}"

        # Remove existing job if any
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

        # Create trigger based on frequency
        trigger = self._create_trigger(analysis)
        if not trigger:
            logger.warning(f"Could not create trigger for analysis {analysis.id}")
            return

        # Add job
        self._scheduler.add_job(
            self._execute_analysis,
            trigger=trigger,
            id=job_id,
            args=[str(analysis.id)],
            replace_existing=True,
        )

        logger.debug(f"Scheduled job for analysis {analysis.id}")

    def _create_trigger(self, analysis: ScheduledAnalysisDB):
        """Create APScheduler trigger from analysis configuration."""
        tz = pytz.timezone(analysis.timezone)

        if analysis.frequency == ScheduleFrequency.ONCE.value:
            # One-time execution at next_run
            if analysis.next_run:
                return DateTrigger(run_date=analysis.next_run, timezone=tz)
            return None

        # Parse time
        hour, minute = 8, 0
        if analysis.scheduled_time:
            parts = analysis.scheduled_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0

        if analysis.frequency == ScheduleFrequency.HOURLY.value:
            return CronTrigger(minute=minute, timezone=tz)

        elif analysis.frequency == ScheduleFrequency.DAILY.value:
            return CronTrigger(hour=hour, minute=minute, timezone=tz)

        elif analysis.frequency == ScheduleFrequency.WEEKLY.value:
            day_of_week = analysis.day_of_week or 0
            return CronTrigger(
                day_of_week=day_of_week,
                hour=hour,
                minute=minute,
                timezone=tz,
            )

        elif analysis.frequency == ScheduleFrequency.MONTHLY.value:
            day = analysis.day_of_month or 1
            return CronTrigger(
                day=day,
                hour=hour,
                minute=minute,
                timezone=tz,
            )

        return None

    async def _execute_analysis(self, analysis_id: str) -> None:
        """Execute a scheduled TAJINE analysis."""
        logger.info(f"Executing scheduled analysis {analysis_id}")

        try:
            async with get_session() as session:
                # Get analysis configuration
                stmt = select(ScheduledAnalysisDB).where(
                    ScheduledAnalysisDB.id == UUID(analysis_id)
                )
                result = await session.execute(stmt)
                analysis = result.scalar_one_or_none()

                if not analysis:
                    logger.error(f"Analysis {analysis_id} not found")
                    return

                if not analysis.is_active:
                    logger.debug(f"Analysis {analysis_id} is inactive, skipping")
                    return

                # Execute TAJINE analysis
                from src.infrastructure.agents.tajine.tajine_agent import TAJINEAgent

                agent = TAJINEAgent()

                # Build context with department codes if specified
                context = {}
                if analysis.department_codes:
                    context["department_codes"] = analysis.department_codes

                # Execute analysis
                response = await agent.execute_task(
                    task=analysis.query,
                    context=context,
                )

                # Update analysis record
                datetime.now(UTC)
                analysis.run_count += 1
                analysis.last_result = {
                    "success": True,
                    "response_length": len(response) if response else 0,
                    "executed_at": datetime.utcnow().isoformat(),
                }

                # Calculate next run
                analysis.next_run = self._calculate_next_run(analysis)

                await session.commit()

                logger.info(f"Analysis {analysis_id} completed successfully")

                # Send notifications if configured
                await self._send_notifications(analysis, response)

        except Exception as e:
            logger.error(f"Error executing analysis {analysis_id}: {e}")

            # Update error count
            try:
                async with get_session() as session:
                    stmt = (
                        update(ScheduledAnalysisDB)
                        .where(ScheduledAnalysisDB.id == UUID(analysis_id))
                        .values(
                            error_count=ScheduledAnalysisDB.error_count + 1,
                            last_result={
                                "success": False,
                                "error": str(e),
                                "executed_at": datetime.utcnow().isoformat(),
                            },
                        )
                    )
                    await session.execute(stmt)
                    await session.commit()
            except Exception as update_error:
                logger.error(f"Failed to update error count: {update_error}")

    def _calculate_next_run(self, analysis: ScheduledAnalysisDB) -> datetime | None:
        """Calculate the next run time for an analysis."""
        tz = pytz.timezone(analysis.timezone)
        now = datetime.now(tz)

        if analysis.frequency == ScheduleFrequency.ONCE.value:
            return None  # No next run for one-time jobs

        # Parse time
        hour, minute = 8, 0
        if analysis.scheduled_time:
            parts = analysis.scheduled_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0

        if analysis.frequency == ScheduleFrequency.HOURLY.value:
            next_run = now.replace(minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(hours=1)
            return next_run

        elif analysis.frequency == ScheduleFrequency.DAILY.value:
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        elif analysis.frequency == ScheduleFrequency.WEEKLY.value:
            day_of_week = analysis.day_of_week or 0
            days_ahead = day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            next_run += timedelta(days=days_ahead)
            return next_run

        elif analysis.frequency == ScheduleFrequency.MONTHLY.value:
            day = analysis.day_of_month or 1
            next_run = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                # Move to next month
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)
            return next_run

        return None

    async def _send_notifications(
        self, analysis: ScheduledAnalysisDB, response: str
    ) -> None:
        """Send notifications for completed analysis."""
        # Email notification
        if analysis.notify_email:
            try:
                from src.infrastructure.notifications import get_email_service

                email_service = get_email_service()
                if email_service.is_enabled:
                    result = await email_service.send_analysis_notification(
                        to=analysis.notify_email,
                        analysis_name=analysis.name,
                        analysis_id=str(analysis.id),
                        response_preview=response[:500] if response else "",
                        dashboard_url=None,  # Could be configured
                    )
                    logger.debug(f"Email notification result for {analysis.id}: {result}")
                else:
                    logger.debug(f"Email notification skipped (service disabled) for {analysis.id}")
            except Exception as e:
                logger.warning(f"Failed to send email notification: {e}")

        # Webhook notification
        if analysis.notify_webhook:
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    await client.post(
                        analysis.notify_webhook,
                        json={
                            "analysis_id": str(analysis.id),
                            "analysis_name": analysis.name,
                            "executed_at": datetime.utcnow().isoformat(),
                            "response_preview": response[:500] if response else "",
                        },
                        timeout=10.0,
                    )
                    logger.debug(f"Sent webhook notification for analysis {analysis.id}")
            except Exception as e:
                logger.warning(f"Failed to send webhook notification: {e}")

    # --- CRUD Operations ---

    async def create_schedule(
        self,
        session: AsyncSession,
        user_id: UUID,
        name: str,
        query: str,
        frequency: str = "daily",
        cognitive_level: str = "analytical",
        scheduled_time: str = "08:00",
        day_of_week: int | None = None,
        day_of_month: int | None = None,
        department_codes: list[str] | None = None,
        description: str | None = None,
        timezone: str = "Europe/Paris",
        notify_email: bool = True,
        notify_webhook: str | None = None,
    ) -> ScheduledAnalysisDB:
        """Create a new scheduled analysis."""
        analysis = ScheduledAnalysisDB(
            user_id=user_id,
            name=name,
            query=query,
            frequency=frequency,
            cognitive_level=cognitive_level,
            scheduled_time=scheduled_time,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            department_codes=department_codes,
            description=description,
            timezone=timezone,
            notify_email=notify_email,
            notify_webhook=notify_webhook,
            is_active=True,
        )

        # Calculate next run
        analysis.next_run = self._calculate_next_run(analysis)

        session.add(analysis)
        await session.flush()

        # Add job to scheduler
        if self._is_running:
            await self._add_job_for_analysis(analysis)

        logger.info(f"Created scheduled analysis: {analysis.id}")
        return analysis

    async def get_schedule(
        self, session: AsyncSession, schedule_id: UUID
    ) -> ScheduledAnalysisDB | None:
        """Get a scheduled analysis by ID."""
        stmt = select(ScheduledAnalysisDB).where(ScheduledAnalysisDB.id == schedule_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_schedules(
        self,
        session: AsyncSession,
        user_id: UUID | None = None,
        active_only: bool = False,
    ) -> list[ScheduledAnalysisDB]:
        """List scheduled analyses."""
        stmt = select(ScheduledAnalysisDB)

        if user_id:
            stmt = stmt.where(ScheduledAnalysisDB.user_id == user_id)

        if active_only:
            stmt = stmt.where(ScheduledAnalysisDB.is_active == True)  # noqa: E712

        stmt = stmt.order_by(ScheduledAnalysisDB.created_at.desc())

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_schedule(
        self,
        session: AsyncSession,
        schedule_id: UUID,
        **updates,
    ) -> ScheduledAnalysisDB | None:
        """Update a scheduled analysis."""
        analysis = await self.get_schedule(session, schedule_id)
        if not analysis:
            return None

        for key, value in updates.items():
            if hasattr(analysis, key):
                setattr(analysis, key, value)

        # Recalculate next run if schedule changed
        if any(k in updates for k in ["frequency", "scheduled_time", "day_of_week", "day_of_month"]):
            analysis.next_run = self._calculate_next_run(analysis)

        await session.flush()

        # Update scheduler job
        if self._is_running:
            await self._add_job_for_analysis(analysis)

        return analysis

    async def delete_schedule(
        self, session: AsyncSession, schedule_id: UUID
    ) -> bool:
        """Delete a scheduled analysis."""
        analysis = await self.get_schedule(session, schedule_id)
        if not analysis:
            return False

        # Remove job from scheduler
        if self._scheduler:
            job_id = f"tajine_analysis_{schedule_id}"
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

        await session.delete(analysis)
        logger.info(f"Deleted scheduled analysis: {schedule_id}")
        return True

    async def toggle_schedule(
        self, session: AsyncSession, schedule_id: UUID
    ) -> ScheduledAnalysisDB | None:
        """Toggle a scheduled analysis active/inactive."""
        analysis = await self.get_schedule(session, schedule_id)
        if not analysis:
            return None

        analysis.is_active = not analysis.is_active
        await session.flush()

        # Update scheduler
        if self._is_running:
            if analysis.is_active:
                await self._add_job_for_analysis(analysis)
            else:
                job_id = f"tajine_analysis_{schedule_id}"
                if self._scheduler and self._scheduler.get_job(job_id):
                    self._scheduler.remove_job(job_id)

        return analysis


# Singleton instance getter
def get_tajine_scheduler() -> TAJINEScheduler:
    """Get the TAJINE scheduler singleton."""
    return TAJINEScheduler.get_instance()
