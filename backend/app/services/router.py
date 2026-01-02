"""Model routing service."""
import random
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ModelNotFoundError, ProviderNotAvailableError
from app.models.llm_model import LLMModel, ModelEndpoint, UserModelAccess, OrgModelAccess
from app.models.provider import Provider
from app.models.user import User
from app.providers.base import BaseProvider, ProviderConfig
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


class AccessDeniedError(Exception):
    """User does not have access to the requested model."""
    def __init__(self, alias: str):
        self.alias = alias
        super().__init__(f"Access denied to model: {alias}")


class ModelRouter:
    """Service for routing requests to appropriate model endpoints."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_user_access(
        self,
        model: LLMModel,
        user: User,
    ) -> bool:
        """Check if user has access to the model.
        
        Access is granted if:
        1. User is a superuser (full access)
        2. User has direct UserModelAccess
        3. User's organization has OrgModelAccess
        """
        if user.is_superuser:
            return True
        
        # Check user-level access
        result = await self.db.execute(
            select(UserModelAccess).where(
                UserModelAccess.user_id == user.id,
                UserModelAccess.model_id == model.id,
                UserModelAccess.is_allowed == True
            )
        )
        if result.scalar_one_or_none():
            return True
        
        # Check organization-level access
        if user.organization_id:
            result = await self.db.execute(
                select(OrgModelAccess).where(
                    OrgModelAccess.organization_id == user.organization_id,
                    OrgModelAccess.model_id == model.id,
                    OrgModelAccess.is_allowed == True
                )
            )
            if result.scalar_one_or_none():
                return True
        
        return False
    
    async def get_model_by_alias(
        self,
        alias: str,
        user: Optional[User] = None,
    ) -> LLMModel:
        """Get a model by its alias, checking access if user provided."""
        result = await self.db.execute(
            select(LLMModel)
            .where(LLMModel.alias == alias)
            .where(LLMModel.is_active == True)
            .options(
                selectinload(LLMModel.endpoints).selectinload(ModelEndpoint.provider)
            )
        )
        model = result.scalar_one_or_none()
        
        if not model:
            raise ModelNotFoundError(alias)
        
        # Check approval status
        if model.approval_status != "approved":
            raise ModelNotFoundError(alias)
        
        # Check user access permissions
        if user and not await self.check_user_access(model, user):
            raise AccessDeniedError(alias)
        
        return model
    
    async def select_endpoint(
        self,
        model: LLMModel,
    ) -> tuple[ModelEndpoint, Provider]:
        """Select the best available endpoint for a model.
        
        Uses priority-based selection with weighted random for load balancing.
        """
        active_endpoints = [ep for ep in model.endpoints if ep.is_active]
        
        if not active_endpoints:
            raise ProviderNotAvailableError(model.alias)
        
        # Sort by priority (higher first)
        active_endpoints.sort(key=lambda x: x.priority, reverse=True)
        
        # Get endpoints with highest priority
        max_priority = active_endpoints[0].priority
        top_endpoints = [ep for ep in active_endpoints if ep.priority == max_priority]
        
        # If multiple endpoints with same priority, use weighted random
        if len(top_endpoints) > 1:
            total_weight = sum(ep.weight for ep in top_endpoints)
            r = random.uniform(0, total_weight)
            cumulative = 0
            for ep in top_endpoints:
                cumulative += ep.weight
                if r <= cumulative:
                    return ep, ep.provider
            # Fallback
            return top_endpoints[0], top_endpoints[0].provider
        
        return top_endpoints[0], top_endpoints[0].provider
    
    def create_provider_instance(
        self,
        endpoint: ModelEndpoint,
        provider: Provider,
    ) -> BaseProvider:
        """Create a provider instance for the given endpoint."""
        config = ProviderConfig(
            base_url=provider.base_url,
            auth_type=provider.auth_type,
            auth_credentials=provider.auth_credentials_encrypted,  # TODO: Decrypt
            headers=provider.default_headers or {},
            timeout=provider.timeout_seconds,
            max_retries=provider.max_retries,
        )
        
        # Select provider class based on type
        provider_classes = {
            "ollama": OllamaProvider,
            "openai": OpenAICompatibleProvider,
            "openai_compatible": OpenAICompatibleProvider,
            "vllm": OpenAICompatibleProvider,
            "anthropic": OpenAICompatibleProvider,  # TODO: Dedicated provider
        }
        
        provider_class = provider_classes.get(
            provider.provider_type,
            OpenAICompatibleProvider
        )
        
        return provider_class(config, endpoint.provider_model_name)
    
    async def route_request(
        self,
        alias: str,
        user: Optional[User] = None,
    ) -> tuple[LLMModel, ModelEndpoint, BaseProvider]:
        """Route a request to the appropriate model and endpoint.
        
        Returns:
            Tuple of (model, endpoint, provider_instance)
        """
        model = await self.get_model_by_alias(alias, user)
        endpoint, provider = await self.select_endpoint(model)
        provider_instance = self.create_provider_instance(endpoint, provider)
        
        return model, endpoint, provider_instance
