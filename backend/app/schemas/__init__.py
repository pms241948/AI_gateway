"""Pydantic schemas package."""
from app.schemas.openai import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelListResponse,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    Token,
    TokenPayload,
)
from app.schemas.provider import (
    ProviderCreate,
    ProviderUpdate,
    ProviderResponse,
    ProviderTestResult,
)
from app.schemas.model import (
    ModelCreate,
    ModelUpdate,
    ModelResponse,
    ModelTestRequest,
    ModelTestResponse,
)
from app.schemas.logs import (
    RequestLogResponse,
    RequestLogFilter,
    AuditLogResponse,
    DashboardStats,
)

__all__ = [
    # OpenAI compatible
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "ModelListResponse",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "Token",
    "TokenPayload",
    # Provider
    "ProviderCreate",
    "ProviderUpdate",
    "ProviderResponse",
    "ProviderTestResult",
    # Model
    "ModelCreate",
    "ModelUpdate",
    "ModelResponse",
    "ModelTestRequest",
    "ModelTestResponse",
    # Logs
    "RequestLogResponse",
    "RequestLogFilter",
    "AuditLogResponse",
    "DashboardStats",
]
