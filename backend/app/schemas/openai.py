"""OpenAI-compatible API schemas."""
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ============================================
# Chat Completion Schemas
# ============================================

class ChatMessage(BaseModel):
    """Chat message in a conversation."""
    role: Literal["system", "user", "assistant", "function", "tool"] = Field(
        ..., description="The role of the message author"
    )
    content: Optional[str] = Field(None, description="The content of the message")
    name: Optional[str] = Field(None, description="Optional name of the author")
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    """Request for chat completion."""
    model: str = Field(..., description="Model alias to use")
    messages: List[ChatMessage] = Field(..., description="Messages in the conversation")
    
    # Optional parameters
    temperature: Optional[float] = Field(1.0, ge=0, le=2)
    top_p: Optional[float] = Field(1.0, ge=0, le=1)
    n: Optional[int] = Field(1, ge=1, le=128)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = Field(0, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(0, ge=-2, le=2)
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    
    # Function calling
    functions: Optional[List[Dict[str, Any]]] = None
    function_call: Optional[Union[str, Dict[str, str]]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


class ChatCompletionChoice(BaseModel):
    """A single chat completion choice."""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionUsage(BaseModel):
    """Token usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Response from chat completion."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None
    system_fingerprint: Optional[str] = None


# Streaming response
class ChatCompletionChunkDelta(BaseModel):
    """Delta content in streaming response."""
    role: Optional[str] = None
    content: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionChunkChoice(BaseModel):
    """Choice in streaming response."""
    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """Streaming chunk response."""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]


# ============================================
# Embedding Schemas
# ============================================

class EmbeddingRequest(BaseModel):
    """Request for text embeddings."""
    model: str = Field(..., description="Model alias to use")
    input: Union[str, List[str]] = Field(..., description="Text to embed")
    encoding_format: Optional[str] = Field("float", description="Encoding format")
    user: Optional[str] = None


class EmbeddingData(BaseModel):
    """Single embedding result."""
    index: int
    object: str = "embedding"
    embedding: List[float]


class EmbeddingUsage(BaseModel):
    """Embedding token usage."""
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    """Response from embedding request."""
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage


# ============================================
# Model List Schemas
# ============================================

class ModelInfo(BaseModel):
    """Information about a single model."""
    id: str
    object: str = "model"
    created: int
    owned_by: str = "ai-gateway"
    permission: Optional[List[Dict[str, Any]]] = []
    root: Optional[str] = None
    parent: Optional[str] = None


class ModelListResponse(BaseModel):
    """Response listing available models."""
    object: str = "list"
    data: List[ModelInfo]


# ============================================
# Error Schemas
# ============================================

class ErrorDetail(BaseModel):
    """Error detail following OpenAI format."""
    message: str
    type: str
    param: Optional[str] = None
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response following OpenAI format."""
    error: ErrorDetail
