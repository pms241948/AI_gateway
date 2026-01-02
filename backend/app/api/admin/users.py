"""User management API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_active_user, get_current_superuser
from app.core.security import generate_api_key, get_password_hash
from app.database import get_db
from app.models.user import ApiKey, User
from app.schemas.user import (
    ApiKeyCreate,
    ApiKeyListResponse,
    ApiKeyResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a user by ID."""
    # Users can view their own profile, admins can view any
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a user."""
    # Users can update their own profile, admins can update any
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.password is not None:
        user.password_hash = get_password_hash(user_update.password)
    if user_update.organization_id is not None:
        user.organization_id = user_update.organization_id
    if user_update.group_id is not None:
        user.group_id = user_update.group_id
    if user_update.is_active is not None and current_user.is_superuser:
        user.is_active = user_update.is_active
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()
    
    return {"message": "User deleted"}


# API Key management
@router.get("/me/api-keys", response_model=List[ApiKeyListResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's API keys."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == current_user.id)
        .order_by(ApiKey.created_at.desc())
    )
    return result.scalars().all()


@router.post("/me/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key for current user."""
    # Generate API key
    full_key, key_hash, key_prefix = generate_api_key()
    
    # Calculate expiration
    expires_at = None
    if key_data.expires_in_days:
        from datetime import datetime, timedelta
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
    
    api_key = ApiKey(
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=key_data.name,
        expires_at=expires_at,
        is_active=True,
    )
    
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    # Return with full key (only time it's visible)
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=full_key,
        key_prefix=api_key.key_prefix,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.delete("/me/api-keys/{key_id}")
async def delete_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an API key."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.id == key_id)
        .where(ApiKey.user_id == current_user.id)
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    await db.delete(api_key)
    await db.commit()
    
    return {"message": "API key deleted"}
