"""Decisions & Stakeholders API routes."""

import enum
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.infrastructure.persistence.database import get_session
from src.infrastructure.persistence.models.decision_models import (
    DecisionDB,
    DecisionPriority,
    DecisionRecommendationDB,
    DecisionRole,
    DecisionStakeholderDB,
    DecisionStatus,
    StakeholderDB,
    StakeholderRelationDB,
    StakeholderRelationType,
    StakeholderType,
    TerritoryScope,
)

router = APIRouter(prefix="/api/v1/decisions", tags=["Decisions"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class StakeholderCreate(BaseModel):
    name: str
    role: str
    organization: str
    type: StakeholderType = StakeholderType.institution
    domains: list[str] = Field(default_factory=list)
    territory_dept: str
    territory_scope: TerritoryScope = TerritoryScope.departement
    influence_level: int = Field(default=3, ge=1, le=5)
    contact_email: str | None = None
    tags: list[str] = Field(default_factory=list)
    avatar_url: str | None = None


class StakeholderUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    organization: str | None = None
    type: StakeholderType | None = None
    domains: list[str] | None = None
    territory_dept: str | None = None
    territory_scope: TerritoryScope | None = None
    influence_level: int | None = Field(default=None, ge=1, le=5)
    contact_email: str | None = None
    tags: list[str] | None = None
    avatar_url: str | None = None
    active: bool | None = None


class StakeholderResponse(BaseModel):
    id: str
    name: str
    role: str
    organization: str
    type: str
    domains: list[str]
    territory_dept: str
    territory_scope: str
    influence_level: int
    contact_email: str | None
    tags: list[str]
    avatar_url: str | None
    active: bool
    created_at: datetime


class RelationCreate(BaseModel):
    from_id: str
    to_id: str
    type: StakeholderRelationType
    strength: int = Field(default=2, ge=1, le=3)
    description: str | None = None
    bidirectional: bool = True


class RelationResponse(BaseModel):
    id: str
    from_id: str
    to_id: str
    from_name: str | None = None
    to_name: str | None = None
    type: str
    strength: int
    description: str | None
    bidirectional: bool


class DecisionStakeholderInput(BaseModel):
    stakeholder_id: str
    role_in_decision: DecisionRole = DecisionRole.informe
    recommendation: str = ""


class DecisionCreate(BaseModel):
    title: str
    description: str = ""
    priority: DecisionPriority = DecisionPriority.moyenne
    dept: str
    source_type: str = "manual"
    source_id: str | None = None
    deadline: datetime | None = None
    stakeholders: list[DecisionStakeholderInput] = Field(default_factory=list)


class DecisionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: DecisionPriority | None = None
    deadline: datetime | None = None


class RecommendationResponse(BaseModel):
    id: str
    target_role: str
    action: str
    reasoning: str
    data_points: list[str]
    confidence: float


class DecisionStakeholderResponse(BaseModel):
    stakeholder_id: str
    stakeholder_name: str
    stakeholder_role: str
    stakeholder_org: str
    role_in_decision: str
    recommendation: str
    notified: bool


class DecisionResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    priority: str
    dept: str
    source_type: str
    source_id: str | None
    deadline: datetime | None
    created_at: datetime
    stakeholders: list[DecisionStakeholderResponse] = Field(default_factory=list)
    recommendations: list[RecommendationResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stakeholder_to_response(s: StakeholderDB) -> StakeholderResponse:
    return StakeholderResponse(
        id=str(s.id),
        name=s.name,
        role=s.role,
        organization=s.organization,
        type=s.type,
        domains=s.domains or [],
        territory_dept=s.territory_dept,
        territory_scope=s.territory_scope,
        influence_level=s.influence_level,
        contact_email=s.contact_email,
        tags=s.tags or [],
        avatar_url=s.avatar_url,
        active=s.active,
        created_at=s.created_at,
    )


def _decision_to_response(d: DecisionDB) -> DecisionResponse:
    stakeholders = []
    for ds in d.stakeholder_links or []:
        sh = ds.stakeholder
        stakeholders.append(
            DecisionStakeholderResponse(
                stakeholder_id=str(ds.stakeholder_id),
                stakeholder_name=sh.name if sh else "?",
                stakeholder_role=sh.role if sh else "",
                stakeholder_org=sh.organization if sh else "",
                role_in_decision=ds.role_in_decision,
                recommendation=ds.recommendation,
                notified=ds.notified,
            )
        )
    recommendations = [
        RecommendationResponse(
            id=str(r.id),
            target_role=r.target_role,
            action=r.action,
            reasoning=r.reasoning,
            data_points=r.data_points or [],
            confidence=r.confidence,
        )
        for r in (d.recommendations or [])
    ]
    return DecisionResponse(
        id=str(d.id),
        title=d.title,
        description=d.description,
        status=d.status,
        priority=d.priority,
        dept=d.dept,
        source_type=d.source_type,
        source_id=d.source_id,
        deadline=d.deadline,
        created_at=d.created_at,
        stakeholders=stakeholders,
        recommendations=recommendations,
    )


# ---------------------------------------------------------------------------
# Stakeholder endpoints
# ---------------------------------------------------------------------------


@router.get("/stakeholders", response_model=list[StakeholderResponse])
async def list_stakeholders(
    dept: str | None = Query(None),
    type: StakeholderType | None = Query(None),
    domain: str | None = Query(None),
    active: bool = Query(True),
):
    """List stakeholders with optional filters."""
    async with get_session() as session:
        q = select(StakeholderDB).where(StakeholderDB.active == active)
        if dept:
            q = q.where(StakeholderDB.territory_dept == dept)
        if type:
            q = q.where(StakeholderDB.type == type.value)
        if domain:
            q = q.where(StakeholderDB.domains.any(domain))
        q = q.order_by(StakeholderDB.influence_level.desc(), StakeholderDB.name)
        result = await session.execute(q)
        return [_stakeholder_to_response(s) for s in result.scalars().all()]


@router.post("/stakeholders", response_model=StakeholderResponse, status_code=201)
async def create_stakeholder(data: StakeholderCreate):
    """Create a new stakeholder."""
    async with get_session() as session:
        s = StakeholderDB(
            id=str(uuid4()),
            name=data.name,
            role=data.role,
            organization=data.organization,
            type=data.type.value,
            domains=data.domains,
            territory_dept=data.territory_dept,
            territory_scope=data.territory_scope.value,
            influence_level=data.influence_level,
            contact_email=data.contact_email,
            tags=data.tags,
            avatar_url=data.avatar_url,
        )
        session.add(s)
        await session.flush()
        logger.info(f"Stakeholder created: {s.name} ({s.role})")
        return _stakeholder_to_response(s)


@router.get("/stakeholders/{stakeholder_id}", response_model=StakeholderResponse)
async def get_stakeholder(stakeholder_id: str):
    """Get stakeholder by ID."""
    async with get_session() as session:
        s = await session.get(StakeholderDB, stakeholder_id)
        if not s:
            raise HTTPException(404, "Stakeholder not found")
        return _stakeholder_to_response(s)


@router.put("/stakeholders/{stakeholder_id}", response_model=StakeholderResponse)
async def update_stakeholder(stakeholder_id: str, data: StakeholderUpdate):
    """Update a stakeholder."""
    async with get_session() as session:
        s = await session.get(StakeholderDB, stakeholder_id)
        if not s:
            raise HTTPException(404, "Stakeholder not found")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if isinstance(value, enum.Enum):
                value = value.value
            setattr(s, key, value)
        await session.flush()
        return _stakeholder_to_response(s)


@router.delete("/stakeholders/{stakeholder_id}", status_code=204)
async def delete_stakeholder(stakeholder_id: str):
    """Delete a stakeholder."""
    async with get_session() as session:
        s = await session.get(StakeholderDB, stakeholder_id)
        if not s:
            raise HTTPException(404, "Stakeholder not found")
        await session.delete(s)


# ---------------------------------------------------------------------------
# Relation endpoints
# ---------------------------------------------------------------------------


@router.get("/relations", response_model=list[RelationResponse])
async def list_relations(dept: str | None = Query(None)):
    """List stakeholder relations (for graph visualization)."""
    async with get_session() as session:
        q = select(StakeholderRelationDB).join(
            StakeholderDB,
            StakeholderRelationDB.from_id == StakeholderDB.id,
        )
        if dept:
            q = q.where(StakeholderDB.territory_dept == dept)

        result = await session.execute(q)
        relations = result.scalars().all()

        responses = []
        for r in relations:
            from_s = await session.get(StakeholderDB, r.from_id)
            to_s = await session.get(StakeholderDB, r.to_id)
            responses.append(
                RelationResponse(
                    id=str(r.id),
                    from_id=str(r.from_id),
                    to_id=str(r.to_id),
                    from_name=from_s.name if from_s else None,
                    to_name=to_s.name if to_s else None,
                    type=r.type,
                    strength=r.strength,
                    description=r.description,
                    bidirectional=r.bidirectional,
                )
            )
        return responses


@router.post("/relations", response_model=RelationResponse, status_code=201)
async def create_relation(data: RelationCreate):
    """Create a relation between two stakeholders."""
    async with get_session() as session:
        # Verify both stakeholders exist
        from_s = await session.get(StakeholderDB, data.from_id)
        to_s = await session.get(StakeholderDB, data.to_id)
        if not from_s or not to_s:
            raise HTTPException(404, "One or both stakeholders not found")

        r = StakeholderRelationDB(
            id=str(uuid4()),
            from_id=data.from_id,
            to_id=data.to_id,
            type=data.type.value,
            strength=data.strength,
            description=data.description,
            bidirectional=data.bidirectional,
        )
        session.add(r)
        await session.flush()
        return RelationResponse(
            id=str(r.id),
            from_id=str(r.from_id),
            to_id=str(r.to_id),
            from_name=from_s.name,
            to_name=to_s.name,
            type=r.type,
            strength=r.strength,
            description=r.description,
            bidirectional=r.bidirectional,
        )


@router.delete("/relations/{relation_id}", status_code=204)
async def delete_relation(relation_id: str):
    """Delete a relation."""
    async with get_session() as session:
        r = await session.get(StakeholderRelationDB, relation_id)
        if not r:
            raise HTTPException(404, "Relation not found")
        await session.delete(r)


# ---------------------------------------------------------------------------
# Decision endpoints
# ---------------------------------------------------------------------------


@router.get("/stats/summary")
async def decision_stats(dept: str | None = Query(None)):
    """Get decision statistics by status and priority."""
    async with get_session() as session:
        q = select(
            DecisionDB.status,
            DecisionDB.priority,
            func.count(DecisionDB.id),
        ).group_by(DecisionDB.status, DecisionDB.priority)

        if dept:
            q = q.where(DecisionDB.dept == dept)

        result = await session.execute(q)
        rows = result.all()

        stats: dict[str, Any] = {
            "total": 0,
            "by_status": {},
            "by_priority": {},
        }
        for status_val, priority_val, count in rows:
            stats["total"] += count
            stats["by_status"][status_val] = stats["by_status"].get(status_val, 0) + count
            stats["by_priority"][priority_val] = stats["by_priority"].get(priority_val, 0) + count
        return stats


@router.get("/", response_model=list[DecisionResponse])
async def list_decisions(
    dept: str | None = Query(None),
    status: DecisionStatus | None = Query(None),
    priority: DecisionPriority | None = Query(None),
    limit: int = Query(50, le=200),
):
    """List decisions with optional filters."""
    async with get_session() as session:
        q = select(DecisionDB).options(
            selectinload(DecisionDB.stakeholder_links).selectinload(
                DecisionStakeholderDB.stakeholder
            ),
            selectinload(DecisionDB.recommendations),
        )
        if dept:
            q = q.where(DecisionDB.dept == dept)
        if status:
            q = q.where(DecisionDB.status == status.value)
        if priority:
            q = q.where(DecisionDB.priority == priority.value)
        q = q.order_by(DecisionDB.created_at.desc()).limit(limit)
        result = await session.execute(q)
        return [_decision_to_response(d) for d in result.scalars().all()]


@router.post("/", response_model=DecisionResponse, status_code=201)
async def create_decision(data: DecisionCreate):
    """Create a new decision."""
    async with get_session() as session:
        d = DecisionDB(
            id=str(uuid4()),
            title=data.title,
            description=data.description,
            priority=data.priority.value,
            dept=data.dept,
            source_type=data.source_type,
            source_id=data.source_id,
            deadline=data.deadline,
        )
        session.add(d)
        await session.flush()

        # Add stakeholder links
        for sh in data.stakeholders:
            ds = DecisionStakeholderDB(
                id=str(uuid4()),
                decision_id=str(d.id),
                stakeholder_id=sh.stakeholder_id,
                role_in_decision=sh.role_in_decision.value,
                recommendation=sh.recommendation,
            )
            session.add(ds)

        await session.flush()

        # Re-fetch with relationships loaded
        q = (
            select(DecisionDB)
            .where(DecisionDB.id == str(d.id))
            .options(
                selectinload(DecisionDB.stakeholder_links).selectinload(
                    DecisionStakeholderDB.stakeholder
                ),
                selectinload(DecisionDB.recommendations),
            )
        )
        result = await session.execute(q)
        refreshed = result.scalar_one()
        logger.info(f"Decision created: {d.title}")
        return _decision_to_response(refreshed)


@router.get("/{decision_id}", response_model=DecisionResponse)
async def get_decision(decision_id: str):
    """Get decision detail with stakeholders and recommendations."""
    async with get_session() as session:
        q = (
            select(DecisionDB)
            .where(DecisionDB.id == decision_id)
            .options(
                selectinload(DecisionDB.stakeholder_links).selectinload(
                    DecisionStakeholderDB.stakeholder
                ),
                selectinload(DecisionDB.recommendations),
            )
        )
        result = await session.execute(q)
        d = result.scalar_one_or_none()
        if not d:
            raise HTTPException(404, "Decision not found")
        return _decision_to_response(d)


@router.put("/{decision_id}", response_model=DecisionResponse)
async def update_decision(decision_id: str, data: DecisionUpdate):
    """Update a decision."""
    async with get_session() as session:
        d = await session.get(DecisionDB, decision_id)
        if not d:
            raise HTTPException(404, "Decision not found")
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if isinstance(value, enum.Enum):
                value = value.value
            setattr(d, key, value)
        await session.flush()
        return _decision_to_response(d)


@router.put("/{decision_id}/status")
async def update_decision_status(decision_id: str, status: DecisionStatus = Query(...)):
    """Change decision status."""
    async with get_session() as session:
        d = await session.get(DecisionDB, decision_id)
        if not d:
            raise HTTPException(404, "Decision not found")
        d.status = status.value
        await session.flush()
        return {"id": str(d.id), "status": d.status}
