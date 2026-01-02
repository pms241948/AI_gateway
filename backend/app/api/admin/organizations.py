"""Organization and Group management API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_active_user, get_current_superuser
from app.database import get_db
from app.models.organization import Group, Organization, OrganizationMember
from app.models.user import User
from app.schemas.user import (
    GroupCreate,
    GroupResponse,
    OrganizationCreate,
    OrganizationResponse,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


async def is_org_admin(user: User, org_id: UUID, db: AsyncSession) -> bool:
    """Check if user is a superuser or an admin of the organization."""
    if user.is_superuser:
        return True
    
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user.id,
                OrganizationMember.is_admin == True
            )
        )
    )
    return result.scalar_one_or_none() is not None



# Organization endpoints
@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all organizations."""
    result = await db.execute(
        select(Organization).order_by(Organization.name)
    )
    return result.scalars().all()


@router.post("", response_model=OrganizationResponse)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization (admin only)."""
    # Check if name already exists
    result = await db.execute(
        select(Organization).where(Organization.name == org_data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Organization name already exists")
    
    org = Organization(
        name=org_data.name,
        description=org_data.description,
        is_active=True,
    )
    
    db.add(org)
    await db.commit()
    await db.refresh(org)
    
    return org


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get an organization by ID."""
    result = await db.execute(
        select(Organization)
        .where(Organization.id == org_id)
        .options(selectinload(Organization.groups))
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return org


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Update an organization (admin only)."""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    org.name = org_data.name
    org.description = org_data.description
    
    await db.commit()
    await db.refresh(org)
    
    return org


@router.delete("/{org_id}")
async def delete_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete an organization (admin only)."""
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    await db.delete(org)
    await db.commit()
    
    return {"message": "Organization deleted"}


# Group endpoints
@router.get("/{org_id}/groups", response_model=List[GroupResponse])
async def list_groups(
    org_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all groups in an organization."""
    result = await db.execute(
        select(Group)
        .where(Group.organization_id == org_id)
        .order_by(Group.name)
    )
    return result.scalars().all()


@router.post("/{org_id}/groups", response_model=GroupResponse)
async def create_group(
    org_id: UUID,
    group_data: GroupCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Create a new group in an organization (admin only)."""
    # Verify organization exists
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Check if group name already exists in org
    result = await db.execute(
        select(Group)
        .where(Group.organization_id == org_id)
        .where(Group.name == group_data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Group name already exists in organization")
    
    group = Group(
        organization_id=org_id,
        name=group_data.name,
        description=group_data.description,
        is_active=True,
    )
    
    db.add(group)
    await db.commit()
    await db.refresh(group)
    
    return group


@router.get("/{org_id}/groups/{group_id}", response_model=GroupResponse)
async def get_group(
    org_id: UUID,
    group_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a group by ID."""
    result = await db.execute(
        select(Group)
        .where(Group.id == group_id)
        .where(Group.organization_id == org_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return group


@router.put("/{org_id}/groups/{group_id}", response_model=GroupResponse)
async def update_group(
    org_id: UUID,
    group_id: UUID,
    group_data: GroupCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Update a group (admin only)."""
    result = await db.execute(
        select(Group)
        .where(Group.id == group_id)
        .where(Group.organization_id == org_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    group.name = group_data.name
    group.description = group_data.description
    
    await db.commit()
    await db.refresh(group)
    
    return group


@router.delete("/{org_id}/groups/{group_id}")
async def delete_group(
    org_id: UUID,
    group_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a group (admin only)."""
    result = await db.execute(
        select(Group)
        .where(Group.id == group_id)
        .where(Group.organization_id == org_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    await db.delete(group)
    await db.commit()
    
    return {"message": "Group deleted"}


# Organization member management
@router.get("/{org_id}/members")
async def list_organization_members(
    org_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all members of an organization with admin status."""
    # Verify organization exists
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get all users in this organization
    result = await db.execute(
        select(User)
        .where(User.organization_id == org_id)
        .order_by(User.username)
    )
    users = result.scalars().all()
    
    # Get org admin status for each user
    members = []
    for user in users:
        admin_result = await db.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.organization_id == org_id,
                    OrganizationMember.user_id == user.id
                )
            )
        )
        membership = admin_result.scalar_one_or_none()
        
        members.append({
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "group_id": str(user.group_id) if user.group_id else None,
            "is_org_admin": membership.is_admin if membership else False,
        })
    
    return members


@router.post("/{org_id}/members/{user_id}")
async def add_member_to_organization(
    org_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a user to an organization (superuser or org admin)."""
    # Check permission
    if not await is_org_admin(current_user, org_id, db):
        raise HTTPException(status_code=403, detail="Not authorized to manage this organization")
    
    # Verify organization exists
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get the user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user's organization
    user.organization_id = org_id
    user.group_id = None  # Clear group when changing organization
    
    # Create membership record if not exists
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id
            )
        )
    )
    if not result.scalar_one_or_none():
        membership = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            is_admin=False
        )
        db.add(membership)
    
    await db.commit()
    
    return {"message": f"User {user.username} added to organization"}


@router.delete("/{org_id}/members/{user_id}")
async def remove_member_from_organization(
    org_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a user from an organization (superuser or org admin)."""
    # Check permission
    if not await is_org_admin(current_user, org_id, db):
        raise HTTPException(status_code=403, detail="Not authorized to manage this organization")
    
    # Get the user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.organization_id != org_id:
        raise HTTPException(status_code=400, detail="User is not a member of this organization")
    
    # Remove user from organization
    user.organization_id = None
    user.group_id = None
    
    # Remove membership record
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id
            )
        )
    )
    membership = result.scalar_one_or_none()
    if membership:
        await db.delete(membership)
    
    await db.commit()
    
    return {"message": f"User {user.username} removed from organization"}


@router.put("/{org_id}/members/{user_id}/admin")
async def set_member_admin_status(
    org_id: UUID,
    user_id: UUID,
    is_admin: bool = False,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Set or remove org admin status for a user (superuser only)."""
    # Verify user is a member
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.organization_id != org_id:
        raise HTTPException(status_code=400, detail="User is not a member of this organization")
    
    # Get or create membership record
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id
            )
        )
    )
    membership = result.scalar_one_or_none()
    
    if membership:
        membership.is_admin = is_admin
    else:
        membership = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            is_admin=is_admin
        )
        db.add(membership)
    
    await db.commit()
    
    action = "granted admin rights" if is_admin else "removed admin rights"
    return {"message": f"User {user.username} {action}"}


@router.put("/{org_id}/members/{user_id}/group")
async def assign_member_to_group(
    org_id: UUID,
    user_id: UUID,
    group_id: UUID = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Assign a user to a group within the organization (superuser or org admin)."""
    # Check permission
    if not await is_org_admin(current_user, org_id, db):
        raise HTTPException(status_code=403, detail="Not authorized to manage this organization")
    
    # Get the user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.organization_id != org_id:
        raise HTTPException(status_code=400, detail="User is not a member of this organization")
    
    # Verify group exists if provided
    if group_id:
        result = await db.execute(
            select(Group)
            .where(Group.id == group_id)
            .where(Group.organization_id == org_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found in this organization")
    
    user.group_id = group_id
    await db.commit()
    
    return {"message": f"User {user.username} assigned to group"}


