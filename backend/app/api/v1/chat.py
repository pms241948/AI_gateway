"""Chat completions API endpoint."""
import time
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_model_router, get_request_logger
from app.config import get_settings
from app.core.auth import get_current_user
from app.core.exceptions import AIGatewayException
from app.database import get_db
from app.models.user import User
from app.schemas.openai import ChatCompletionRequest, ChatCompletionResponse
from app.services.logger import RequestLogger
from app.services.masking import get_masking_service, PIIMaskingService
from app.services.normalizer import ResponseNormalizer
from app.services.router import ModelRouter, AccessDeniedError

router = APIRouter(tags=["Chat"])
settings = get_settings()


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    router_service: ModelRouter = Depends(get_model_router),
    logger: RequestLogger = Depends(get_request_logger),
    db: AsyncSession = Depends(get_db),
):
    """Create a chat completion.
    
    OpenAI-compatible endpoint for chat completions.
    Supports both streaming and non-streaming responses.
    """
    start_time = time.time()
    pii_entities_found = []
    
    try:
        # Apply PII masking to request if enabled
        masked_request = request
        if settings.pii_masking_enabled and settings.pii_mask_request:
            try:
                masking_service = get_masking_service()
                masked_messages, pii_entities = masking_service.mask_chat_messages(
                    [m.model_dump() for m in request.messages],
                    language=settings.pii_language,
                )
                pii_entities_found = pii_entities
                
                # Create new request with masked messages
                if pii_entities:
                    from app.schemas.openai import ChatMessage
                    masked_request = request.model_copy(
                        update={"messages": [ChatMessage(**m) for m in masked_messages]}
                    )
            except Exception as e:
                # Log masking error but continue with original request
                import logging
                logging.warning(f"PII masking failed: {e}")
        
        # Route request to appropriate model/endpoint
        model, endpoint, provider = await router_service.route_request(
            masked_request.model,
            current_user,
        )
        
        # Handle streaming
        if masked_request.stream:
            return StreamingResponse(
                stream_completion(
                    masked_request,
                    model,
                    endpoint,
                    provider,
                    current_user,
                    logger,
                    db,
                    pii_entities_found,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        
        # Non-streaming request
        provider_response = await provider.chat_completion(masked_request)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        if not provider_response.success:
            # Log failed request
            await logger.log_request(
                user=current_user,
                model_id=model.id,
                provider_id=endpoint.provider_id,
                endpoint="/v1/chat/completions",
                method="POST",
                status_code=502,
                latency_ms=latency_ms,
                provider_response=provider_response,
                request_metadata={
                    "model_alias": request.model,
                    "pii_masked": len(pii_entities_found) > 0,
                    "pii_entities_count": len(pii_entities_found),
                },
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
        response = ResponseNormalizer.normalize_chat_completion(
            provider_response,
            request.model,
        )
        
        # Log successful request
        await logger.log_request(
            user=current_user,
            model_id=model.id,
            provider_id=endpoint.provider_id,
            endpoint="/v1/chat/completions",
            method="POST",
            status_code=200,
            latency_ms=latency_ms,
            provider_response=provider_response,
            request_metadata={
                "model_alias": request.model,
                "pii_masked": len(pii_entities_found) > 0,
                "pii_entities_count": len(pii_entities_found),
            },
        )
        await db.commit()
        
        return response
    
    except AccessDeniedError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log access denied
        await logger.log_request(
            user=current_user,
            model_id=None,
            provider_id=None,
            endpoint="/v1/chat/completions",
            method="POST",
            status_code=403,
            latency_ms=latency_ms,
            request_metadata={"model_alias": request.model, "error": "Access denied"},
        )
        await db.commit()
        
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "message": f"Access denied to model: {e.alias}. Contact your administrator to request access.",
                    "type": "access_denied",
                    "code": 403,
                }
            },
        )
        
    except AIGatewayException as e:
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log error
        await logger.log_request(
            user=current_user,
            model_id=None,
            provider_id=None,
            endpoint="/v1/chat/completions",
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


async def stream_completion(
    request: ChatCompletionRequest,
    model,
    endpoint,
    provider,
    user: User,
    logger: RequestLogger,
    db: AsyncSession,
    pii_entities_found: list = None,
):
    """Stream chat completion response."""
    start_time = time.time()
    pii_entities_found = pii_entities_found or []
    
    try:
        async for chunk in provider.chat_completion_stream(request):
            yield chunk
    finally:
        # Log streaming request
        latency_ms = int((time.time() - start_time) * 1000)
        await logger.log_request(
            user=user,
            model_id=model.id,
            provider_id=endpoint.provider_id,
            endpoint="/v1/chat/completions",
            method="POST",
            status_code=200,
            latency_ms=latency_ms,
            request_metadata={
                "model_alias": request.model,
                "stream": True,
                "pii_masked": len(pii_entities_found) > 0,
                "pii_entities_count": len(pii_entities_found),
            },
        )
        await db.commit()
