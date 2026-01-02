"""Custom exceptions for AI Gateway."""
from typing import Any, Dict, Optional


class AIGatewayException(Exception):
    """Base exception for AI Gateway."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_type: str = "internal_error",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to OpenAI-compatible error format."""
        return {
            "error": {
                "message": self.message,
                "type": self.error_type,
                "code": self.error_type,
                **self.details,
            }
        }


class AuthenticationError(AIGatewayException):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=401,
            error_type="authentication_error",
        )


class AuthorizationError(AIGatewayException):
    """Authorization failed - user lacks required permissions."""
    
    def __init__(
        self, 
        message: str = "You don't have permission to perform this action",
        resource: Optional[str] = None,
    ):
        details = {}
        if resource:
            details["resource"] = resource
        super().__init__(
            message=message,
            status_code=403,
            error_type="authorization_error",
            details=details,
        )


class NotFoundError(AIGatewayException):
    """Resource not found."""
    
    def __init__(
        self, 
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        super().__init__(
            message=message,
            status_code=404,
            error_type="not_found_error",
            details=details,
        )


class ValidationError(AIGatewayException):
    """Validation error."""
    
    def __init__(
        self, 
        message: str = "Validation error",
        field: Optional[str] = None,
    ):
        details = {}
        if field:
            details["param"] = field
        super().__init__(
            message=message,
            status_code=400,
            error_type="invalid_request_error",
            details=details,
        )


class RateLimitError(AIGatewayException):
    """Rate limit exceeded."""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(
            message=message,
            status_code=429,
            error_type="rate_limit_error",
            details=details,
        )


class ProviderError(AIGatewayException):
    """Error from LLM provider."""
    
    def __init__(
        self,
        message: str = "Provider error",
        provider: Optional[str] = None,
        original_error: Optional[str] = None,
        status_code: int = 502,
    ):
        details = {}
        if provider:
            details["provider"] = provider
        if original_error:
            details["original_error"] = original_error
        super().__init__(
            message=message,
            status_code=status_code,
            error_type="provider_error",
            details=details,
        )


class ModelNotFoundError(NotFoundError):
    """Model not found or not accessible."""
    
    def __init__(self, model_alias: str):
        super().__init__(
            message=f"Model '{model_alias}' not found or not accessible",
            resource_type="model",
            resource_id=model_alias,
        )


class ProviderNotAvailableError(ProviderError):
    """All provider endpoints are unavailable."""
    
    def __init__(self, model_alias: str):
        super().__init__(
            message=f"No available endpoints for model '{model_alias}'",
            status_code=503,
        )
