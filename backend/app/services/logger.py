"""Request logging service."""
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.logs import AuditLog, RequestLog
from app.models.user import User
from app.providers.base import ProviderResponse

settings = get_settings()


class RequestLogger:
    """Service for logging API requests and responses."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_request(
        self,
        user: Optional[User],
        model_id: Optional[UUID],
        provider_id: Optional[UUID],
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: int,
        provider_response: Optional[ProviderResponse] = None,
        request_body: Optional[Dict[str, Any]] = None,
        response_body: Optional[Dict[str, Any]] = None,
        request_metadata: Optional[Dict[str, Any]] = None,
        cost: Optional[Decimal] = None,
    ) -> RequestLog:
        """Log an API request and response."""
        request_id = f"req-{uuid.uuid4().hex[:24]}"
        
        # Prepare request/response bodies based on settings
        stored_request_body = None
        stored_response_body = None
        body_masked = False
        
        if settings.log_request_body and request_body:
            stored_request_body = json.dumps(request_body, ensure_ascii=False)
        
        if settings.log_response_body and response_body:
            stored_response_body = json.dumps(response_body, ensure_ascii=False)
        
        # Extract token usage from provider response
        input_tokens = None
        output_tokens = None
        if provider_response:
            input_tokens = provider_response.input_tokens
            output_tokens = provider_response.output_tokens
        
        log = RequestLog(
            user_id=user.id if user else None,
            model_id=model_id,
            provider_id=provider_id,
            request_id=request_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            request_metadata=request_metadata,
            request_body=stored_request_body,
            response_body=stored_response_body,
            body_masked=body_masked,
        )
        
        self.db.add(log)
        await self.db.flush()
        
        return log
    
    async def log_audit(
        self,
        user: Optional[User],
        action: str,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log an administrative action."""
        log = AuditLog(
            user_id=user.id if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )
        
        self.db.add(log)
        await self.db.flush()
        
        return log
