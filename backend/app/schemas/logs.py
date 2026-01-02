"""Log-related Pydantic schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RequestLogResponse(BaseModel):
    """Schema for request log response."""
    id: UUID
    user_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    request_id: str
    endpoint: str
    method: str
    status_code: int
    latency_ms: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost: Optional[float] = None
    request_metadata: Optional[Dict[str, Any]] = None
    request_body: Optional[str] = None  # May be masked or omitted
    response_body: Optional[str] = None  # May be masked or omitted
    body_masked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RequestLogFilter(BaseModel):
    """Schema for filtering request logs."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    user_id: Optional[UUID] = None
    model_id: Optional[UUID] = None
    status_code: Optional[int] = None
    min_latency_ms: Optional[int] = None
    max_latency_ms: Optional[int] = None
    endpoint: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=1000)


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""
    id: UUID
    user_id: Optional[UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[UUID] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogFilter(BaseModel):
    """Schema for filtering audit logs."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    user_id: Optional[UUID] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=1000)


class DashboardStats(BaseModel):
    """Schema for dashboard statistics."""
    total_requests_24h: int
    total_requests_7d: int
    total_requests_30d: int
    active_models: int
    active_providers: int
    active_users: int
    avg_latency_ms: float
    error_rate: float
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float


class UsageStats(BaseModel):
    """Schema for usage statistics."""
    period: str  # hourly, daily, weekly
    data: List[Dict[str, Any]]


class ModelStats(BaseModel):
    """Schema for per-model statistics."""
    model_id: UUID
    model_alias: str
    total_requests: int
    avg_latency_ms: float
    error_rate: float
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float


class UserStats(BaseModel):
    """Schema for per-user statistics."""
    user_id: UUID
    username: str
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float


class PaginatedResponse(BaseModel):
    """Generic paginated response."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
