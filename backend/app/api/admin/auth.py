"""Authentication API endpoints."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_request_logger
from app.config import get_settings
from app.core.auth import get_current_active_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.database import get_db
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.logger import RequestLogger

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
    logger: RequestLogger = Depends(get_request_logger),
):
    """Login with username/email and password."""
    # Find user by username or email
    result = await db.execute(
        select(User).where(
            (User.username == credentials.username) | (User.email == credentials.username)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User account is disabled")
    
    # Create tokens
    access_token = create_access_token(
        subject=str(user.id),
        additional_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    refresh_token = create_refresh_token(subject=str(user.id))
    
    # Log login
    await logger.log_audit(
        user=user,
        action="login",
        resource_type="user",
        resource_id=user.id,
        ip_address=get_client_ip(request),
    )
    await db.commit()
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    logger: RequestLogger = Depends(get_request_logger),
):
    """Register a new user account."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        organization_id=user_data.organization_id,
        group_id=user_data.group_id,
        is_active=True,
        is_superuser=False,
        auth_provider="local",
    )
    
    db.add(user)
    await db.flush()
    
    # Log registration
    await logger.log_audit(
        user=user,
        action="register",
        resource_type="user",
        resource_id=user.id,
        ip_address=get_client_ip(request),
    )
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        auth_provider=user.auth_provider,
        organization_id=user.organization_id,
        group_id=user.group_id,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    payload = verify_token(refresh_token, expected_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    # Verify user still exists and is active
    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    
    # Create new tokens
    access_token = create_access_token(
        subject=str(user.id),
        additional_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    new_refresh_token = create_refresh_token(subject=str(user.id))
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """Get current authenticated user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        auth_provider=current_user.auth_provider,
        organization_id=current_user.organization_id,
        group_id=current_user.group_id,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )
