"""Response normalization service."""
import time
import uuid
from typing import List, Optional

from app.providers.base import ProviderResponse
from app.schemas.openai import (
    ChatCompletionChoice,
    ChatCompletionResponse,
    ChatCompletionUsage,
    ChatMessage,
    EmbeddingData,
    EmbeddingResponse,
    EmbeddingUsage,
)


class ResponseNormalizer:
    """Service for normalizing provider responses to OpenAI format."""
    
    @staticmethod
    def normalize_chat_completion(
        provider_response: ProviderResponse,
        model_alias: str,
        request_id: Optional[str] = None,
    ) -> ChatCompletionResponse:
        """Normalize a provider response to OpenAI chat completion format."""
        if request_id is None:
            request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        
        # Build the response message
        message = ChatMessage(
            role="assistant",
            content=provider_response.content,
            function_call=provider_response.function_call,
            tool_calls=provider_response.tool_calls,
        )
        
        # Build choice
        choice = ChatCompletionChoice(
            index=0,
            message=message,
            finish_reason=provider_response.finish_reason or "stop",
        )
        
        # Build usage if available
        usage = None
        if provider_response.input_tokens is not None or provider_response.output_tokens is not None:
            usage = ChatCompletionUsage(
                prompt_tokens=provider_response.input_tokens or 0,
                completion_tokens=provider_response.output_tokens or 0,
                total_tokens=provider_response.total_tokens or (
                    (provider_response.input_tokens or 0) + (provider_response.output_tokens or 0)
                ),
            )
        
        return ChatCompletionResponse(
            id=request_id,
            object="chat.completion",
            created=int(time.time()),
            model=model_alias,
            choices=[choice],
            usage=usage,
        )
    
    @staticmethod
    def normalize_embeddings(
        provider_response: ProviderResponse,
        model_alias: str,
    ) -> EmbeddingResponse:
        """Normalize a provider response to OpenAI embeddings format."""
        data = []
        
        if provider_response.embeddings:
            for i, embedding in enumerate(provider_response.embeddings):
                data.append(EmbeddingData(
                    index=i,
                    object="embedding",
                    embedding=embedding,
                ))
        
        usage = EmbeddingUsage(
            prompt_tokens=provider_response.input_tokens or 0,
            total_tokens=provider_response.total_tokens or provider_response.input_tokens or 0,
        )
        
        return EmbeddingResponse(
            object="list",
            data=data,
            model=model_alias,
            usage=usage,
        )
    
    @staticmethod
    def normalize_error(
        error_message: str,
        error_type: str = "api_error",
        status_code: int = 500,
    ) -> dict:
        """Create an OpenAI-compatible error response."""
        return {
            "error": {
                "message": error_message,
                "type": error_type,
                "code": str(status_code),
            }
        }
