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


@router.get("/available")
async def list_available_organizations(
    db: AsyncSession = Depends(get_db),
):
    """List all active organizations available for joining (public endpoint)."""
    result = await db.execute(
        select(Organization)
        .where(Organization.is_active == True)
        .order_by(Organization.name)
    )
    orgs = result.scalars().all()
    
    return [
        {
            "id": str(org.id),
            "name": org.name,
            "description": org.description,
        }
        for org in orgs
    ]


@router.get("/my-join-requests")
async def list_my_join_requests(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List my organization join requests."""
    from app.models.org_request import OrgJoinRequest
    result = await db.execute(
        select(OrgJoinRequest, Organization).join(
            Organization, OrgJoinRequest.organization_id == Organization.id
        ).where(
            OrgJoinRequest.user_id == current_user.id
        ).order_by(OrgJoinRequest.created_at.desc())
    )
    requests = result.all()
    
    return [
        {
            "id": str(req.id),
            "organization_id": str(org.id),
            "organization_name": org.name,
            "request_reason": req.request_reason,
            "status": req.status.value,
            "response_note": req.response_note,
            "created_at": req.created_at.isoformat(),
            "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        }
        for req, org in requests
    ]


@router.get("/managed-join-requests")
async def list_managed_join_requests(
    status: str = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List join requests from all organizations where current user is admin."""
    from app.models.org_request import OrgJoinRequest, JoinRequestStatus
    
    # Get all organizations where user is admin
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.is_admin == True
            )
        )
    )
    admin_memberships = result.scalars().all()
    admin_org_ids = [m.organization_id for m in admin_memberships]
    
    # Also include if user is superuser (they can manage all)
    if current_user.is_superuser:
        result = await db.execute(select(Organization.id))
        admin_org_ids = [row[0] for row in result.all()]
    
    if not admin_org_ids:
        return []
    
    # Get join requests for these organizations
    from sqlalchemy import or_
    query = select(OrgJoinRequest, User, Organization).join(
        User, OrgJoinRequest.user_id == User.id
    ).join(
        Organization, OrgJoinRequest.organization_id == Organization.id
    ).where(
        OrgJoinRequest.organization_id.in_(admin_org_ids)
    )
    
    if status:
        query = query.where(OrgJoinRequest.status == JoinRequestStatus(status))
    
    query = query.order_by(OrgJoinRequest.created_at.desc())
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "id": str(req.id),
            "organization_id": str(org.id),
            "organization_name": org.name,
            "user_id": str(user.id),
            "user_email": user.email,
            "user_username": user.username,
            "request_reason": req.request_reason,
            "status": req.status.value,
            "response_note": req.response_note,
            "created_at": req.created_at.isoformat(),
            "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        }
        for req, user, org in rows
    ]


@router.post("/skip-organization")
async def skip_organization_selection(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark user as having skipped organization selection (independent user)."""
    return {"message": "You've chosen to continue as an independent user", "organization_id": None}


@router.put("/set-default/{org_id}")
async def set_default_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Set an organization as the user's default organization."""
    # Check if user is a member of this organization
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == current_user.id
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You are not a member of this organization")
    
    # Get organization name for response
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Update user's default organization
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    user.organization_id = org_id
    
    await db.commit()
    
    return {"message": f"'{org.name}' 이(가) 기본 조직으로 설정되었습니다.", "organization_id": str(org_id)}


@router.get("/user-status")
async def get_user_organization_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's organization status including all memberships."""
    from app.models.org_request import OrgJoinRequest, JoinRequestStatus
    
    # Get all organization memberships for this user
    result = await db.execute(
        select(OrganizationMember, Organization)
        .join(Organization, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == current_user.id)
        .order_by(Organization.name)
    )
    membership_rows = result.all()
    
    memberships = [
        {
            "organization_id": str(org.id),
            "organization_name": org.name,
            "is_admin": membership.is_admin,
            "role": "관리자" if membership.is_admin else "멤버",
        }
        for membership, org in membership_rows
    ]
    
    # Check for pending join requests
    result = await db.execute(
        select(OrgJoinRequest, Organization).join(
            Organization, OrgJoinRequest.organization_id == Organization.id
        ).where(
            and_(
                OrgJoinRequest.user_id == current_user.id,
                OrgJoinRequest.status == JoinRequestStatus.PENDING
            )
        )
    )
    pending_requests = [
        {
            "organization_id": str(org.id),
            "organization_name": org.name,
        }
        for req, org in result.all()
    ]
    
    # Default organization info (for backwards compatibility)
    default_org_name = None
    is_default_org_admin = False
    if current_user.organization_id:
        result = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        org = result.scalar_one_or_none()
        if org:
            default_org_name = org.name
            is_default_org_admin = await is_org_admin(current_user, current_user.organization_id, db)
    
    return {
        "has_organization": len(memberships) > 0,
        "organization_id": str(current_user.organization_id) if current_user.organization_id else None,
        "organization_name": default_org_name,
        "is_org_admin": is_default_org_admin,
        "memberships": memberships,  # All organization memberships
        "pending_requests": pending_requests,  # All pending join requests
        "has_pending_request": len(pending_requests) > 0,
        "pending_org_name": pending_requests[0]["organization_name"] if pending_requests else None,
    }



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
    
    # Get all members via OrganizationMember (supports multi-org membership)
    result = await db.execute(
        select(User, OrganizationMember)
        .join(OrganizationMember, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(User.username)
    )
    rows = result.all()
    
    members = []
    for user, membership in rows:
        members.append({
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "group_id": str(user.group_id) if user.group_id else None,
            "is_org_admin": membership.is_admin,
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
    
    # Check membership exists
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id
            )
        )
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=400, detail="User is not a member of this organization")
    
    # Get the user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Clear default org only if this org was the default
    if user.organization_id == org_id:
        user.organization_id = None
        user.group_id = None
    
    # Remove membership record
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
    # Get membership record (check if user is member of this org)
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id
            )
        )
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(status_code=400, detail="User is not a member of this organization")
    
    # Get user for response message
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update admin status
    membership.is_admin = is_admin
    
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


# ============================================================================
# Organization Join Request Workflow
# ============================================================================

from datetime import datetime
from pydantic import BaseModel
from app.models.org_request import OrgJoinRequest, JoinRequestStatus


class JoinRequestCreate(BaseModel):
    request_reason: str = None


class JoinReviewRequest(BaseModel):
    response_note: str = None




@router.post("/{org_id}/join")
async def request_to_join_organization(
    org_id: UUID,
    request_data: JoinRequestCreate = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Request to join an organization."""
    # Check if organization exists
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    if not org.is_active:
        raise HTTPException(status_code=400, detail="Organization is not active")
    
    # Check if user is already a member of THIS organization
    result = await db.execute(
        select(OrganizationMember).where(
            and_(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == current_user.id
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You are already a member of this organization")
    
    # Check if already has pending request for this org
    result = await db.execute(
        select(OrgJoinRequest).where(
            and_(
                OrgJoinRequest.user_id == current_user.id,
                OrgJoinRequest.organization_id == org_id,
                OrgJoinRequest.status == JoinRequestStatus.PENDING
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already have a pending request for this organization")
    
    # Create join request
    join_request = OrgJoinRequest(
        user_id=current_user.id,
        organization_id=org_id,
        request_reason=request_data.request_reason if request_data else None,
        status=JoinRequestStatus.PENDING,
    )
    db.add(join_request)
    await db.commit()
    await db.refresh(join_request)
    
    return {
        "id": str(join_request.id),
        "message": f"Join request for '{org.name}' submitted",
        "status": "pending",
    }


@router.get("/{org_id}/join-requests")
async def list_organization_join_requests(
    org_id: UUID,
    status: str = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List join requests for an organization (org admin only)."""
    # Check permission
    if not await is_org_admin(current_user, org_id, db):
        raise HTTPException(status_code=403, detail="Not authorized to view join requests")
    
    query = select(OrgJoinRequest, User).join(
        User, OrgJoinRequest.user_id == User.id
    ).where(OrgJoinRequest.organization_id == org_id)
    
    if status:
        query = query.where(OrgJoinRequest.status == JoinRequestStatus(status))
    
    query = query.order_by(OrgJoinRequest.created_at.desc())
    
    result = await db.execute(query)
    requests = result.all()
    
    return [
        {
            "id": str(req.id),
            "user_id": str(user.id),
            "user_email": user.email,
            "user_username": user.username,
            "request_reason": req.request_reason,
            "status": req.status.value,
            "response_note": req.response_note,
            "created_at": req.created_at.isoformat(),
            "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        }
        for req, user in requests
    ]


@router.put("/join-requests/{request_id}/approve")
async def approve_join_request(
    request_id: UUID,
    review: JoinReviewRequest = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a join request (org admin only)."""
    # Get the request
    result = await db.execute(
        select(OrgJoinRequest).where(OrgJoinRequest.id == request_id)
    )
    join_request = result.scalar_one_or_none()
    
    if not join_request:
        raise HTTPException(status_code=404, detail="Join request not found")
    
    # Check permission
    if not await is_org_admin(current_user, join_request.organization_id, db):
        raise HTTPException(status_code=403, detail="Not authorized to approve join requests")
    
    if join_request.status != JoinRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")
    
    # Update request status
    join_request.status = JoinRequestStatus.APPROVED
    join_request.reviewed_by = current_user.id
    join_request.reviewed_at = datetime.utcnow()
    if review and review.response_note:
        join_request.response_note = review.response_note
    
    # Add user to organization
    result = await db.execute(select(User).where(User.id == join_request.user_id))
    user = result.scalar_one_or_none()
    
    if user:
        # Set as default organization only if user has no org yet (first membership)
        if not user.organization_id:
            user.organization_id = join_request.organization_id
        
        # Create membership record
        result = await db.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.organization_id == join_request.organization_id,
                    OrganizationMember.user_id == user.id
                )
            )
        )
        if not result.scalar_one_or_none():
            membership = OrganizationMember(
                organization_id=join_request.organization_id,
                user_id=user.id,
                is_admin=False
            )
            db.add(membership)
    
    await db.commit()
    
    return {"message": "Join request approved", "status": "approved"}


@router.put("/join-requests/{request_id}/reject")
async def reject_join_request(
    request_id: UUID,
    review: JoinReviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a join request (org admin only)."""
    # Get the request
    result = await db.execute(
        select(OrgJoinRequest).where(OrgJoinRequest.id == request_id)
    )
    join_request = result.scalar_one_or_none()
    
    if not join_request:
        raise HTTPException(status_code=404, detail="Join request not found")
    
    # Check permission
    if not await is_org_admin(current_user, join_request.organization_id, db):
        raise HTTPException(status_code=403, detail="Not authorized to reject join requests")
    
    if join_request.status != JoinRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")
    
    # Update request status
    join_request.status = JoinRequestStatus.REJECTED
    join_request.reviewed_by = current_user.id
    join_request.reviewed_at = datetime.utcnow()
    if review and review.response_note:
        join_request.response_note = review.response_note
    
    await db.commit()
    
    return {"message": "Join request rejected", "status": "rejected"}


