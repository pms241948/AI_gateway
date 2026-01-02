"""Masking policy database models."""
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaskingPolicy(Base):
    """PII masking policy configuration."""

    __tablename__ = "masking_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    
    apply_to_request: Mapped[bool] = mapped_column(Boolean, default=False)
    apply_to_response: Mapped[bool] = mapped_column(Boolean, default=False)
    apply_to_logs: Mapped[bool] = mapped_column(Boolean, default=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    entities: Mapped[List["MaskingEntity"]] = relationship(
        "MaskingEntity", back_populates="policy", cascade="all, delete-orphan"
    )


class MaskingEntity(Base):
    """Entity types to detect and mask."""

    __tablename__ = "masking_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("masking_policies.id")
    )
    
    # Entity type: PHONE_NUMBER, EMAIL_ADDRESS, PERSON, etc.
    entity_type: Mapped[str] = mapped_column(String(100))
    
    # Action: mask, redact, hash
    action: Mapped[str] = mapped_column(String(50), default="mask")
    
    # Replacement pattern (e.g., "[MASKED]", "***", etc.)
    replacement_pattern: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    policy: Mapped["MaskingPolicy"] = relationship(
        "MaskingPolicy", back_populates="entities"
    )
