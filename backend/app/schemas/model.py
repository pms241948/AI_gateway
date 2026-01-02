"""Model-related Pydantic schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ModelEndpointCreate(BaseModel):
    """Schema for creating a model endpoint."""
    provider_id: UUID
    provider_model_name: str = Field(..., description="Actual model name at the provider")
    priority: int = Field(1, ge=1, le=100)
    weight: int = Field(100, ge=1, le=1000)


class ModelEndpointResponse(BaseModel):
    """Schema for model endpoint response."""
    id: UUID
    provider_id: UUID
    provider_model_name: str
    priority: int
    weight: int
    is_active: bool

    class Config:
        from_attributes = True


class ModelPolicyCreate(BaseModel):
    """Schema for creating a model policy."""
    max_tokens: Optional[int] = Field(None, ge=1)
    rate_limit_rpm: Optional[int] = Field(None, ge=1)
    rate_limit_tpm: Optional[int] = Field(None, ge=1)
    max_concurrent: Optional[int] = Field(None, ge=1)
    cost_per_1k_input: Optional[float] = Field(None, ge=0)
    cost_per_1k_output: Optional[float] = Field(None, ge=0)


class ModelBase(BaseModel):
    """Base model schema."""
    alias: str = Field(..., min_length=1, max_length=255, description="Unique model alias")
    display_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    model_type: str = Field("chat", description="Model type: chat, embedding, rerank")
    capabilities: Optional[Dict[str, Any]] = Field(
        None,
        description="Model capabilities: chat, embeddings, vision, function_calling"
    )


class ModelCreate(ModelBase):
    """Schema for creating a model."""
    endpoints: List[ModelEndpointCreate] = Field(..., min_length=1)
    policy: Optional[ModelPolicyCreate] = None
    requires_approval: bool = False


class ModelUpdate(BaseModel):
    """Schema for updating a model."""
    alias: Optional[str] = Field(None, min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    model_type: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ModelResponse(ModelBase):
    """Schema for model response."""
    id: UUID
    is_active: bool
    requires_approval: bool
    approval_status: str
    endpoints: List[ModelEndpointResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelTestRequest(BaseModel):
    """Schema for testing a model."""
    prompt: str = Field(
        "Hello, how are you?",
        description="Test prompt to send to the model"
    )
    max_tokens: Optional[int] = Field(50, ge=1, le=1000)


class ModelTestResponse(BaseModel):
    """Schema for model test result."""
    success: bool
    latency_ms: Optional[int] = None
    response: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error_message: Optional[str] = None
    provider_used: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Schema for health check result."""
    id: UUID
    model_id: UUID
    endpoint_id: UUID
    is_healthy: bool
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    checked_at: datetime

    class Config:
        from_attributes = True


class SecurityScanRequest(BaseModel):
    """Schema for initiating a security scan."""
    scanner_type: str = Field(
        "promptfoo",
        description="Scanner type: promptfoo, garak, ps-fuzz"
    )
    config: Optional[Dict[str, Any]] = None


class SecurityScanResponse(BaseModel):
    """Schema for security scan result."""
    id: UUID
    model_id: UUID
    scanner_type: str
    scan_status: str
    summary: Optional[Dict[str, Any]] = None
    recommendation: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModelAccessUpdate(BaseModel):
    """Schema for updating model access."""
    organization_ids: Optional[List[UUID]] = None
    group_ids: Optional[List[UUID]] = None
    user_ids: Optional[List[UUID]] = None
