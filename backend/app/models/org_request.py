"""Organization Join Request model for membership workflow."""
import uuid
from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JoinRequestStatus(str, enum.Enum):
    """Status of organization join request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class OrgJoinRequest(Base):
    """Organization join request for membership workflow."""
    
    __tablename__ = "org_join_requests"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # Requester
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    
    # Target organization
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    
    # Request details
    request_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[JoinRequestStatus] = mapped_column(
        SQLEnum(JoinRequestStatus), default=JoinRequestStatus.PENDING
    )
    
    # Review details
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    response_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], backref="org_join_requests")
    organization: Mapped["Organization"] = relationship("Organization", backref="join_requests")
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])


# Import for type hints
from app.models.user import User
from app.models.organization import Organization
