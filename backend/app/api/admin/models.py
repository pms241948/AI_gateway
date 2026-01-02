"""Model management API endpoints."""
import time
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_model_router
from app.core.auth import get_current_active_user, get_current_superuser
from app.database import get_db
from app.models.llm_model import LLMModel, ModelEndpoint, ModelPolicy
from app.models.logs import HealthCheckResult
from app.models.provider import Provider
from app.models.user import User
from app.schemas.model import (
    HealthCheckResponse,
    ModelCreate,
    ModelResponse,
    ModelTestRequest,
    ModelTestResponse,
    ModelUpdate,
)
from app.schemas.openai import ChatCompletionRequest, ChatMessage
from app.services.router import ModelRouter

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("", response_model=List[ModelResponse])
async def list_models(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all models with their endpoints."""
    query = select(LLMModel).options(
        selectinload(LLMModel.endpoints)
    ).order_by(LLMModel.alias)
    
    if not include_inactive and not current_user.is_superuser:
        query = query.where(LLMModel.is_active == True)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=ModelResponse)
async def create_model(
    model_data: ModelCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Create a new model (admin only)."""
    # Check if alias already exists
    result = await db.execute(
        select(LLMModel).where(LLMModel.alias == model_data.alias)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Model alias already exists")
    
    # Create model
    model = LLMModel(
        alias=model_data.alias,
        display_name=model_data.display_name,
        description=model_data.description,
        model_type=model_data.model_type,
        capabilities=model_data.capabilities,
        is_active=True,
        requires_approval=model_data.requires_approval,
        approval_status="approved" if not model_data.requires_approval else "pending",
    )
    
    db.add(model)
    await db.flush()
    
    # Create endpoints
    for ep_data in model_data.endpoints:
        # Verify provider exists
        result = await db.execute(
            select(Provider).where(Provider.id == ep_data.provider_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Provider {ep_data.provider_id} not found"
            )
        
        endpoint = ModelEndpoint(
            model_id=model.id,
            provider_id=ep_data.provider_id,
            provider_model_name=ep_data.provider_model_name,
            priority=ep_data.priority,
            weight=ep_data.weight,
            is_active=True,
        )
        db.add(endpoint)
    
    # Create policy if provided
    if model_data.policy:
        policy = ModelPolicy(
            model_id=model.id,
            max_tokens=model_data.policy.max_tokens,
            rate_limit_rpm=model_data.policy.rate_limit_rpm,
            rate_limit_tpm=model_data.policy.rate_limit_tpm,
            max_concurrent=model_data.policy.max_concurrent,
            cost_per_1k_input=model_data.policy.cost_per_1k_input,
            cost_per_1k_output=model_data.policy.cost_per_1k_output,
        )
        db.add(policy)
    
    await db.commit()
    
    # Reload with endpoints
    result = await db.execute(
        select(LLMModel)
        .where(LLMModel.id == model.id)
        .options(selectinload(LLMModel.endpoints))
    )
    return result.scalar_one()


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a model by ID."""
    result = await db.execute(
        select(LLMModel)
        .where(LLMModel.id == model_id)
        .options(selectinload(LLMModel.endpoints))
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return model


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: UUID,
    model_update: ModelUpdate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Update a model (admin only)."""
    result = await db.execute(
        select(LLMModel)
        .where(LLMModel.id == model_id)
        .options(selectinload(LLMModel.endpoints))
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Update fields
    update_data = model_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(model, field, value)
    
    await db.commit()
    await db.refresh(model)
    
    return model


@router.delete("/{model_id}")
async def delete_model(
    model_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a model (admin only)."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    await db.delete(model)
    await db.commit()
    
    return {"message": "Model deleted"}


@router.post("/{model_id}/test", response_model=ModelTestResponse)
async def test_model(
    model_id: UUID,
    test_request: ModelTestRequest,
    current_user: User = Depends(get_current_active_user),
    router_service: ModelRouter = Depends(get_model_router),
    db: AsyncSession = Depends(get_db),
):
    """Test a model with a sample prompt."""
    result = await db.execute(
        select(LLMModel)
        .where(LLMModel.id == model_id)
        .options(selectinload(LLMModel.endpoints).selectinload(ModelEndpoint.provider))
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    start_time = time.time()
    
    try:
        # Route and get provider
        _, endpoint, provider = await router_service.route_request(
            model.alias,
            current_user,
        )
        
        # Create test request
        chat_request = ChatCompletionRequest(
            model=model.alias,
            messages=[ChatMessage(role="user", content=test_request.prompt)],
            max_tokens=test_request.max_tokens,
        )
        
        # Execute request
        response = await provider.chat_completion(chat_request)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return ModelTestResponse(
            success=response.success,
            latency_ms=latency_ms,
            response=response.content,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error_message=response.error_message,
            provider_used=endpoint.provider.name if endpoint.provider else None,
        )
        
    except Exception as e:
        return ModelTestResponse(
            success=False,
            latency_ms=int((time.time() - start_time) * 1000),
            error_message=str(e),
        )


@router.post("/{model_id}/health-check", response_model=List[HealthCheckResponse])
async def run_health_check(
    model_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Run health check on all model endpoints."""
    result = await db.execute(
        select(LLMModel)
        .where(LLMModel.id == model_id)
        .options(selectinload(LLMModel.endpoints).selectinload(ModelEndpoint.provider))
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    results = []
    
    for endpoint in model.endpoints:
        provider = endpoint.provider
        
        # Create provider config
        from app.providers.base import ProviderConfig
        config = ProviderConfig(
            base_url=provider.base_url,
            auth_type=provider.auth_type,
            auth_credentials=provider.auth_credentials_encrypted,
            headers=provider.default_headers or {},
            timeout=provider.timeout_seconds,
        )
        
        # Create provider instance
        if provider.provider_type == "ollama":
            from app.providers.ollama_provider import OllamaProvider
            provider_instance = OllamaProvider(config, endpoint.provider_model_name)
        else:
            from app.providers.openai_compatible import OpenAICompatibleProvider
            provider_instance = OpenAICompatibleProvider(config, endpoint.provider_model_name)
        
        # Run health check
        is_healthy, latency_ms, error_message = await provider_instance.health_check()
        
        # Save result
        health_result = HealthCheckResult(
            model_id=model.id,
            endpoint_id=endpoint.id,
            is_healthy=is_healthy,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        db.add(health_result)
        
        results.append(HealthCheckResponse(
            id=health_result.id,
            model_id=model.id,
            endpoint_id=endpoint.id,
            is_healthy=is_healthy,
            latency_ms=latency_ms,
            error_message=error_message,
            checked_at=health_result.checked_at,
        ))
    
    await db.commit()
    
    return results


@router.get("/{model_id}/health-history", response_model=List[HealthCheckResponse])
async def get_health_history(
    model_id: UUID,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get health check history for a model."""
    result = await db.execute(
        select(HealthCheckResult)
        .where(HealthCheckResult.model_id == model_id)
        .order_by(HealthCheckResult.checked_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/{model_id}/approve")
async def approve_model(
    model_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Approve a model for use (admin only)."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model.approval_status = "approved"
    await db.commit()
    
    return {"message": "Model approved"}
