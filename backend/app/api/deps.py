"""Common API dependencies."""
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user, get_current_user
from app.database import get_db
from app.models.user import User
from app.services.logger import RequestLogger
from app.services.router import ModelRouter


async def get_model_router(db: AsyncSession = Depends(get_db)) -> ModelRouter:
    """Get model router instance."""
    return ModelRouter(db)


async def get_request_logger(db: AsyncSession = Depends(get_db)) -> RequestLogger:
    """Get request logger instance."""
    return RequestLogger(db)


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    # Check for forwarded headers (reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if request.client:
        return request.client.host
    
    return None
