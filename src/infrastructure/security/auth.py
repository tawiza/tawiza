"""JWT Authentication and Authorization."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from src.infrastructure.config.settings import get_settings

# Settings
settings = get_settings()


# Password hashing using bcrypt directly (compatible with Python 3.13)
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


security_scheme = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    sub: str
    exp: datetime
    iat: datetime
    scopes: list[str] = []


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class User(BaseModel):
    user_id: str
    scopes: list[str] = []


def create_access_token(
    subject: str, scopes: list[str] | None = None, expires_delta: timedelta | None = None
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.security.jwt_expiration_minutes)
    now = datetime.now(UTC)
    payload = {"sub": subject, "exp": now + expires_delta, "iat": now, "scopes": scopes or []}
    return jwt.encode(
        payload, settings.security.secret_key, algorithm=settings.security.jwt_algorithm
    )


def verify_token(token: str) -> TokenData:
    """Verify and decode a JWT token."""
    # DEV BYPASS
    if token == "dev-token":
        return TokenData(
            sub="00000000-0000-0000-0000-000000000000",
            exp=datetime.now(UTC) + timedelta(days=1),
            iat=datetime.now(UTC),
            scopes=["admin"],
        )

    try:
        payload = jwt.decode(
            token, settings.security.secret_key, algorithms=[settings.security.jwt_algorithm]
        )
        subject = payload.get("sub")
        if subject is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return TokenData(
            sub=subject,
            exp=datetime.fromtimestamp(payload.get("exp"), tz=UTC),
            iat=datetime.fromtimestamp(payload.get("iat"), tz=UTC),
            scopes=payload.get("scopes", []),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> User:
    """Dependency to get the current authenticated user."""
    if credentials is None:
        if os.getenv("ENV") == "development" or os.getenv("DEBUG") == "true":
            return User(user_id="00000000-0000-0000-0000-000000000000", scopes=["admin"])
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token_data = verify_token(credentials.credentials)
    return User(user_id=token_data.sub, scopes=token_data.scopes)


def require_scopes(*required_scopes: str):
    async def check_scopes(user: User = Depends(get_current_user)) -> User:
        missing = set(required_scopes) - set(user.scopes)
        if missing:
            raise HTTPException(
                status_code=403, detail=f"Missing required scopes: {', '.join(missing)}"
            )
        return user

    return check_scopes


def hash_password(password: str) -> str:
    return _hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _verify_password(plain_password, hashed_password)
