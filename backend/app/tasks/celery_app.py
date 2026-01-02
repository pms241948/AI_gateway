"""Celery application and tasks for AI Gateway."""
import asyncio
from datetime import datetime

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "ai_gateway",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "health-check-all-models": {
        "task": "app.tasks.celery_app.health_check_all_models",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "cleanup-old-logs": {
        "task": "app.tasks.celery_app.cleanup_old_logs",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}


def run_async(coro):
    """Helper to run async code in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3)
def health_check_all_models(self):
    """Run health check on all active models."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    async def _check_models():
        from app.database import AsyncSessionLocal
        from app.models.llm_model import LLMModel, ModelEndpoint
        from app.models.logs import HealthCheckResult
        from app.providers.base import ProviderConfig
        from app.providers.ollama_provider import OllamaProvider
        from app.providers.openai_compatible import OpenAICompatibleProvider
        
        results = []
        
        async with AsyncSessionLocal() as db:
            # Get all active models with endpoints
            query_result = await db.execute(
                select(LLMModel)
                .where(LLMModel.is_active == True)
                .options(
                    selectinload(LLMModel.endpoints).selectinload(ModelEndpoint.provider)
                )
            )
            models = query_result.scalars().all()
            
            for model in models:
                for endpoint in model.endpoints:
                    if not endpoint.is_active:
                        continue
                    
                    provider = endpoint.provider
                    
                    # Create provider config
                    config = ProviderConfig(
                        base_url=provider.base_url,
                        auth_type=provider.auth_type,
                        auth_credentials=provider.auth_credentials_encrypted,
                        headers=provider.default_headers or {},
                        timeout=provider.timeout_seconds,
                    )
                    
                    # Create provider instance
                    if provider.provider_type == "ollama":
                        provider_instance = OllamaProvider(config, endpoint.provider_model_name)
                    else:
                        provider_instance = OpenAICompatibleProvider(config, endpoint.provider_model_name)
                    
                    # Run health check
                    is_healthy, latency_ms, error_message = await provider_instance.health_check()
                    
                    # Save result
                    health_result = HealthCheckResult(
                        model_id=model.id,
                        endpoint_id=endpoint.id,
                        is_healthy=is_healthy,
                        latency_ms=latency_ms,
                        error_message=error_message,
                    )
                    db.add(health_result)
                    
                    results.append({
                        "model": model.alias,
                        "endpoint": endpoint.id,
                        "healthy": is_healthy,
                        "latency_ms": latency_ms,
                    })
            
            await db.commit()
        
        return results
    
    return run_async(_check_models())


@celery_app.task(bind=True)
def cleanup_old_logs(self, days_to_keep: int = 90):
    """Clean up old request logs."""
    from datetime import timedelta
    from sqlalchemy import delete
    
    async def _cleanup():
        from app.database import AsyncSessionLocal
        from app.models.logs import RequestLog
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(RequestLog).where(RequestLog.created_at < cutoff_date)
            )
            deleted_count = result.rowcount
            await db.commit()
            
        return {"deleted_count": deleted_count, "cutoff_date": cutoff_date.isoformat()}
    
    return run_async(_cleanup())


@celery_app.task(bind=True)
def run_model_health_check(self, model_id: str):
    """Run health check on a specific model."""
    from uuid import UUID
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    async def _check_model():
        from app.database import AsyncSessionLocal
        from app.models.llm_model import LLMModel, ModelEndpoint
        from app.models.logs import HealthCheckResult
        from app.providers.base import ProviderConfig
        from app.providers.ollama_provider import OllamaProvider
        from app.providers.openai_compatible import OpenAICompatibleProvider
        
        results = []
        
        async with AsyncSessionLocal() as db:
            query_result = await db.execute(
                select(LLMModel)
                .where(LLMModel.id == UUID(model_id))
                .options(
                    selectinload(LLMModel.endpoints).selectinload(ModelEndpoint.provider)
                )
            )
            model = query_result.scalar_one_or_none()
            
            if not model:
                return {"error": "Model not found"}
            
            for endpoint in model.endpoints:
                if not endpoint.is_active:
                    continue
                
                provider = endpoint.provider
                
                config = ProviderConfig(
                    base_url=provider.base_url,
                    auth_type=provider.auth_type,
                    auth_credentials=provider.auth_credentials_encrypted,
                    headers=provider.default_headers or {},
                    timeout=provider.timeout_seconds,
                )
                
                if provider.provider_type == "ollama":
                    provider_instance = OllamaProvider(config, endpoint.provider_model_name)
                else:
                    provider_instance = OpenAICompatibleProvider(config, endpoint.provider_model_name)
                
                is_healthy, latency_ms, error_message = await provider_instance.health_check()
                
                health_result = HealthCheckResult(
                    model_id=model.id,
                    endpoint_id=endpoint.id,
                    is_healthy=is_healthy,
                    latency_ms=latency_ms,
                    error_message=error_message,
                )
                db.add(health_result)
                
                results.append({
                    "endpoint_id": str(endpoint.id),
                    "healthy": is_healthy,
                    "latency_ms": latency_ms,
                    "error": error_message,
                })
            
            await db.commit()
        
        return results
    
    return run_async(_check_model())
