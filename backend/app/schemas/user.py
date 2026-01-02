"""User-related Pydantic schemas."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8)
    organization_id: Optional[UUID] = None
    group_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    password: Optional[str] = Field(None, min_length=8)
    organization_id: Optional[UUID] = None
    group_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID
    organization_id: Optional[UUID] = None
    group_id: Optional[UUID] = None
    is_active: bool
    is_superuser: bool
    auth_provider: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str  # Can be username or email
    password: str


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    exp: int
    iat: int
    type: str  # access or refresh


class ApiKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    expires_in_days: Optional[int] = None


class ApiKeyResponse(BaseModel):
    """Schema for API key response (only shown once on creation)."""
    id: UUID
    name: str
    key: str  # Full key, only returned on creation
    key_prefix: str
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyListResponse(BaseModel):
    """Schema for listing API keys (key not shown)."""
    id: UUID
    name: str
    key_prefix: str
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Organization schemas
class OrganizationCreate(BaseModel):
    """Schema for creating an organization."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class OrganizationResponse(BaseModel):
    """Schema for organization response."""
    id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Group schemas
class GroupCreate(BaseModel):
    """Schema for creating a group."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class GroupResponse(BaseModel):
    """Schema for group response."""
    id: UUID
    organization_id: UUID
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Role schemas
class RoleCreate(BaseModel):
    """Schema for creating a role."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    scope: str = "global"


class RoleResponse(BaseModel):
    """Schema for role response."""
    id: UUID
    name: str
    description: Optional[str] = None
    scope: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserRoleAssign(BaseModel):
    """Schema for assigning a role to a user."""
    role_id: UUID
    scope_org_id: Optional[UUID] = None
    scope_group_id: Optional[UUID] = None
