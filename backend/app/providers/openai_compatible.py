"""OpenAI-compatible provider implementation."""
import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.providers.base import BaseProvider, ProviderConfig, ProviderResponse
from app.schemas.openai import ChatCompletionRequest, EmbeddingRequest


class OpenAICompatibleProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs (vLLM, LocalAI, etc.)."""
    
    async def chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ProviderResponse:
        """Perform a chat completion request."""
        start_time = time.time()
        
        url = f"{self.config.base_url.rstrip('/')}/v1/chat/completions"
        
        # Build request payload
        payload = {
            "model": self.model_name,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
            "stream": False,
        }
        
        # Add optional parameters
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stop is not None:
            payload["stop"] = request.stop
        if request.presence_penalty is not None:
            payload["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            payload["frequency_penalty"] = request.frequency_penalty
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code != 200:
                    error_body = response.text
                    return ProviderResponse(
                        success=False,
                        error_message=f"Provider returned {response.status_code}: {error_body}",
                        error_code=str(response.status_code),
                        latency_ms=latency_ms,
                    )
                
                data = response.json()
                
                # Extract response
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                usage = data.get("usage", {})
                
                return ProviderResponse(
                    success=True,
                    content=message.get("content"),
                    model=data.get("model", self.model_name),
                    finish_reason=choice.get("finish_reason"),
                    input_tokens=usage.get("prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    function_call=message.get("function_call"),
                    tool_calls=message.get("tool_calls"),
                    latency_ms=latency_ms,
                    raw_response=data,
                )
                
        except httpx.TimeoutException:
            return ProviderResponse(
                success=False,
                error_message="Request timed out",
                error_code="timeout",
                latency_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return ProviderResponse(
                success=False,
                error_message=str(e),
                error_code="connection_error",
                latency_ms=int((time.time() - start_time) * 1000),
            )
    
    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[str]:
        """Perform a streaming chat completion request."""
        url = f"{self.config.base_url.rstrip('/')}/v1/chat/completions"
        
        payload = {
            "model": self.model_name,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
            "stream": True,
        }
        
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stop is not None:
            payload["stop"] = request.stop
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield f"data: {json.dumps({'error': error_body.decode()})}\n\n"
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            yield f"{line}\n\n"
                        elif line.strip():
                            yield f"data: {line}\n\n"
                            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    async def embeddings(
        self,
        request: EmbeddingRequest,
    ) -> ProviderResponse:
        """Generate embeddings."""
        start_time = time.time()
        
        url = f"{self.config.base_url.rstrip('/')}/v1/embeddings"
        
        payload = {
            "model": self.model_name,
            "input": request.input,
        }
        
        if request.encoding_format:
            payload["encoding_format"] = request.encoding_format
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code != 200:
                    return ProviderResponse(
                        success=False,
                        error_message=f"Provider returned {response.status_code}",
                        error_code=str(response.status_code),
                        latency_ms=latency_ms,
                    )
                
                data = response.json()
                usage = data.get("usage", {})
                
                # Extract embeddings
                embeddings = [item["embedding"] for item in data.get("data", [])]
                
                return ProviderResponse(
                    success=True,
                    embeddings=embeddings,
                    model=data.get("model", self.model_name),
                    input_tokens=usage.get("prompt_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    latency_ms=latency_ms,
                    raw_response=data,
                )
                
        except Exception as e:
            return ProviderResponse(
                success=False,
                error_message=str(e),
                error_code="connection_error",
                latency_ms=int((time.time() - start_time) * 1000),
            )
    
    async def health_check(self) -> tuple[bool, Optional[int], Optional[str]]:
        """Check if the provider is healthy."""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Try to list models or hit a simple endpoint
                url = f"{self.config.base_url.rstrip('/')}/v1/models"
                response = await client.get(url, headers=self._get_headers())
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code == 200:
                    return True, latency_ms, None
                else:
                    return False, latency_ms, f"Status {response.status_code}"
                    
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return False, latency_ms, str(e)
