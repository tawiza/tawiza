"""Repository for LLM predictions."""

from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.persistence.models.llm_prediction import LLMPredictionDB


class PredictionRepository:
    """Repository for LLM prediction operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with a session."""
        self._session = session

    async def create(
        self,
        prediction_id: UUID,
        model_name: str,
        prompt: str,
        response_text: str,
        latency_ms: float,
        model_id: UUID | None = None,
        model_version: str = "1.0.0",
        confidence: float | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        temperature: float = 0.7,
        max_tokens: int = 512,
        extra_data: dict | None = None,
    ) -> LLMPredictionDB:
        """Create a new prediction record."""
        prediction = LLMPredictionDB(
            id=prediction_id,
            model_id=model_id,
            model_name=model_name,
            model_version=model_version,
            prompt=prompt,
            response_text=response_text,
            confidence=confidence,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_data=extra_data or {},
        )
        self._session.add(prediction)
        await self._session.flush()
        await self._session.refresh(prediction)
        logger.debug(f"Created prediction {prediction_id}")
        return prediction

    async def get_by_id(self, prediction_id: UUID) -> LLMPredictionDB | None:
        """Get prediction by ID."""
        query = select(LLMPredictionDB).where(LLMPredictionDB.id == prediction_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        limit: int = 50,
        offset: int = 0,
        model_name: str | None = None,
    ) -> list[LLMPredictionDB]:
        """List recent predictions."""
        query = (
            select(LLMPredictionDB)
            .order_by(LLMPredictionDB.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if model_name:
            query = query.where(LLMPredictionDB.model_name == model_name)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count(self, model_name: str | None = None) -> int:
        """Count predictions."""
        query = select(func.count()).select_from(LLMPredictionDB)
        if model_name:
            query = query.where(LLMPredictionDB.model_name == model_name)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_stats(self, model_name: str | None = None) -> dict:
        """Get prediction statistics."""
        query = select(
            func.count().label("count"),
            func.avg(LLMPredictionDB.latency_ms).label("avg_latency"),
            func.avg(LLMPredictionDB.total_tokens).label("avg_tokens"),
        ).select_from(LLMPredictionDB)

        if model_name:
            query = query.where(LLMPredictionDB.model_name == model_name)

        result = await self._session.execute(query)
        row = result.one()

        return {
            "count": row.count or 0,
            "avg_latency_ms": round(row.avg_latency or 0, 2),
            "avg_tokens": round(row.avg_tokens or 0, 1),
        }
