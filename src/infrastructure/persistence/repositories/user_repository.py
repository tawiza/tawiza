"""SQLAlchemy implementation of User repository."""

import secrets
from datetime import datetime, timedelta
from uuid import UUID

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.models.user_model import RefreshTokenDB, UserDB
from src.infrastructure.security.auth import hash_password, verify_password


class UserRepository:
    """Repository for user operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with a session.

        Args:
            session: Database session
        """
        self._session = session

    async def get_by_id(self, user_id: UUID) -> UserDB | None:
        """Get a user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None
        """
        return await self._session.get(UserDB, user_id)

    async def get_by_email(self, email: str) -> UserDB | None:
        """Get a user by email.

        Args:
            email: User email

        Returns:
            User or None
        """
        query = select(UserDB).where(UserDB.email == email)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        password: str,
        name: str,
        role: str = "analyst",
    ) -> UserDB:
        """Create a new user.

        Args:
            email: User email
            password: Plain text password (will be hashed)
            name: User name
            role: User role

        Returns:
            Created user
        """
        user = UserDB(
            email=email,
            name=name,
            password_hash=hash_password(password),
            role=role,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        logger.info(f"Created user {email}")
        return user

    async def update_last_login(self, user: UserDB) -> None:
        """Update user's last login timestamp.

        Args:
            user: User to update
        """
        user.last_login = datetime.utcnow()
        await self._session.flush()

    async def update_preferences(
        self, user: UserDB, preferences: dict
    ) -> UserDB:
        """Update user preferences.

        Args:
            user: User to update
            preferences: New preferences (merged with existing)

        Returns:
            Updated user
        """
        # Merge preferences
        current = user.preferences.copy()
        for key, value in preferences.items():
            if value is not None:
                current[key] = value
        user.preferences = current
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def verify_credentials(
        self, email: str, password: str
    ) -> UserDB | None:
        """Verify user credentials.

        Args:
            email: User email
            password: Plain text password

        Returns:
            User if credentials valid, None otherwise
        """
        user = await self.get_by_email(email)
        if user and verify_password(password, user.password_hash):
            return user
        return None


class RefreshTokenRepository:
    """Repository for refresh token operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with a session.

        Args:
            session: Database session
        """
        self._session = session

    async def create(
        self, user_id: UUID, expires_days: int = 7
    ) -> RefreshTokenDB:
        """Create a new refresh token.

        Args:
            user_id: User ID
            expires_days: Token validity in days

        Returns:
            Created refresh token
        """
        token = RefreshTokenDB(
            token=secrets.token_urlsafe(32),
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(days=expires_days),
        )
        self._session.add(token)
        await self._session.flush()
        await self._session.refresh(token)
        return token

    async def get_by_token(self, token: str) -> RefreshTokenDB | None:
        """Get a refresh token by its value.

        Args:
            token: Token value

        Returns:
            RefreshToken or None
        """
        query = select(RefreshTokenDB).where(
            RefreshTokenDB.token == token,
            not RefreshTokenDB.revoked,
            RefreshTokenDB.expires_at > datetime.utcnow(),
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def revoke(self, token: str) -> bool:
        """Revoke a refresh token.

        Args:
            token: Token value

        Returns:
            True if revoked, False if not found
        """
        refresh_token = await self.get_by_token(token)
        if refresh_token:
            refresh_token.revoked = True
            await self._session.flush()
            return True
        return False

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user.

        Args:
            user_id: User ID

        Returns:
            Number of tokens revoked
        """
        query = (
            delete(RefreshTokenDB)
            .where(RefreshTokenDB.user_id == user_id)
            .returning(RefreshTokenDB.id)
        )
        result = await self._session.execute(query)
        count = len(result.all())
        logger.info(f"Revoked {count} tokens for user {user_id}")
        return count

    async def cleanup_expired(self) -> int:
        """Delete expired tokens.

        Returns:
            Number of tokens deleted
        """
        query = delete(RefreshTokenDB).where(
            RefreshTokenDB.expires_at < datetime.utcnow()
        )
        result = await self._session.execute(query)
        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired tokens")
        return count
