"""Embeddings API endpoint."""
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_model_router, get_request_logger
from app.core.auth import get_current_user
from app.core.exceptions import AIGatewayException
from app.database import get_db
from app.models.user import User
from app.schemas.openai import EmbeddingRequest, EmbeddingResponse
from app.services.logger import RequestLogger
from app.services.normalizer import ResponseNormalizer
from app.services.router import ModelRouter

router = APIRouter(tags=["Embeddings"])


@router.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(
    request: EmbeddingRequest,
    current_user: User = Depends(get_current_user),
    router_service: ModelRouter = Depends(get_model_router),
    logger: RequestLogger = Depends(get_request_logger),
    db: AsyncSession = Depends(get_db),
):
    """Create embeddings for the input text.
    
    OpenAI-compatible endpoint for text embeddings.
    """
    start_time = time.time()
    
    try:
        # Route request to appropriate model/endpoint
        model, endpoint, provider = await router_service.route_request(
            request.model,
            current_user,
        )
        
        # Generate embeddings
        provider_response = await provider.embeddings(request)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        if not provider_response.success:
            # Log failed request
            await logger.log_request(
                user=current_user,
                model_id=model.id,
                provider_id=endpoint.provider_id,
                endpoint="/v1/embeddings",
                method="POST",
                status_code=502,
                latency_ms=latency_ms,
                provider_response=provider_response,
                request_metadata={"model_alias": request.model},
            )
            await db.commit()
            
            return JSONResponse(
                status_code=502,
                content=ResponseNormalizer.normalize_error(
                    provider_response.error_message or "Provider error",
                    "provider_error",
                    502,
                ),
            )
        
        # Normalize response
        response = ResponseNormalizer.normalize_embeddings(
            provider_response,
            request.model,
        )
        
        # Log successful request
        await logger.log_request(
            user=current_user,
            model_id=model.id,
            provider_id=endpoint.provider_id,
            endpoint="/v1/embeddings",
            method="POST",
            status_code=200,
            latency_ms=latency_ms,
            provider_response=provider_response,
            request_metadata={"model_alias": request.model},
        )
        await db.commit()
        
        return response
        
    except AIGatewayException as e:
        latency_ms = int((time.time() - start_time) * 1000)
        
        await logger.log_request(
            user=current_user,
            model_id=None,
            provider_id=None,
            endpoint="/v1/embeddings",
            method="POST",
            status_code=e.status_code,
            latency_ms=latency_ms,
            request_metadata={"model_alias": request.model, "error": e.message},
        )
        await db.commit()
        
        return JSONResponse(
            status_code=e.status_code,
            content=e.to_dict(),
        )
