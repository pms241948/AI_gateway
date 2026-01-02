"""Chat completions API endpoint."""
import time
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_model_router, get_request_logger
from app.core.auth import get_current_user
from app.core.exceptions import AIGatewayException
from app.database import get_db
from app.models.user import User
from app.schemas.openai import ChatCompletionRequest, ChatCompletionResponse
from app.services.logger import RequestLogger
from app.services.normalizer import ResponseNormalizer
from app.services.router import ModelRouter, AccessDeniedError

router = APIRouter(tags=["Chat"])


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
    
    try:
        # Route request to appropriate model/endpoint
        model, endpoint, provider = await router_service.route_request(
            request.model,
            current_user,
        )
        
        # Handle streaming
        if request.stream:
            return StreamingResponse(
                stream_completion(
                    request,
                    model,
                    endpoint,
                    provider,
                    current_user,
                    logger,
                    db,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        
        # Non-streaming request
        provider_response = await provider.chat_completion(request)
        
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
            request_metadata={"model_alias": request.model},
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
):
    """Stream chat completion response."""
    start_time = time.time()
    
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
            request_metadata={"model_alias": request.model, "stream": True},
        )
        await db.commit()
