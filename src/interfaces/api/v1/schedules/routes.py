"""Scheduled Analyses API endpoints.

Provides CRUD operations for TAJINE scheduled analyses.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.tajine_scheduler import get_tajine_scheduler
from src.infrastructure.persistence.database import get_db_session
from src.infrastructure.persistence.models.scheduled_analysis_model import ScheduleFrequency
from src.infrastructure.security.auth import User as AuthUser
from src.infrastructure.security.auth import get_current_user

router = APIRouter(prefix="/schedules", tags=["Scheduled Analyses"])


# --- Pydantic Models ---

class CreateScheduleRequest(BaseModel):
    """Request to create a scheduled analysis."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the schedule")
    query: str = Field(..., min_length=1, max_length=2048, description="TAJINE query to execute")
    description: str | None = Field(None, max_length=1024)
    cognitive_level: str = Field("analytical", description="Cognitive level (reactive, analytical, strategic, prospective, theoretical)")
    frequency: str = Field("daily", description="Schedule frequency (once, hourly, daily, weekly, monthly)")
    scheduled_time: str = Field("08:00", pattern=r"^\d{2}:\d{2}$", description="Time of day (HH:MM)")
    day_of_week: int | None = Field(None, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    day_of_month: int | None = Field(None, ge=1, le=31, description="Day of month (1-31)")
    department_codes: list[str] | None = Field(None, description="Target department codes (null=all)")
    timezone: str = Field("Europe/Paris", description="Timezone for scheduling")
    notify_email: bool = Field(True, description="Send email notifications")
    notify_webhook: str | None = Field(None, max_length=500, description="Webhook URL for notifications")


class UpdateScheduleRequest(BaseModel):
    """Request to update a scheduled analysis."""
    name: str | None = Field(None, min_length=1, max_length=255)
    query: str | None = Field(None, min_length=1, max_length=2048)
    description: str | None = Field(None, max_length=1024)
    cognitive_level: str | None = None
    frequency: str | None = None
    scheduled_time: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    day_of_week: int | None = Field(None, ge=0, le=6)
    day_of_month: int | None = Field(None, ge=1, le=31)
    department_codes: list[str] | None = None
    timezone: str | None = None
    notify_email: bool | None = None
    notify_webhook: str | None = Field(None, max_length=500)


class ScheduleResponse(BaseModel):
    """Response for a scheduled analysis."""
    id: str
    user_id: str
    name: str
    description: str | None
    query: str
    cognitive_level: str
    frequency: str
    scheduled_time: str | None
    day_of_week: int | None
    day_of_month: int | None
    department_codes: list[str] | None
    timezone: str
    notify_email: bool
    notify_webhook: str | None
    is_active: bool
    next_run: str | None
    last_run: str | None
    run_count: int
    error_count: int
    created_at: str
    updated_at: str


class ScheduleListResponse(BaseModel):
    """Response for listing scheduled analyses."""
    schedules: list[ScheduleResponse]
    total: int


# --- Helper Functions ---

def schedule_to_response(schedule) -> ScheduleResponse:
    """Convert a ScheduledAnalysisDB to response model."""
    return ScheduleResponse(
        id=str(schedule.id),
        user_id=str(schedule.user_id),
        name=schedule.name,
        description=schedule.description,
        query=schedule.query,
        cognitive_level=schedule.cognitive_level,
        frequency=schedule.frequency,
        scheduled_time=schedule.scheduled_time,
        day_of_week=schedule.day_of_week,
        day_of_month=schedule.day_of_month,
        department_codes=schedule.department_codes,
        timezone=schedule.timezone,
        notify_email=schedule.notify_email,
        notify_webhook=schedule.notify_webhook,
        is_active=schedule.is_active,
        next_run=schedule.next_run.isoformat() if schedule.next_run else None,
        last_run=schedule.last_run.isoformat() if schedule.last_run else None,
        run_count=schedule.run_count,
        error_count=schedule.error_count,
        created_at=schedule.created_at.isoformat(),
        updated_at=schedule.updated_at.isoformat(),
    )


# --- API Endpoints ---

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    request: CreateScheduleRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new scheduled TAJINE analysis."""
    scheduler = get_tajine_scheduler()

    # Validate frequency
    try:
        ScheduleFrequency(request.frequency)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid frequency: {request.frequency}. Must be one of: once, hourly, daily, weekly, monthly",
        )

    # Validate cognitive level
    valid_levels = ["reactive", "analytical", "strategic", "prospective", "theoretical"]
    if request.cognitive_level not in valid_levels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cognitive_level. Must be one of: {', '.join(valid_levels)}",
        )

    schedule = await scheduler.create_schedule(
        session=session,
        user_id=UUID(current_user.user_id),
        name=request.name,
        query=request.query,
        description=request.description,
        cognitive_level=request.cognitive_level,
        frequency=request.frequency,
        scheduled_time=request.scheduled_time,
        day_of_week=request.day_of_week,
        day_of_month=request.day_of_month,
        department_codes=request.department_codes,
        timezone=request.timezone,
        notify_email=request.notify_email,
        notify_webhook=request.notify_webhook,
    )

    await session.commit()
    return schedule_to_response(schedule)


@router.get("", response_model=ScheduleListResponse)
async def list_schedules(
    active_only: bool = False,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """List scheduled analyses for the current user."""
    scheduler = get_tajine_scheduler()

    schedules = await scheduler.list_schedules(
        session=session,
        user_id=UUID(current_user.user_id),
        active_only=active_only,
    )

    return ScheduleListResponse(
        schedules=[schedule_to_response(s) for s in schedules],
        total=len(schedules),
    )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Get a scheduled analysis by ID."""
    scheduler = get_tajine_scheduler()

    try:
        uuid = UUID(schedule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid schedule ID format",
        )

    schedule = await scheduler.get_schedule(session, uuid)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    # Check ownership
    if str(schedule.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return schedule_to_response(schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    request: UpdateScheduleRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Update a scheduled analysis."""
    scheduler = get_tajine_scheduler()

    try:
        uuid = UUID(schedule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid schedule ID format",
        )

    # Get existing schedule
    schedule = await scheduler.get_schedule(session, uuid)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    # Check ownership
    if str(schedule.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Validate updates
    updates = request.model_dump(exclude_unset=True, exclude_none=True)

    if "frequency" in updates:
        try:
            ScheduleFrequency(updates["frequency"])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid frequency: {updates['frequency']}",
            )

    if "cognitive_level" in updates:
        valid_levels = ["reactive", "analytical", "strategic", "prospective", "theoretical"]
        if updates["cognitive_level"] not in valid_levels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cognitive_level. Must be one of: {', '.join(valid_levels)}",
            )

    updated = await scheduler.update_schedule(session, uuid, **updates)
    await session.commit()

    return schedule_to_response(updated)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a scheduled analysis."""
    scheduler = get_tajine_scheduler()

    try:
        uuid = UUID(schedule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid schedule ID format",
        )

    # Get existing schedule
    schedule = await scheduler.get_schedule(session, uuid)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    # Check ownership
    if str(schedule.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    await scheduler.delete_schedule(session, uuid)
    await session.commit()


@router.post("/{schedule_id}/toggle", response_model=ScheduleResponse)
async def toggle_schedule(
    schedule_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Toggle a scheduled analysis active/inactive."""
    scheduler = get_tajine_scheduler()

    try:
        uuid = UUID(schedule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid schedule ID format",
        )

    # Get existing schedule
    schedule = await scheduler.get_schedule(session, uuid)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    # Check ownership
    if str(schedule.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    updated = await scheduler.toggle_schedule(session, uuid)
    await session.commit()

    return schedule_to_response(updated)


@router.post("/{schedule_id}/run-now", response_model=dict)
async def run_schedule_now(
    schedule_id: str,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Trigger immediate execution of a scheduled analysis."""
    scheduler = get_tajine_scheduler()

    try:
        uuid = UUID(schedule_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid schedule ID format",
        )

    # Get existing schedule
    schedule = await scheduler.get_schedule(session, uuid)

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found",
        )

    # Check ownership
    if str(schedule.user_id) != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Execute immediately (async)
    import asyncio
    asyncio.create_task(scheduler._execute_analysis(schedule_id))

    return {
        "message": "Analysis execution started",
        "schedule_id": schedule_id,
    }
