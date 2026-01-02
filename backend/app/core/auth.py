"""Authentication dependencies and utilities."""
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import verify_api_key, verify_token
from app.database import get_db
from app.models.user import ApiKey, User

settings = get_settings()
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user from JWT or API key."""
    token = None
    
    # Try to get token from HTTPBearer first
    if credentials:
        token = credentials.credentials
    # Fall back to Authorization header
    elif authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
    
    if not token:
        raise AuthenticationError("Missing authentication token")
    
    # Check if it's an API key (starts with sk-)
    if token.startswith("sk-"):
        return await authenticate_api_key(token, db)
    
    # Otherwise, treat as JWT
    return await authenticate_jwt(token, db)


async def authenticate_jwt(token: str, db: AsyncSession) -> User:
    """Authenticate using JWT token."""
    payload = verify_token(token, expected_type="access")
    if not payload:
        raise AuthenticationError("Invalid or expired token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise AuthenticationError("Invalid user ID in token")
    
    result = await db.execute(
        select(User)
        .where(User.id == user_uuid)
        .options(selectinload(User.user_roles))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise AuthenticationError("User not found")
    
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    
    return user


async def authenticate_api_key(key: str, db: AsyncSession) -> User:
    """Authenticate using API key."""
    # Get the key prefix for lookup
    key_prefix = key[:10]
    
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.key_prefix == key_prefix)
        .where(ApiKey.is_active == True)
        .options(selectinload(ApiKey.user))
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise AuthenticationError("Invalid API key")
    
    if not verify_api_key(key, api_key.key_hash):
        raise AuthenticationError("Invalid API key")
    
    # Check expiration
    if api_key.expires_at:
        from datetime import datetime
        if datetime.utcnow() > api_key.expires_at:
            raise AuthenticationError("API key has expired")
    
    user = api_key.user
    if not user or not user.is_active:
        raise AuthenticationError("User account is disabled")
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is active."""
    if not current_user.is_active:
        raise AuthenticationError("User account is disabled")
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensure the current user is a superuser."""
    if not current_user.is_superuser:
        raise AuthorizationError("Superuser privileges required")
    return current_user


def require_permission(resource: str, action: str):
    """Dependency factory to require a specific permission."""
    
    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        # Superusers have all permissions
        if current_user.is_superuser:
            return current_user
        
        # TODO: Check user roles and permissions
        # For now, allow all authenticated users
        return current_user
    
    return permission_checker
