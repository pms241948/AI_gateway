"""LLM Model and related database models."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.provider import Provider
    from app.models.organization import Organization, Group
    from app.models.logs import RequestLog, HealthCheckResult, SecurityScanResult


class LLMModel(Base):
    """LLM Model alias and metadata."""

    __tablename__ = "models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alias: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Model type: chat, embedding, rerank
    model_type: Mapped[str] = mapped_column(String(50), default="chat")
    
    # Capabilities: chat, embeddings, vision, function_calling
    capabilities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Approval workflow
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_status: Mapped[str] = mapped_column(String(50), default="approved")  # pending, approved, rejected
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    endpoints: Mapped[List["ModelEndpoint"]] = relationship(
        "ModelEndpoint", back_populates="model", cascade="all, delete-orphan"
    )
    policies: Mapped[List["ModelPolicy"]] = relationship(
        "ModelPolicy", back_populates="model", cascade="all, delete-orphan"
    )
    org_access: Mapped[List["OrgModelAccess"]] = relationship(
        "OrgModelAccess", back_populates="model", cascade="all, delete-orphan"
    )
    group_access: Mapped[List["GroupModelAccess"]] = relationship(
        "GroupModelAccess", back_populates="model", cascade="all, delete-orphan"
    )
    request_logs: Mapped[List["RequestLog"]] = relationship(
        "RequestLog", back_populates="model"
    )
    health_checks: Mapped[List["HealthCheckResult"]] = relationship(
        "HealthCheckResult", back_populates="model", cascade="all, delete-orphan"
    )
    security_scans: Mapped[List["SecurityScanResult"]] = relationship(
        "SecurityScanResult", back_populates="model", cascade="all, delete-orphan"
    )


class ModelEndpoint(Base):
    """Model to Provider endpoint mapping (supports multiple endpoints per model)."""

    __tablename__ = "model_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id")
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id")
    )
    
    # The actual model name at the provider (e.g., "llama3:8b" for Ollama)
    provider_model_name: Mapped[str] = mapped_column(String(255))
    
    # Load balancing configuration
    priority: Mapped[int] = mapped_column(Integer, default=1)  # Higher = preferred
    weight: Mapped[int] = mapped_column(Integer, default=100)  # For weighted routing
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    model: Mapped["LLMModel"] = relationship("LLMModel", back_populates="endpoints")
    provider: Mapped["Provider"] = relationship("Provider", back_populates="endpoints")
    health_checks: Mapped[List["HealthCheckResult"]] = relationship(
        "HealthCheckResult", back_populates="endpoint", cascade="all, delete-orphan"
    )


class ModelPolicy(Base):
    """Policy configuration for a model."""

    __tablename__ = "model_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id")
    )
    
    # Token limits
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Rate limiting
    rate_limit_rpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Requests per minute
    rate_limit_tpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Tokens per minute
    max_concurrent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Cost tracking
    cost_per_1k_input: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    cost_per_1k_output: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    
    # Access control (JSON arrays of UUIDs)
    allowed_orgs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    allowed_groups: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    allowed_users: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    model: Mapped["LLMModel"] = relationship("LLMModel", back_populates="policies")


class OrgModelAccess(Base):
    """Organization-level model access control."""

    __tablename__ = "org_model_access"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id"), primary_key=True
    )
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="model_access"
    )
    model: Mapped["LLMModel"] = relationship("LLMModel", back_populates="org_access")


class GroupModelAccess(Base):
    """Group-level model access control."""

    __tablename__ = "group_model_access"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), primary_key=True
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id"), primary_key=True
    )
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="model_access")
    model: Mapped["LLMModel"] = relationship("LLMModel", back_populates="group_access")


class UserModelAccess(Base):
    """User-level model access control."""

    __tablename__ = "user_model_access"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id", ondelete="CASCADE"), primary_key=True
    )
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # Admin who granted access


class ApiKeyModelAccess(Base):
    """API Key specific model access - limits which models an API key can access."""

    __tablename__ = "api_key_model_access"

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), primary_key=True
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("models.id", ondelete="CASCADE"), primary_key=True
    )
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

