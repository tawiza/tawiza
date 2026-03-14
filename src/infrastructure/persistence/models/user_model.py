"""Database models for authentication."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.database import Base


class UserDB(Base):
    """Database model for users."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="analyst", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # User preferences stored as JSONB
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "theme": "dark",
            "default_level": "analytical",
            "notifications": True,
            "language": "fr",
        },
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship to refresh tokens
    refresh_tokens: Mapped[list["RefreshTokenDB"]] = relationship(
        "RefreshTokenDB", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<UserDB(id={self.id}, email={self.email}, role={self.role})>"


class RefreshTokenDB(Base):
    """Database model for refresh tokens."""

    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationship to user
    user: Mapped["UserDB"] = relationship("UserDB", back_populates="refresh_tokens")

    # Index for cleanup queries
    __table_args__ = (
        Index("ix_refresh_tokens_expires_at", "expires_at"),
        Index("ix_refresh_tokens_user_revoked", "user_id", "revoked"),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<RefreshTokenDB(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"
