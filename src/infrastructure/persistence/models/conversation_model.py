"""Database models for TAJINE conversations."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.database import Base


class ConversationDB(Base):
    """Database model for TAJINE conversations."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cognitive_level: Mapped[str] = mapped_column(String(50), nullable=False, default="analytical")
    department_code: Mapped[str | None] = mapped_column(String(3), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    messages: Mapped[list["MessageDB"]] = relationship(
        "MessageDB",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageDB.created_at",
    )

    # Indexes
    __table_args__ = (Index("ix_conversations_user_updated", "user_id", "updated_at"),)

    def __repr__(self) -> str:
        """String representation."""
        return f"<ConversationDB(id={self.id}, title={self.title}, level={self.cognitive_level})>"


class MessageDB(Base):
    """Database model for conversation messages."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant' | 'system'
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Extra data for assistant messages (sources, confidence, etc.)
    extra_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationship
    conversation: Mapped["ConversationDB"] = relationship(
        "ConversationDB", back_populates="messages"
    )

    def __repr__(self) -> str:
        """String representation."""
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<MessageDB(id={self.id}, role={self.role}, content='{preview}')>"


class AnalysisResultDB(Base):
    """Database model for cached TAJINE analysis results."""

    __tablename__ = "analysis_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    cognitive_level: Mapped[str] = mapped_column(String(50), nullable=True)

    # Territories analyzed (array of department codes)
    department_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String(3)), nullable=True)

    # Analysis result
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Indexes for querying
    __table_args__ = (
        Index("ix_analysis_results_user_created", "user_id", "created_at"),
        Index("ix_analysis_results_dept", "department_codes", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        """String representation."""
        preview = self.query[:50] + "..." if len(self.query) > 50 else self.query
        return f"<AnalysisResultDB(id={self.id}, query='{preview}')>"
