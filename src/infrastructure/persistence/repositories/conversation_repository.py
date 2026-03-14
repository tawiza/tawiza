"""SQLAlchemy implementation of Conversation and Message repositories."""

from datetime import UTC, datetime
from uuid import UUID

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.infrastructure.persistence.models.conversation_model import (
    AnalysisResultDB,
    ConversationDB,
    MessageDB,
)


class ConversationRepository:
    """Repository for conversation operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with a session."""
        self._session = session

    async def create(
        self,
        user_id: UUID,
        title: str | None = None,
        cognitive_level: str = "analytical",
        department_code: str | None = None,
    ) -> ConversationDB:
        """Create a new conversation."""
        conversation = ConversationDB(
            user_id=user_id,
            title=title,
            cognitive_level=cognitive_level,
            department_code=department_code,
        )
        self._session.add(conversation)
        await self._session.flush()
        await self._session.refresh(conversation)
        logger.debug(f"Created conversation {conversation.id} for user {user_id}")
        return conversation

    async def get_by_id(
        self, conversation_id: UUID, include_messages: bool = False
    ) -> ConversationDB | None:
        """Get a conversation by ID, optionally with messages."""
        if include_messages:
            query = (
                select(ConversationDB)
                .where(ConversationDB.id == conversation_id)
                .options(selectinload(ConversationDB.messages))
            )
        else:
            query = select(ConversationDB).where(ConversationDB.id == conversation_id)

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        cognitive_level: str | None = None,
        department_code: str | None = None,
    ) -> list[ConversationDB]:
        """List conversations for a user with optional filters."""
        query = (
            select(ConversationDB)
            .where(ConversationDB.user_id == user_id)
            .order_by(ConversationDB.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if cognitive_level:
            query = query.where(ConversationDB.cognitive_level == cognitive_level)
        if department_code:
            query = query.where(ConversationDB.department_code == department_code)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID) -> int:
        """Count conversations for a user."""
        query = (
            select(func.count())
            .select_from(ConversationDB)
            .where(ConversationDB.user_id == user_id)
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def update(
        self,
        conversation_id: UUID,
        title: str | None = None,
        cognitive_level: str | None = None,
        department_code: str | None = None,
    ) -> ConversationDB | None:
        """Update a conversation."""
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            return None

        if title is not None:
            conversation.title = title
        if cognitive_level is not None:
            conversation.cognitive_level = cognitive_level
        if department_code is not None:
            conversation.department_code = department_code

        conversation.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(conversation)
        return conversation

    async def delete(self, conversation_id: UUID) -> bool:
        """Delete a conversation and its messages."""
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            return False

        await self._session.delete(conversation)
        await self._session.flush()
        logger.debug(f"Deleted conversation {conversation_id}")
        return True

    async def search_full_text(
        self,
        user_id: UUID,
        query: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ConversationDB], int]:
        """
        Search conversations using PostgreSQL full-text search.

        Searches in conversation titles and message content.

        Args:
            user_id: User ID to filter by
            query: Search query string
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Tuple of (matching conversations, total count)
        """
        from sqlalchemy import literal_column, or_
        from sqlalchemy.sql import text

        # Prepare search query for PostgreSQL (replace spaces with &)
        " & ".join(query.strip().split())

        # First, find conversations where title matches OR has matching messages
        # Using plainto_tsquery for natural language query parsing
        subquery = (
            select(MessageDB.conversation_id)
            .where(
                func.to_tsvector("french", MessageDB.content).match(
                    func.plainto_tsquery("french", query)
                )
            )
            .distinct()
        )

        # Main query: conversations matching by title OR having matching messages
        query_obj = (
            select(ConversationDB)
            .where(ConversationDB.user_id == user_id)
            .where(
                or_(
                    # Title match (simple ILIKE for short titles)
                    ConversationDB.title.ilike(f"%{query}%"),
                    # Message content full-text match
                    ConversationDB.id.in_(subquery),
                )
            )
            .order_by(ConversationDB.updated_at.desc())
        )

        # Get total count
        count_query = select(func.count()).select_from(query_obj.subquery())
        count_result = await self._session.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query_obj = query_obj.limit(limit).offset(offset)
        result = await self._session.execute(query_obj)
        conversations = list(result.scalars().all())

        logger.debug(f"Full-text search for '{query}' found {total} conversations")
        return conversations, total


class MessageRepository:
    """Repository for message operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with a session."""
        self._session = session

    async def create(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        extra_data: dict | None = None,
    ) -> MessageDB:
        """Create a new message."""
        message = MessageDB(
            conversation_id=conversation_id,
            role=role,
            content=content,
            extra_data=extra_data or {},
        )
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)

        # Update conversation's updated_at
        query = select(ConversationDB).where(ConversationDB.id == conversation_id)
        result = await self._session.execute(query)
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.updated_at = datetime.now(UTC)
            await self._session.flush()

        return message

    async def get_by_conversation(
        self,
        conversation_id: UUID,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[MessageDB]:
        """Get messages for a conversation."""
        query = (
            select(MessageDB)
            .where(MessageDB.conversation_id == conversation_id)
            .order_by(MessageDB.created_at.asc())
            .limit(limit)
        )

        if before:
            query = query.where(MessageDB.created_at < before)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_by_conversation(self, conversation_id: UUID) -> int:
        """Count messages in a conversation."""
        query = (
            select(func.count())
            .select_from(MessageDB)
            .where(MessageDB.conversation_id == conversation_id)
        )
        result = await self._session.execute(query)
        return result.scalar_one()


class AnalysisResultRepository:
    """Repository for analysis result caching."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with a session."""
        self._session = session

    async def create(
        self,
        query: str,
        result: dict,
        user_id: UUID | None = None,
        cognitive_level: str | None = None,
        department_codes: list[str] | None = None,
        sources: list[dict] | None = None,
        confidence: float | None = None,
        duration_ms: int | None = None,
    ) -> AnalysisResultDB:
        """Store an analysis result."""
        analysis = AnalysisResultDB(
            user_id=user_id,
            query=query,
            cognitive_level=cognitive_level,
            department_codes=department_codes,
            result=result,
            sources=sources or [],
            confidence=confidence,
            duration_ms=duration_ms,
        )
        self._session.add(analysis)
        await self._session.flush()
        await self._session.refresh(analysis)
        logger.debug(f"Stored analysis result {analysis.id}")
        return analysis

    async def get_by_id(self, analysis_id: UUID) -> AnalysisResultDB | None:
        """Get an analysis result by ID."""
        return await self._session.get(AnalysisResultDB, analysis_id)

    async def find_similar(
        self,
        query: str,
        cognitive_level: str | None = None,
        department_codes: list[str] | None = None,
        max_age_hours: int = 24,
    ) -> AnalysisResultDB | None:
        """Find a cached analysis with similar parameters."""
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)

        stmt = (
            select(AnalysisResultDB)
            .where(AnalysisResultDB.query == query)
            .where(AnalysisResultDB.created_at > cutoff)
            .order_by(AnalysisResultDB.created_at.desc())
            .limit(1)
        )

        if cognitive_level:
            stmt = stmt.where(AnalysisResultDB.cognitive_level == cognitive_level)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        user_id: UUID | None = None,
        limit: int = 20,
    ) -> list[AnalysisResultDB]:
        """List recent analysis results."""
        query = select(AnalysisResultDB).order_by(AnalysisResultDB.created_at.desc()).limit(limit)

        if user_id:
            query = query.where(AnalysisResultDB.user_id == user_id)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def cleanup_old(self, days: int = 30) -> int:
        """Delete analysis results older than specified days."""
        from datetime import timedelta

        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = delete(AnalysisResultDB).where(AnalysisResultDB.created_at < cutoff)
        result = await self._session.execute(stmt)
        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} old analysis results")
        return count
