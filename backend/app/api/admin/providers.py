"""Provider management API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user, get_current_superuser
from app.database import get_db
from app.models.provider import Provider
from app.models.user import User
from app.providers.base import ProviderConfig
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.provider import (
    ProviderCreate,
    ProviderResponse,
    ProviderTestResult,
    ProviderUpdate,
)

router = APIRouter(prefix="/providers", tags=["Providers"])


@router.get("", response_model=List[ProviderResponse])
async def list_providers(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all providers."""
    result = await db.execute(
        select(Provider).order_by(Provider.name)
    )
    return result.scalars().all()


@router.post("", response_model=ProviderResponse)
async def create_provider(
    provider_data: ProviderCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Create a new provider (admin only)."""
    # Check if name already exists
    result = await db.execute(
        select(Provider).where(Provider.name == provider_data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Provider name already exists")
    
    provider = Provider(
        name=provider_data.name,
        provider_type=provider_data.provider_type,
        base_url=provider_data.base_url,
        auth_type=provider_data.auth_type,
        auth_credentials_encrypted=provider_data.auth_credentials,  # TODO: Encrypt
        default_headers=provider_data.default_headers,
        timeout_seconds=provider_data.timeout_seconds,
        max_retries=provider_data.max_retries,
        is_active=True,
    )
    
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    
    return provider


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a provider by ID."""
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return provider


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    provider_update: ProviderUpdate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Update a provider (admin only)."""
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Update fields
    update_data = provider_update.model_dump(exclude_unset=True)
    if "auth_credentials" in update_data:
        update_data["auth_credentials_encrypted"] = update_data.pop("auth_credentials")
    
    for field, value in update_data.items():
        setattr(provider, field, value)
    
    await db.commit()
    await db.refresh(provider)
    
    return provider


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a provider (admin only)."""
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    await db.delete(provider)
    await db.commit()
    
    return {"message": "Provider deleted"}


@router.post("/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Test provider connection."""
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Create provider config
    config = ProviderConfig(
        base_url=provider.base_url,
        auth_type=provider.auth_type,
        auth_credentials=provider.auth_credentials_encrypted,
        headers=provider.default_headers or {},
        timeout=provider.timeout_seconds,
        max_retries=provider.max_retries,
    )
    
    # Select provider class based on type
    if provider.provider_type == "ollama":
        provider_instance = OllamaProvider(config, "")  # Empty model for health check
    else:
        provider_instance = OpenAICompatibleProvider(config, "")
    
    # Run health check
    is_healthy, latency_ms, error_message = await provider_instance.health_check()
    
    return ProviderTestResult(
        success=is_healthy,
        latency_ms=latency_ms,
        error_message=error_message,
    )
