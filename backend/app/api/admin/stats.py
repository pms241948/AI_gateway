"""Statistics and dashboard API endpoints."""
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.database import get_db
from app.models.llm_model import LLMModel
from app.models.logs import RequestLog
from app.models.provider import Provider
from app.models.user import User
from app.schemas.logs import DashboardStats, ModelStats, UsageStats, UserStats

router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics."""
    now = datetime.utcnow()
    
    # Time boundaries
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    
    # Request counts
    result = await db.execute(
        select(func.count(RequestLog.id))
        .where(RequestLog.created_at >= last_24h)
    )
    total_requests_24h = result.scalar() or 0
    
    result = await db.execute(
        select(func.count(RequestLog.id))
        .where(RequestLog.created_at >= last_7d)
    )
    total_requests_7d = result.scalar() or 0
    
    result = await db.execute(
        select(func.count(RequestLog.id))
        .where(RequestLog.created_at >= last_30d)
    )
    total_requests_30d = result.scalar() or 0
    
    # Active models
    result = await db.execute(
        select(func.count(LLMModel.id))
        .where(LLMModel.is_active == True)
        .where(LLMModel.approval_status == "approved")
    )
    active_models = result.scalar() or 0
    
    # Active providers
    result = await db.execute(
        select(func.count(Provider.id))
        .where(Provider.is_active == True)
    )
    active_providers = result.scalar() or 0
    
    # Active users (logged in within 30 days)
    result = await db.execute(
        select(func.count(func.distinct(RequestLog.user_id)))
        .where(RequestLog.created_at >= last_30d)
    )
    active_users = result.scalar() or 0
    
    # Average latency (last 24h)
    result = await db.execute(
        select(func.avg(RequestLog.latency_ms))
        .where(RequestLog.created_at >= last_24h)
    )
    avg_latency = result.scalar() or 0
    
    # Error rate (last 24h)
    result = await db.execute(
        select(func.count(RequestLog.id))
        .where(RequestLog.created_at >= last_24h)
        .where(RequestLog.status_code >= 400)
    )
    error_count = result.scalar() or 0
    error_rate = (error_count / total_requests_24h * 100) if total_requests_24h > 0 else 0
    
    # Token usage (last 30d)
    result = await db.execute(
        select(
            func.coalesce(func.sum(RequestLog.input_tokens), 0),
            func.coalesce(func.sum(RequestLog.output_tokens), 0),
            func.coalesce(func.sum(RequestLog.cost), 0),
        )
        .where(RequestLog.created_at >= last_30d)
    )
    row = result.one()
    total_input_tokens = int(row[0] or 0)
    total_output_tokens = int(row[1] or 0)
    total_cost = float(row[2] or 0)
    
    return DashboardStats(
        total_requests_24h=total_requests_24h,
        total_requests_7d=total_requests_7d,
        total_requests_30d=total_requests_30d,
        active_models=active_models,
        active_providers=active_providers,
        active_users=active_users,
        avg_latency_ms=float(avg_latency),
        error_rate=error_rate,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cost=total_cost,
    )


@router.get("/usage", response_model=UsageStats)
async def get_usage_stats(
    period: str = Query("daily", regex="^(hourly|daily|weekly)$"),
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get usage statistics over time."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    # Determine grouping based on period
    if period == "hourly":
        # Group by hour
        time_trunc = func.date_trunc("hour", RequestLog.created_at)
    elif period == "weekly":
        time_trunc = func.date_trunc("week", RequestLog.created_at)
    else:
        time_trunc = func.date_trunc("day", RequestLog.created_at)
    
    result = await db.execute(
        select(
            time_trunc.label("period"),
            func.count(RequestLog.id).label("requests"),
            func.avg(RequestLog.latency_ms).label("avg_latency"),
            func.sum(RequestLog.input_tokens).label("input_tokens"),
            func.sum(RequestLog.output_tokens).label("output_tokens"),
        )
        .where(RequestLog.created_at >= start_date)
        .group_by(time_trunc)
        .order_by(time_trunc)
    )
    
    data = []
    for row in result.all():
        data.append({
            "period": row.period.isoformat() if row.period else None,
            "requests": row.requests or 0,
            "avg_latency_ms": float(row.avg_latency or 0),
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
        })
    
    return UsageStats(period=period, data=data)


@router.get("/models", response_model=List[ModelStats])
async def get_model_stats(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get per-model statistics."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(
            RequestLog.model_id,
            LLMModel.alias,
            func.count(RequestLog.id).label("total_requests"),
            func.avg(RequestLog.latency_ms).label("avg_latency"),
            func.sum(
                func.case((RequestLog.status_code >= 400, 1), else_=0)
            ).label("error_count"),
            func.sum(RequestLog.input_tokens).label("input_tokens"),
            func.sum(RequestLog.output_tokens).label("output_tokens"),
            func.sum(RequestLog.cost).label("total_cost"),
        )
        .join(LLMModel, RequestLog.model_id == LLMModel.id, isouter=True)
        .where(RequestLog.created_at >= start_date)
        .where(RequestLog.model_id.isnot(None))
        .group_by(RequestLog.model_id, LLMModel.alias)
        .order_by(func.count(RequestLog.id).desc())
    )
    
    stats = []
    for row in result.all():
        total_requests = row.total_requests or 0
        error_count = row.error_count or 0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
        
        stats.append(ModelStats(
            model_id=row.model_id,
            model_alias=row.alias or "Unknown",
            total_requests=total_requests,
            avg_latency_ms=float(row.avg_latency or 0),
            error_rate=error_rate,
            total_input_tokens=int(row.input_tokens or 0),
            total_output_tokens=int(row.output_tokens or 0),
            total_cost=float(row.total_cost or 0),
        ))
    
    return stats


@router.get("/users", response_model=List[UserStats])
async def get_user_stats(
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get per-user statistics."""
    # Only admins can see all users, others see only themselves
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = select(
        RequestLog.user_id,
        User.username,
        func.count(RequestLog.id).label("total_requests"),
        func.sum(RequestLog.input_tokens).label("input_tokens"),
        func.sum(RequestLog.output_tokens).label("output_tokens"),
        func.sum(RequestLog.cost).label("total_cost"),
    ).join(User, RequestLog.user_id == User.id, isouter=True).where(
        RequestLog.created_at >= start_date
    ).where(
        RequestLog.user_id.isnot(None)
    )
    
    if not current_user.is_superuser:
        query = query.where(RequestLog.user_id == current_user.id)
    
    query = query.group_by(
        RequestLog.user_id, User.username
    ).order_by(
        func.count(RequestLog.id).desc()
    ).limit(limit)
    
    result = await db.execute(query)
    
    stats = []
    for row in result.all():
        stats.append(UserStats(
            user_id=row.user_id,
            username=row.username or "Unknown",
            total_requests=row.total_requests or 0,
            total_input_tokens=int(row.input_tokens or 0),
            total_output_tokens=int(row.output_tokens or 0),
            total_cost=float(row.total_cost or 0),
        ))
    
    return stats
