"""Authentication API endpoints.

Provides JWT-based authentication with access and refresh tokens,
persisted in PostgreSQL.
"""

import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.settings import get_settings
from src.infrastructure.persistence.database import get_db_session
from src.infrastructure.persistence.repositories.user_repository import (
    RefreshTokenRepository,
    UserRepository,
)
from src.infrastructure.security.auth import (
    User as AuthUser,
)
from src.infrastructure.security.auth import (
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

# Rate limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)


# --- Pydantic Models ---


class LoginRequest(BaseModel):
    """Login request body."""

    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password")


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Expiration in seconds")


class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    name: str
    role: str
    preferences: dict
    created_at: str
    last_login: str | None = None


class RegisterRequest(BaseModel):
    """Registration request."""

    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=2)


class UpdatePreferencesRequest(BaseModel):
    """Update user preferences."""

    theme: str | None = None
    default_level: str | None = None
    notifications: bool | None = None
    language: str | None = None


# --- Helper to ensure admin exists ---


async def ensure_admin_exists(session: AsyncSession) -> None:
    """Create default admin user if not exists.

    SECURITY: Admin credentials must be set via environment variables.
    If not set, admin creation is skipped for security.
    """
    # Get admin credentials from environment
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_name = os.getenv("ADMIN_NAME", "Administrateur")

    # Skip if environment variables not set (security measure)
    if not admin_email or not admin_password:
        logger.debug(
            "ADMIN_EMAIL or ADMIN_PASSWORD not set - skipping default admin creation. "
            "Set these environment variables to create an initial admin user."
        )
        return

    # Validate password length
    if len(admin_password) < 12:
        logger.warning(
            "ADMIN_PASSWORD must be at least 12 characters for security. Skipping admin creation."
        )
        return

    user_repo = UserRepository(session)
    admin = await user_repo.get_by_email(admin_email)

    if not admin:
        await user_repo.create(
            email=admin_email,
            password=admin_password,
            name=admin_name,
            role="admin",
        )
        await session.commit()
        logger.info(f"Created admin user from environment: {admin_email}")


# --- API Endpoints ---


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Authenticate user and return access token.

    Also sets httpOnly refresh token cookie.
    """
    # Ensure admin exists on first login attempt
    await ensure_admin_exists(session)

    user_repo = UserRepository(session)
    token_repo = RefreshTokenRepository(session)

    user = await user_repo.verify_credentials(login_data.email, login_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last login
    await user_repo.update_last_login(user)

    # Create tokens
    access_token = create_access_token(
        subject=str(user.id),
        scopes=[user.role],
    )
    refresh_token = await token_repo.create(user.id)

    await session.commit()

    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token.token,
        httponly=True,
        secure=False,  # Set True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.security.jwt_expiration_minutes * 60,
    )


@router.post("/login/form", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login_form(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    """OAuth2 compatible login endpoint."""
    login_data = LoginRequest(email=form_data.username, password=form_data.password)
    return await login(request, response, login_data, session)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
    session: AsyncSession = Depends(get_db_session),
):
    """Refresh access token using refresh token cookie."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    token_repo = RefreshTokenRepository(session)
    user_repo = UserRepository(session)

    token = await token_repo.get_by_token(refresh_token)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await user_repo.get_by_id(token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Create new access token
    access_token = create_access_token(
        subject=str(user.id),
        scopes=[user.role],
    )

    # Rotate refresh token
    await token_repo.revoke(refresh_token)
    new_token = await token_repo.create(user.id)

    await session.commit()

    response.set_cookie(
        key="refresh_token",
        value=new_token.token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.security.jwt_expiration_minutes * 60,
    )


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
    session: AsyncSession = Depends(get_db_session),
):
    """Logout user and invalidate refresh token."""
    if refresh_token:
        token_repo = RefreshTokenRepository(session)
        await token_repo.revoke(refresh_token)
        await session.commit()

    response.delete_cookie("refresh_token")

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Get current user profile."""
    from uuid import UUID

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(UUID(current_user.user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        preferences=user.preferences,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.put("/me/preferences", response_model=UserResponse)
async def update_preferences(
    request: UpdatePreferencesRequest,
    current_user: AuthUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Update current user preferences."""
    from uuid import UUID

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(UUID(current_user.user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update preferences
    updates = request.model_dump(exclude_unset=True, exclude_none=True)
    if updates:
        user = await user_repo.update_preferences(user, updates)
        await session.commit()

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        preferences=user.preferences,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(
    request: Request,
    register_data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Register a new user."""
    user_repo = UserRepository(session)

    existing = await user_repo.get_by_email(register_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await user_repo.create(
        email=register_data.email,
        password=register_data.password,
        name=register_data.name,
        role="analyst",  # Default role
    )

    await session.commit()

    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        preferences=user.preferences,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )
