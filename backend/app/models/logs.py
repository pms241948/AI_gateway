"""Logging-related database models."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.llm_model import LLMModel, ModelEndpoint
    from app.models.provider import Provider


class RequestLog(Base):
    """Request/Response log for all API calls."""

    __tablename__ = "request_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    model_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id"), nullable=True
    )
    provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id"), nullable=True
    )
    
    request_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    
    # Request info
    endpoint: Mapped[str] = mapped_column(String(255))  # /v1/chat/completions, etc.
    method: Mapped[str] = mapped_column(String(10))  # POST, GET
    
    # Response info
    status_code: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    
    # Token usage
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    
    # Metadata
    request_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Full request/response bodies (optional, based on policy)
    request_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_masked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="request_logs")
    model: Mapped[Optional["LLMModel"]] = relationship(
        "LLMModel", back_populates="request_logs"
    )


class AuditLog(Base):
    """Audit log for administrative actions."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    
    action: Mapped[str] = mapped_column(String(100), index=True)  # create, update, delete, login
    resource_type: Mapped[str] = mapped_column(String(100), index=True)  # user, model, provider
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    old_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


class HealthCheckResult(Base):
    """Health check results for model endpoints."""

    __tablename__ = "health_check_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id")
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_endpoints.id")
    )
    
    is_healthy: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    checked_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Relationships
    model: Mapped["LLMModel"] = relationship("LLMModel", back_populates="health_checks")
    endpoint: Mapped["ModelEndpoint"] = relationship(
        "ModelEndpoint", back_populates="health_checks"
    )


class SecurityScanResult(Base):
    """Security scan results for models."""

    __tablename__ = "security_scan_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id")
    )
    
    scanner_type: Mapped[str] = mapped_column(String(50))  # promptfoo, garak, ps-fuzz
    scan_status: Mapped[str] = mapped_column(String(50))  # pending, running, completed, failed
    
    results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # approve, hold, reject
    
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    model: Mapped["LLMModel"] = relationship("LLMModel", back_populates="security_scans")
