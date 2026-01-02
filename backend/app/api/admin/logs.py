"""Log management API endpoints."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user, get_current_superuser
from app.database import get_db
from app.models.logs import AuditLog, RequestLog
from app.models.user import User
from app.schemas.logs import AuditLogResponse, PaginatedResponse, RequestLogResponse

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("/requests", response_model=PaginatedResponse)
async def list_request_logs(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    user_id: Optional[UUID] = None,
    model_id: Optional[UUID] = None,
    status_code: Optional[int] = None,
    endpoint: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List request logs with filtering."""
    # Build query
    query = select(RequestLog)
    count_query = select(func.count(RequestLog.id))
    
    # Apply filters
    conditions = []
    
    # Non-admins can only see their own logs
    if not current_user.is_superuser:
        conditions.append(RequestLog.user_id == current_user.id)
    elif user_id:
        conditions.append(RequestLog.user_id == user_id)
    
    if start_date:
        conditions.append(RequestLog.created_at >= start_date)
    if end_date:
        conditions.append(RequestLog.created_at <= end_date)
    if model_id:
        conditions.append(RequestLog.model_id == model_id)
    if status_code:
        conditions.append(RequestLog.status_code == status_code)
    if endpoint:
        conditions.append(RequestLog.endpoint.ilike(f"%{endpoint}%"))
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.order_by(RequestLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return PaginatedResponse(
        items=[RequestLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/requests/{log_id}", response_model=RequestLogResponse)
async def get_request_log(
    log_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific request log."""
    query = select(RequestLog).where(RequestLog.id == log_id)
    
    # Non-admins can only view their own logs
    if not current_user.is_superuser:
        query = query.where(RequestLog.user_id == current_user.id)
    
    result = await db.execute(query)
    log = result.scalar_one_or_none()
    
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Log not found")
    
    return log


@router.get("/audit", response_model=PaginatedResponse)
async def list_audit_logs(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    user_id: Optional[UUID] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs (admin only)."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))
    
    conditions = []
    
    if start_date:
        conditions.append(AuditLog.created_at >= start_date)
    if end_date:
        conditions.append(AuditLog.created_at <= end_date)
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/export")
async def export_logs(
    log_type: str = Query("requests", regex="^(requests|audit)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Export logs as CSV (admin only)."""
    import csv
    import io
    
    # Build query based on log type
    if log_type == "requests":
        query = select(RequestLog)
        if start_date:
            query = query.where(RequestLog.created_at >= start_date)
        if end_date:
            query = query.where(RequestLog.created_at <= end_date)
        query = query.order_by(RequestLog.created_at.desc())
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "request_id", "created_at", "user_id", "model_id",
            "endpoint", "method", "status_code", "latency_ms",
            "input_tokens", "output_tokens", "cost"
        ])
        
        for log in logs:
            writer.writerow([
                log.request_id,
                log.created_at.isoformat() if log.created_at else "",
                str(log.user_id) if log.user_id else "",
                str(log.model_id) if log.model_id else "",
                log.endpoint,
                log.method,
                log.status_code,
                log.latency_ms,
                log.input_tokens or "",
                log.output_tokens or "",
                str(log.cost) if log.cost else "",
            ])
        
        filename = f"request_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
    else:  # audit
        query = select(AuditLog)
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)
        query = query.order_by(AuditLog.created_at.desc())
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "created_at", "user_id", "action", "resource_type",
            "resource_id", "ip_address"
        ])
        
        for log in logs:
            writer.writerow([
                log.created_at.isoformat() if log.created_at else "",
                str(log.user_id) if log.user_id else "",
                log.action,
                log.resource_type,
                str(log.resource_id) if log.resource_id else "",
                log.ip_address or "",
            ])
        
        filename = f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
