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
    """Test provider connection with actual LLM inference."""
    import httpx
    import time
    from app.schemas.openai import ChatCompletionRequest, ChatMessage
    
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
    
    start_time = time.time()
    
    try:
        # First, get available models from the provider
        if provider.provider_type == "ollama":
            url = f"{provider.base_url.rstrip('/')}/api/tags"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return ProviderTestResult(
                        success=False,
                        latency_ms=int((time.time() - start_time) * 1000),
                        error_message=f"Failed to get models: {response.status_code}",
                    )
                data = response.json()
                models = data.get("models", [])
                if not models:
                    return ProviderTestResult(
                        success=False,
                        latency_ms=int((time.time() - start_time) * 1000),
                        error_message="No models available. Please pull a model first (e.g., ollama pull llama3)",
                    )
                # Use the first available model
                model_name = models[0].get("name", "")
        else:
            # For OpenAI compatible, use a default model
            model_name = "gpt-3.5-turbo"
        
        # Create provider instance with the model
        if provider.provider_type == "ollama":
            provider_instance = OllamaProvider(config, model_name)
        else:
            provider_instance = OpenAICompatibleProvider(config, model_name)
        
        # Send test prompt
        test_request = ChatCompletionRequest(
            model=model_name,
            messages=[
                ChatMessage(role="user", content="Say 'Hello! Provider test successful.' in exactly those words.")
            ],
            max_tokens=50,
            temperature=0.1,
        )
        
        response = await provider_instance.chat_completion(test_request)
        latency_ms = int((time.time() - start_time) * 1000)
        
        if response.success:
            # Try to get content from response, or extract from raw_response
            content = response.content
            if not content and response.raw_response:
                # Fallback: try to extract from raw Ollama response
                raw = response.raw_response
                if isinstance(raw, dict):
                    message = raw.get("message", {})
                    # Try content first, then thinking (for models with thinking mode)
                    content = message.get("content", "") or message.get("thinking", "")
            
            return ProviderTestResult(
                success=True,
                latency_ms=latency_ms,
                response_preview=content[:200] if content else "(Empty response from model)",
            )
        else:
            return ProviderTestResult(
                success=False,
                latency_ms=latency_ms,
                error_message=response.error_message,
            )
            
    except Exception as e:
        return ProviderTestResult(
            success=False,
            latency_ms=int((time.time() - start_time) * 1000),
            error_message=str(e),
        )

