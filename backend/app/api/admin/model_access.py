"""Model Access management API endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user, get_current_superuser
from app.database import get_db
from app.models.user import User, ApiKey
from app.models.llm_model import LLMModel, UserModelAccess, ApiKeyModelAccess, OrgModelAccess
from app.models.organization import Organization

router = APIRouter(prefix="/model-access", tags=["Model Access"])


class ModelAccessResponse(BaseModel):
    model_id: str
    model_alias: str
    model_display_name: str
    is_allowed: bool


class ModelAccessGrant(BaseModel):
    model_id: UUID
    is_allowed: bool = True


# Get available models for a user (what they're allowed to use)
@router.get("/users/{user_id}/models")
async def get_user_available_models(
    user_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Get all models a user has access to (admin only)."""
    # Get user's org and group
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get granted models for this user
    result = await db.execute(
        select(UserModelAccess, LLMModel)
        .join(LLMModel, UserModelAccess.model_id == LLMModel.id)
        .where(UserModelAccess.user_id == user_id)
        .where(UserModelAccess.is_allowed == True)
    )
    user_models = result.all()
    
    # Get org-level model access
    org_models = []
    if user.organization_id:
        result = await db.execute(
            select(OrgModelAccess, LLMModel)
            .join(LLMModel, OrgModelAccess.model_id == LLMModel.id)
            .where(OrgModelAccess.organization_id == user.organization_id)
            .where(OrgModelAccess.is_allowed == True)
        )
        org_models = result.all()
    
    # Combine and deduplicate
    models = {}
    for access, model in org_models:
        if model.is_active:
            models[str(model.id)] = {
                "model_id": str(model.id),
                "model_alias": model.alias,
                "model_display_name": model.display_name,
                "source": "organization",
            }
    
    for access, model in user_models:
        if model.is_active:
            models[str(model.id)] = {
                "model_id": str(model.id),
                "model_alias": model.alias,
                "model_display_name": model.display_name,
                "source": "user",
            }
    
    return list(models.values())


# Grant model access to a user
@router.post("/users/{user_id}/models")
async def grant_user_model_access(
    user_id: UUID,
    grant: ModelAccessGrant,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Grant model access to a user (admin only)."""
    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify model exists
    result = await db.execute(select(LLMModel).where(LLMModel.id == grant.model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check if access already exists
    result = await db.execute(
        select(UserModelAccess).where(
            and_(
                UserModelAccess.user_id == user_id,
                UserModelAccess.model_id == grant.model_id
            )
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.is_allowed = grant.is_allowed
    else:
        access = UserModelAccess(
            user_id=user_id,
            model_id=grant.model_id,
            is_allowed=grant.is_allowed,
            created_by=current_user.id
        )
        db.add(access)
    
    await db.commit()
    
    return {"message": f"Model {model.alias} access granted to user"}


# Revoke model access from a user
@router.delete("/users/{user_id}/models/{model_id}")
async def revoke_user_model_access(
    user_id: UUID,
    model_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Revoke model access from a user (admin only)."""
    result = await db.execute(
        delete(UserModelAccess).where(
            and_(
                UserModelAccess.user_id == user_id,
                UserModelAccess.model_id == model_id
            )
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Access not found")
    
    await db.commit()
    
    return {"message": "Model access revoked"}


# Grant model access to an organization
@router.post("/organizations/{org_id}/models")
async def grant_org_model_access(
    org_id: UUID,
    grant: ModelAccessGrant,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Grant model access to an organization (admin only)."""
    # Verify org exists
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Verify model exists
    result = await db.execute(select(LLMModel).where(LLMModel.id == grant.model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check if access already exists
    result = await db.execute(
        select(OrgModelAccess).where(
            and_(
                OrgModelAccess.organization_id == org_id,
                OrgModelAccess.model_id == grant.model_id
            )
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.is_allowed = grant.is_allowed
    else:
        access = OrgModelAccess(
            organization_id=org_id,
            model_id=grant.model_id,
            is_allowed=grant.is_allowed
        )
        db.add(access)
    
    await db.commit()
    
    return {"message": f"Model {model.alias} access granted to organization"}


# Revoke model access from an organization
@router.delete("/organizations/{org_id}/models/{model_id}")
async def revoke_org_model_access(
    org_id: UUID,
    model_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Revoke model access from an organization (admin only)."""
    result = await db.execute(
        delete(OrgModelAccess).where(
            and_(
                OrgModelAccess.organization_id == org_id,
                OrgModelAccess.model_id == model_id
            )
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Access not found")
    
    await db.commit()
    
    return {"message": "Model access revoked from organization"}



# Get organization's available models
@router.get("/organizations/{org_id}/models")
async def get_org_available_models(
    org_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all models an organization has access to."""
    result = await db.execute(
        select(OrgModelAccess, LLMModel)
        .join(LLMModel, OrgModelAccess.model_id == LLMModel.id)
        .where(OrgModelAccess.organization_id == org_id)
        .where(OrgModelAccess.is_allowed == True)
        .where(LLMModel.is_active == True)
    )
    models = result.all()
    
    return [
        {
            "model_id": str(model.id),
            "model_alias": model.alias,
            "model_display_name": model.display_name,
        }
        for access, model in models
    ]


# Get my available models (for end users)
@router.get("/me/models")
async def get_my_available_models(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all models the current user has access to.
    
    Users only see model alias and display name - not actual LLM details.
    """
    models = {}
    
    # 1. Get user's personal model access
    result = await db.execute(
        select(UserModelAccess, LLMModel)
        .join(LLMModel, UserModelAccess.model_id == LLMModel.id)
        .where(UserModelAccess.user_id == current_user.id)
        .where(UserModelAccess.is_allowed == True)
        .where(LLMModel.is_active == True)
    )
    for access, model in result.all():
        models[str(model.id)] = {
            "model": model.alias,
            "display_name": model.display_name,
            "type": model.model_type,
        }
    
    # 2. Get organization-level access
    if current_user.organization_id:
        result = await db.execute(
            select(OrgModelAccess, LLMModel)
            .join(LLMModel, OrgModelAccess.model_id == LLMModel.id)
            .where(OrgModelAccess.organization_id == current_user.organization_id)
            .where(OrgModelAccess.is_allowed == True)
            .where(LLMModel.is_active == True)
        )
        for access, model in result.all():
            if str(model.id) not in models:
                models[str(model.id)] = {
                    "model": model.alias,
                    "display_name": model.display_name,
                    "type": model.model_type,
                }
    
    return list(models.values())


# ============================================================================
# Model Access Request Approval Workflow
# ============================================================================

from datetime import datetime
from app.models.model_request import ModelAccessRequest, RequestStatus


class AccessRequestCreate(BaseModel):
    model_id: UUID
    request_reason: str = None


class AccessRequestResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    model_id: str
    model_alias: str
    request_reason: str = None
    status: str
    response_note: str = None
    created_at: datetime
    reviewed_at: datetime = None


@router.post("/requests")
async def create_access_request(
    request_data: AccessRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a model access request."""
    # Check if model exists
    result = await db.execute(select(LLMModel).where(LLMModel.id == request_data.model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check if already has pending request
    result = await db.execute(
        select(ModelAccessRequest).where(
            and_(
                ModelAccessRequest.user_id == current_user.id,
                ModelAccessRequest.model_id == request_data.model_id,
                ModelAccessRequest.status == RequestStatus.PENDING
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Pending request already exists")
    
    # Create request
    access_request = ModelAccessRequest(
        user_id=current_user.id,
        model_id=request_data.model_id,
        request_reason=request_data.request_reason,
        status=RequestStatus.PENDING,
    )
    db.add(access_request)
    await db.commit()
    await db.refresh(access_request)
    
    return {
        "id": str(access_request.id),
        "message": f"Access request for model '{model.alias}' submitted",
        "status": "pending",
    }


@router.get("/requests")
async def list_access_requests(
    status: str = None,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List all access requests (admin only)."""
    query = select(ModelAccessRequest, User, LLMModel).join(
        User, ModelAccessRequest.user_id == User.id
    ).join(
        LLMModel, ModelAccessRequest.model_id == LLMModel.id
    )
    
    if status:
        query = query.where(ModelAccessRequest.status == RequestStatus(status))
    
    query = query.order_by(ModelAccessRequest.created_at.desc())
    
    result = await db.execute(query)
    requests = result.all()
    
    return [
        {
            "id": str(req.id),
            "user_id": str(user.id),
            "user_email": user.email,
            "model_id": str(model.id),
            "model_alias": model.alias,
            "request_reason": req.request_reason,
            "status": req.status.value,
            "response_note": req.response_note,
            "created_at": req.created_at.isoformat(),
            "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        }
        for req, user, model in requests
    ]


@router.get("/my-requests")
async def list_my_requests(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List my access requests."""
    result = await db.execute(
        select(ModelAccessRequest, LLMModel).join(
            LLMModel, ModelAccessRequest.model_id == LLMModel.id
        ).where(
            ModelAccessRequest.user_id == current_user.id
        ).order_by(ModelAccessRequest.created_at.desc())
    )
    requests = result.all()
    
    return [
        {
            "id": str(req.id),
            "model_alias": model.alias,
            "model_display_name": model.display_name,
            "request_reason": req.request_reason,
            "status": req.status.value,
            "response_note": req.response_note,
            "created_at": req.created_at.isoformat(),
            "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        }
        for req, model in requests
    ]


class ReviewRequest(BaseModel):
    response_note: str = None


@router.put("/requests/{request_id}/approve")
async def approve_access_request(
    request_id: UUID,
    review: ReviewRequest = None,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Approve an access request (admin only)."""
    result = await db.execute(
        select(ModelAccessRequest).where(ModelAccessRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.status != RequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")
    
    # Update request status
    request.status = RequestStatus.APPROVED
    request.reviewed_by = current_user.id
    request.reviewed_at = datetime.utcnow()
    if review and review.response_note:
        request.response_note = review.response_note
    
    # Grant access
    result = await db.execute(
        select(UserModelAccess).where(
            and_(
                UserModelAccess.user_id == request.user_id,
                UserModelAccess.model_id == request.model_id
            )
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.is_allowed = True
    else:
        access = UserModelAccess(
            user_id=request.user_id,
            model_id=request.model_id,
            is_allowed=True,
            created_by=current_user.id,
        )
        db.add(access)
    
    await db.commit()
    
    return {"message": "Request approved", "status": "approved"}


@router.put("/requests/{request_id}/reject")
async def reject_access_request(
    request_id: UUID,
    review: ReviewRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Reject an access request (admin only)."""
    result = await db.execute(
        select(ModelAccessRequest).where(ModelAccessRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.status != RequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")
    
    # Update request status
    request.status = RequestStatus.REJECTED
    request.reviewed_by = current_user.id
    request.reviewed_at = datetime.utcnow()
    if review and review.response_note:
        request.response_note = review.response_note
    
    await db.commit()
    
    return {"message": "Request rejected", "status": "rejected"}


@router.get("/requests/pending/count")
async def get_pending_requests_count(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Get count of pending requests (admin only)."""
    from sqlalchemy import func
    
    result = await db.execute(
        select(func.count(ModelAccessRequest.id)).where(
            ModelAccessRequest.status == RequestStatus.PENDING
        )
    )
    count = result.scalar()
    
    return {"pending_count": count}
