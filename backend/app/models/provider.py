"""LLM Provider database model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.llm_model import ModelEndpoint


class Provider(Base):
    """LLM Provider connection configuration."""

    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    
    # Provider type: openai, anthropic, ollama, vllm, openai_compatible
    provider_type: Mapped[str] = mapped_column(String(50), index=True)
    
    # Connection
    base_url: Mapped[str] = mapped_column(String(500))
    
    # Authentication
    auth_type: Mapped[str] = mapped_column(String(50), default="none")  # none, api_key, bearer
    auth_credentials_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Request configuration
    default_headers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    endpoints: Mapped[List["ModelEndpoint"]] = relationship(
        "ModelEndpoint", back_populates="provider", cascade="all, delete-orphan"
    )
