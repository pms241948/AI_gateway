"""Models API endpoint."""
import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.database import get_db
from app.models.llm_model import LLMModel
from app.models.user import User
from app.schemas.openai import ModelInfo, ModelListResponse

router = APIRouter(tags=["Models"])


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available models.
    
    OpenAI-compatible endpoint for listing models.
    Only returns models the user has access to.
    """
    # Get all active, approved models
    result = await db.execute(
        select(LLMModel)
        .where(LLMModel.is_active == True)
        .where(LLMModel.approval_status == "approved")
        .order_by(LLMModel.alias)
    )
    models = result.scalars().all()
    
    # TODO: Filter by user permissions
    
    # Convert to OpenAI format
    model_infos = []
    for model in models:
        created = int(model.created_at.timestamp()) if model.created_at else int(time.time())
        model_infos.append(ModelInfo(
            id=model.alias,
            object="model",
            created=created,
            owned_by="ai-gateway",
        ))
    
    return ModelListResponse(
        object="list",
        data=model_infos,
    )


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific model by ID (alias).
    
    OpenAI-compatible endpoint for getting model details.
    """
    result = await db.execute(
        select(LLMModel)
        .where(LLMModel.alias == model_id)
        .where(LLMModel.is_active == True)
        .where(LLMModel.approval_status == "approved")
    )
    model = result.scalar_one_or_none()
    
    if not model:
        return {
            "error": {
                "message": f"Model '{model_id}' not found",
                "type": "invalid_request_error",
                "code": "model_not_found",
            }
        }
    
    created = int(model.created_at.timestamp()) if model.created_at else int(time.time())
    
    return ModelInfo(
        id=model.alias,
        object="model",
        created=created,
        owned_by="ai-gateway",
    )
