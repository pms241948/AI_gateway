"""Ollama provider implementation."""
import json
import time
from typing import AsyncIterator, Optional

import httpx

from app.providers.base import BaseProvider, ProviderConfig, ProviderResponse
from app.schemas.openai import ChatCompletionRequest, EmbeddingRequest


class OllamaProvider(BaseProvider):
    """Provider for Ollama API."""
    
    async def chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ProviderResponse:
        """Perform a chat completion using Ollama's native API."""
        start_time = time.time()
        
        # Ollama supports OpenAI-compatible endpoint
        url = f"{self.config.base_url.rstrip('/')}/api/chat"
        
        # Convert messages to Ollama format
        messages = []
        for msg in request.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content or "",
            })
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        
        # Add options
        options = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.top_p is not None:
            options["top_p"] = request.top_p
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        
        if options:
            payload["options"] = options
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(url, json=payload)
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code != 200:
                    return ProviderResponse(
                        success=False,
                        error_message=f"Ollama returned {response.status_code}: {response.text}",
                        error_code=str(response.status_code),
                        latency_ms=latency_ms,
                    )
                
                data = response.json()
                
                # Extract Ollama response format
                message = data.get("message", {})
                
                # Calculate token usage from eval_count and prompt_eval_count
                input_tokens = data.get("prompt_eval_count")
                output_tokens = data.get("eval_count")
                total_tokens = None
                if input_tokens and output_tokens:
                    total_tokens = input_tokens + output_tokens
                
                return ProviderResponse(
                    success=True,
                    content=message.get("content"),
                    model=data.get("model", self.model_name),
                    finish_reason="stop" if data.get("done") else None,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
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
        """Perform a streaming chat completion using Ollama."""
        url = f"{self.config.base_url.rstrip('/')}/api/chat"
        
        messages = []
        for msg in request.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content or "",
            })
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
        
        options = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        
        if options:
            payload["options"] = options
        
        request_id = f"chatcmpl-{int(time.time())}"
        created = int(time.time())
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        error = await response.aread()
                        yield f"data: {json.dumps({'error': error.decode()})}\n\n"
                        return
                    
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            message = data.get("message", {})
                            content = message.get("content", "")
                            done = data.get("done", False)
                            
                            # Convert to OpenAI format
                            chunk = {
                                "id": request_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": self.model_name,
                                "choices": [{
                                    "index": 0,
                                    "delta": {
                                        "content": content,
                                    } if content else {},
                                    "finish_reason": "stop" if done else None,
                                }],
                            }
                            
                            yield f"data: {json.dumps(chunk)}\n\n"
                            
                            if done:
                                yield "data: [DONE]\n\n"
                                
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    async def embeddings(
        self,
        request: EmbeddingRequest,
    ) -> ProviderResponse:
        """Generate embeddings using Ollama."""
        start_time = time.time()
        
        url = f"{self.config.base_url.rstrip('/')}/api/embeddings"
        
        # Handle single or multiple inputs
        inputs = request.input if isinstance(request.input, list) else [request.input]
        
        all_embeddings = []
        total_latency = 0
        
        for text in inputs:
            payload = {
                "model": self.model_name,
                "prompt": text,
            }
            
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                    response = await client.post(url, json=payload)
                    
                    if response.status_code != 200:
                        return ProviderResponse(
                            success=False,
                            error_message=f"Ollama returned {response.status_code}",
                            error_code=str(response.status_code),
                            latency_ms=int((time.time() - start_time) * 1000),
                        )
                    
                    data = response.json()
                    embedding = data.get("embedding", [])
                    all_embeddings.append(embedding)
                    
            except Exception as e:
                return ProviderResponse(
                    success=False,
                    error_message=str(e),
                    error_code="connection_error",
                    latency_ms=int((time.time() - start_time) * 1000),
                )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return ProviderResponse(
            success=True,
            embeddings=all_embeddings,
            model=self.model_name,
            latency_ms=latency_ms,
        )
    
    async def health_check(self) -> tuple[bool, Optional[int], Optional[str]]:
        """Check if Ollama is healthy."""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Ollama has a simple API endpoint to list models
                url = f"{self.config.base_url.rstrip('/')}/api/tags"
                response = await client.get(url)
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code == 200:
                    # Check if our model exists
                    data = response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    
                    # Model name might be with or without tag
                    model_exists = any(
                        self.model_name in m or m.startswith(self.model_name.split(":")[0])
                        for m in models
                    )
                    
                    if model_exists or not models:  # Accept if no models listed (might be loading)
                        return True, latency_ms, None
                    else:
                        return False, latency_ms, f"Model {self.model_name} not found"
                else:
                    return False, latency_ms, f"Status {response.status_code}"
                    
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return False, latency_ms, str(e)
