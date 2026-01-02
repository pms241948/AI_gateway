"""Base provider abstract class."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from app.schemas.openai import ChatCompletionRequest, EmbeddingRequest


@dataclass
class ProviderResponse:
    """Standardized response from a provider."""
    
    success: bool
    content: Optional[str] = None
    
    # Token usage
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    
    # Embedding specific
    embeddings: Optional[List[List[float]]] = None
    
    # Metadata
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[int] = None
    
    # Raw response for debugging
    raw_response: Optional[Dict[str, Any]] = None
    
    # Error info
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # Function/tool calling
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class ProviderConfig:
    """Configuration for a provider."""
    
    base_url: str
    auth_type: str = "none"  # none, api_key, bearer
    auth_credentials: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 60
    max_retries: int = 3


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: ProviderConfig, model_name: str):
        """Initialize the provider.
        
        Args:
            config: Provider configuration
            model_name: The model name to use at the provider
        """
        self.config = config
        self.model_name = model_name
    
    @abstractmethod
    async def chat_completion(
        self,
        request: ChatCompletionRequest,
    ) -> ProviderResponse:
        """Perform a chat completion request.
        
        Args:
            request: The chat completion request
            
        Returns:
            ProviderResponse with the completion result
        """
        pass
    
    @abstractmethod
    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
    ) -> AsyncIterator[str]:
        """Perform a streaming chat completion request.
        
        Args:
            request: The chat completion request
            
        Yields:
            SSE-formatted chunks
        """
        pass
    
    @abstractmethod
    async def embeddings(
        self,
        request: EmbeddingRequest,
    ) -> ProviderResponse:
        """Generate embeddings for the input.
        
        Args:
            request: The embedding request
            
        Returns:
            ProviderResponse with embeddings
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> tuple[bool, Optional[int], Optional[str]]:
        """Check if the provider is healthy.
        
        Returns:
            Tuple of (is_healthy, latency_ms, error_message)
        """
        pass
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers including authentication."""
        headers = {
            "Content-Type": "application/json",
            **self.config.headers,
        }
        
        if self.config.auth_type == "api_key" and self.config.auth_credentials:
            headers["Authorization"] = f"Bearer {self.config.auth_credentials}"
        elif self.config.auth_type == "bearer" and self.config.auth_credentials:
            headers["Authorization"] = f"Bearer {self.config.auth_credentials}"
        
        return headers
