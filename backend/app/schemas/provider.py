"""Provider-related Pydantic schemas."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ProviderBase(BaseModel):
    """Base provider schema."""
    name: str = Field(..., min_length=1, max_length=255)
    provider_type: str = Field(
        ...,
        description="Provider type: openai, anthropic, ollama, vllm, openai_compatible"
    )
    base_url: str = Field(..., description="Base URL for the provider API")


class ProviderCreate(ProviderBase):
    """Schema for creating a provider."""
    auth_type: str = Field("none", description="Authentication type: none, api_key, bearer")
    auth_credentials: Optional[str] = Field(None, description="API key or bearer token")
    default_headers: Optional[Dict[str, str]] = None
    timeout_seconds: int = Field(60, ge=1, le=300)
    max_retries: int = Field(3, ge=0, le=10)


class ProviderUpdate(BaseModel):
    """Schema for updating a provider."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: Optional[str] = None
    auth_credentials: Optional[str] = None
    default_headers: Optional[Dict[str, str]] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300)
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    is_active: Optional[bool] = None


class ProviderResponse(ProviderBase):
    """Schema for provider response."""
    id: UUID
    auth_type: str
    default_headers: Optional[Dict[str, str]] = None
    timeout_seconds: int
    max_retries: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProviderTestRequest(BaseModel):
    """Schema for testing a provider connection."""
    test_prompt: Optional[str] = Field(
        "Hello",
        description="Simple prompt for connection test"
    )


class ProviderTestResult(BaseModel):
    """Schema for provider test result."""
    success: bool
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    response_preview: Optional[str] = None
