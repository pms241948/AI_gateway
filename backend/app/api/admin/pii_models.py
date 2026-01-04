"""PII Model Management API endpoints."""
import json
import httpx
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_superuser
from app.database import get_db
from app.models.user import User
from app.models.pii_models import PIINlpModel, PIIRecognizer, PIIApiEndpoint
from app.services.masking import (
    get_masking_service,
    reload_masking_service,
    BUILTIN_RECOGNIZERS,
    set_pii_enabled,
    set_mask_request,
    set_mask_response,
    get_runtime_settings,
    set_model_enabled,
    get_all_models_status,
)

router = APIRouter(prefix="/pii", tags=["PII Management"])


# ============================================================================
# Schemas
# ============================================================================

class NlpModelBase(BaseModel):
    lang_code: str = Field(..., max_length=10, description="Language code (e.g., 'en', 'ko')")
    model_name: str = Field(..., max_length=100, description="spaCy model name")
    description: Optional[str] = None


class NlpModelCreate(NlpModelBase):
    name: str = Field(..., max_length=100, description="Display name")


class NlpModelResponse(NlpModelBase):
    id: UUID
    name: str
    is_default: bool
    is_enabled: bool

    class Config:
        from_attributes = True


class RecognizerBase(BaseModel):
    name: str = Field(..., max_length=50, pattern="^[A-Z_]+$", description="Entity name (uppercase with underscores)")
    display_name: str = Field(..., max_length=100)
    description: Optional[str] = None
    pattern: str = Field(..., description="Regex pattern")
    score: float = Field(default=0.85, ge=0.0, le=1.0)
    context_words: Optional[List[str]] = None


class RecognizerCreate(RecognizerBase):
    pass


class RecognizerUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    pattern: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    context_words: Optional[List[str]] = None
    is_enabled: Optional[bool] = None


class RecognizerResponse(RecognizerBase):
    id: str  # String to support both UUIDs and built-in IDs
    is_builtin: bool
    is_enabled: bool

    class Config:
        from_attributes = True


class PatternTestRequest(BaseModel):
    pattern: str = Field(..., description="Regex pattern to test")
    text: str = Field(..., description="Sample text to test against")


class PatternTestResponse(BaseModel):
    matches: List[dict]
    count: int


# PII API Endpoint Schemas
class PIIApiEndpointBase(BaseModel):
    name: str = Field(..., max_length=100, description="Display name")
    api_url: str = Field(..., max_length=500, description="API URL (e.g., http://presidio:3000)")
    api_type: str = Field(default="presidio", description="API type: presidio or custom")
    priority: int = Field(default=10, ge=1, le=100, description="Priority (lower = higher priority)")
    health_check_path: str = Field(default="/health", description="Health check endpoint path")
    analyze_path: str = Field(default="/analyze", description="Analyze endpoint path")
    auth_type: Optional[str] = Field(default=None, description="Authentication type: bearer, api_key, or None")
    auth_token: Optional[str] = Field(default=None, description="Authentication token")


class PIIApiEndpointCreate(PIIApiEndpointBase):
    pass


class PIIApiEndpointUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    api_type: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=100)
    health_check_path: Optional[str] = None
    analyze_path: Optional[str] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    is_enabled: Optional[bool] = None


class PIIApiEndpointResponse(PIIApiEndpointBase):
    id: UUID
    is_enabled: bool
    is_default: bool
    is_healthy: bool
    last_health_check: Optional[datetime] = None

    class Config:
        from_attributes = True


class PIIApiTestRequest(BaseModel):
    text: str = Field(..., description="Text to analyze")
    language: str = Field(default="en", description="Language code")


class PIIApiTestResponse(BaseModel):
    success: bool
    entities: List[dict] = []
    error: Optional[str] = None


# ============================================================================
# NLP Model Endpoints
# ============================================================================

@router.get("/nlp-models", response_model=List[NlpModelResponse])
async def list_nlp_models(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List all registered NLP models."""
    result = await db.execute(select(PIINlpModel).order_by(PIINlpModel.is_default.desc()))
    models = result.scalars().all()
    
    # Get runtime model status
    models_status = get_all_models_status()
    
    # If no models in DB, return the defaults (English + Korean) with runtime status
    if not models:
        return [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "English (Default)",
                "lang_code": "en",
                "model_name": "en_core_web_sm",
                "description": "Built-in English NLP model (lightweight)",
                "is_default": True,
                "is_enabled": models_status.get("en", True),
            },
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "name": "Korean (Default)",
                "lang_code": "ko",
                "model_name": "ko_core_news_md",
                "description": "한국어 NLP 모델 (NER F-score: 0.75)",
                "is_default": True,
                "is_enabled": models_status.get("ko", True),
            }
        ]
    
    return models


@router.post("/nlp-models/{lang_code}/toggle")
async def toggle_nlp_model(
    lang_code: str,
    current_user: User = Depends(get_current_superuser),
):
    """Toggle an NLP model on or off at runtime (no restart required)."""
    models_status = get_all_models_status()
    
    if lang_code not in models_status:
        raise HTTPException(status_code=404, detail=f"Model for language '{lang_code}' not found")
    
    new_status = not models_status[lang_code]
    set_model_enabled(lang_code, new_status)
    
    return {
        "lang_code": lang_code,
        "is_enabled": new_status,
        "message": f"Model '{lang_code}' {'enabled' if new_status else 'disabled'}"
    }


@router.post("/nlp-models", response_model=NlpModelResponse)
async def add_nlp_model(
    model: NlpModelCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Add a new NLP model.
    
    Note: The spaCy model must be installed in the container first.
    """
    # Check if model already exists
    existing = await db.execute(
        select(PIINlpModel).where(PIINlpModel.lang_code == model.lang_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Model for language '{model.lang_code}' already exists")
    
    db_model = PIINlpModel(
        name=model.name,
        lang_code=model.lang_code,
        model_name=model.model_name,
        description=model.description,
        is_default=False,
        is_enabled=True,
    )
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    
    # Reload masking service with new models
    await _reload_service(db)
    
    return db_model


@router.put("/nlp-models/{model_id}")
async def update_nlp_model(
    model_id: UUID,
    is_enabled: bool,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable an NLP model."""
    result = await db.execute(select(PIINlpModel).where(PIINlpModel.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if model.is_default and not is_enabled:
        raise HTTPException(status_code=400, detail="Cannot disable default model")
    
    model.is_enabled = is_enabled
    await db.commit()
    
    await _reload_service(db)
    
    return {"message": "Model updated", "is_enabled": is_enabled}


@router.delete("/nlp-models/{model_id}")
async def delete_nlp_model(
    model_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete an NLP model."""
    result = await db.execute(select(PIINlpModel).where(PIINlpModel.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if model.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default model")
    
    await db.delete(model)
    await db.commit()
    
    await _reload_service(db)
    
    return {"message": "Model deleted"}


# ============================================================================
# Recognizer Endpoints
# ============================================================================

@router.get("/recognizers", response_model=List[RecognizerResponse])
async def list_recognizers(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List all PII recognizers (built-in + custom)."""
    # Get custom recognizers from DB
    result = await db.execute(select(PIIRecognizer).order_by(PIIRecognizer.is_builtin.desc()))
    db_recognizers = result.scalars().all()
    
    recognizers = []
    
    # Add built-in recognizers that aren't in DB
    builtin_in_db = {r.name for r in db_recognizers if r.is_builtin}
    for name, recognizer_class in BUILTIN_RECOGNIZERS.items():
        if name not in builtin_in_db:
            recognizers.append({
                "id": f"builtin-{name.lower()}",
                "name": name,
                "display_name": getattr(recognizer_class, 'BUILTIN_DISPLAY', name),
                "description": f"Built-in {name} recognizer",
                "pattern": getattr(recognizer_class, 'BUILTIN_PATTERN', ''),
                "score": 0.9,
                "context_words": [],
                "is_builtin": True,
                "is_enabled": True,
            })
    
    # Add DB recognizers
    for r in db_recognizers:
        context_words = []
        if r.context_words:
            try:
                context_words = json.loads(r.context_words)
            except json.JSONDecodeError:
                pass
        
        recognizers.append({
            "id": str(r.id),
            "name": r.name,
            "display_name": r.display_name,
            "description": r.description,
            "pattern": r.pattern,
            "score": r.score,
            "context_words": context_words,
            "is_builtin": r.is_builtin,
            "is_enabled": r.is_enabled,
        })
    
    return recognizers


@router.post("/recognizers", response_model=RecognizerResponse)
async def create_recognizer(
    recognizer: RecognizerCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Create a new custom PII recognizer."""
    # Check if name already exists
    existing = await db.execute(
        select(PIIRecognizer).where(PIIRecognizer.name == recognizer.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Recognizer '{recognizer.name}' already exists")
    
    # Also check built-ins
    if recognizer.name in BUILTIN_RECOGNIZERS:
        raise HTTPException(status_code=400, detail=f"'{recognizer.name}' is a built-in recognizer")
    
    # Validate regex pattern
    import re
    try:
        re.compile(recognizer.pattern)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {e}")
    
    context_words_json = json.dumps(recognizer.context_words) if recognizer.context_words else None
    
    db_recognizer = PIIRecognizer(
        name=recognizer.name,
        display_name=recognizer.display_name,
        description=recognizer.description,
        pattern=recognizer.pattern,
        score=recognizer.score,
        context_words=context_words_json,
        is_builtin=False,
        is_enabled=True,
    )
    db.add(db_recognizer)
    await db.commit()
    await db.refresh(db_recognizer)
    
    await _reload_service(db)
    
    return {
        **db_recognizer.__dict__,
        "context_words": recognizer.context_words or [],
    }


@router.put("/recognizers/{recognizer_id}", response_model=RecognizerResponse)
async def update_recognizer(
    recognizer_id: UUID,
    update: RecognizerUpdate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Update a custom PII recognizer."""
    result = await db.execute(select(PIIRecognizer).where(PIIRecognizer.id == recognizer_id))
    recognizer = result.scalar_one_or_none()
    
    if not recognizer:
        raise HTTPException(status_code=404, detail="Recognizer not found")
    
    if recognizer.is_builtin:
        # Only allow enabling/disabling built-ins
        if update.is_enabled is not None:
            recognizer.is_enabled = update.is_enabled
        else:
            raise HTTPException(status_code=400, detail="Cannot modify built-in recognizer (only enable/disable)")
    else:
        # Update fields
        if update.display_name is not None:
            recognizer.display_name = update.display_name
        if update.description is not None:
            recognizer.description = update.description
        if update.pattern is not None:
            import re
            try:
                re.compile(update.pattern)
            except re.error as e:
                raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {e}")
            recognizer.pattern = update.pattern
        if update.score is not None:
            recognizer.score = update.score
        if update.context_words is not None:
            recognizer.context_words = json.dumps(update.context_words)
        if update.is_enabled is not None:
            recognizer.is_enabled = update.is_enabled
    
    await db.commit()
    await db.refresh(recognizer)
    
    await _reload_service(db)
    
    context_words = []
    if recognizer.context_words:
        try:
            context_words = json.loads(recognizer.context_words)
        except json.JSONDecodeError:
            pass
    
    return {
        **recognizer.__dict__,
        "context_words": context_words,
    }


@router.delete("/recognizers/{recognizer_id}")
async def delete_recognizer(
    recognizer_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom PII recognizer."""
    result = await db.execute(select(PIIRecognizer).where(PIIRecognizer.id == recognizer_id))
    recognizer = result.scalar_one_or_none()
    
    if not recognizer:
        raise HTTPException(status_code=404, detail="Recognizer not found")
    
    if recognizer.is_builtin:
        raise HTTPException(status_code=400, detail="Cannot delete built-in recognizer")
    
    await db.delete(recognizer)
    await db.commit()
    
    await _reload_service(db)
    
    return {"message": "Recognizer deleted"}


@router.post("/recognizers/test", response_model=PatternTestResponse)
async def test_pattern(
    request: PatternTestRequest,
    current_user: User = Depends(get_current_superuser),
):
    """Test a regex pattern against sample text."""
    import re
    
    try:
        pattern = re.compile(request.pattern)
    except re.error as e:
        raise HTTPException(status_code=400, detail=f"Invalid regex pattern: {e}")
    
    matches = []
    for match in pattern.finditer(request.text):
        matches.append({
            "text": match.group(),
            "start": match.start(),
            "end": match.end(),
        })
    
    return PatternTestResponse(matches=matches, count=len(matches))


# ============================================================================
# Helper Functions
# ============================================================================

async def _reload_service(db: AsyncSession):
    """Reload the masking service with current DB configuration."""
    try:
        # Get enabled NLP models
        result = await db.execute(
            select(PIINlpModel).where(PIINlpModel.is_enabled == True)
        )
        nlp_models = result.scalars().all()
        
        nlp_config = [
            {"lang_code": m.lang_code, "model_name": m.model_name}
            for m in nlp_models
        ]
        
        # If no models in DB, use default
        if not nlp_config:
            nlp_config = [{"lang_code": "en", "model_name": "en_core_web_sm"}]
        
        # Get enabled custom recognizers
        result = await db.execute(
            select(PIIRecognizer).where(
                PIIRecognizer.is_enabled == True,
                PIIRecognizer.is_builtin == False
            )
        )
        custom_recognizers = result.scalars().all()
        
        recognizer_configs = []
        for r in custom_recognizers:
            context_words = []
            if r.context_words:
                try:
                    context_words = json.loads(r.context_words)
                except json.JSONDecodeError:
                    pass
            
            recognizer_configs.append({
                "name": r.name,
                "pattern": r.pattern,
                "score": r.score,
                "context_words": context_words,
            })
        
        # Reload service
        reload_masking_service(
            nlp_models=nlp_config,
            custom_recognizers=recognizer_configs,
        )
        
    except Exception as e:
        import logging
        logging.error(f"Failed to reload masking service: {e}")


# ============================================================================
# External PII API Endpoints
# ============================================================================

@router.get("/endpoints", response_model=List[PIIApiEndpointResponse])
async def list_pii_endpoints(
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """List all registered external PII API endpoints."""
    result = await db.execute(
        select(PIIApiEndpoint).order_by(PIIApiEndpoint.priority)
    )
    return result.scalars().all()


@router.post("/endpoints", response_model=PIIApiEndpointResponse)
async def create_pii_endpoint(
    endpoint: PIIApiEndpointCreate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Register a new external PII API endpoint."""
    # Check if name already exists
    existing = await db.execute(
        select(PIIApiEndpoint).where(PIIApiEndpoint.name == endpoint.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Endpoint '{endpoint.name}' already exists")
    
    db_endpoint = PIIApiEndpoint(
        name=endpoint.name,
        api_url=endpoint.api_url,
        api_type=endpoint.api_type,
        priority=endpoint.priority,
        health_check_path=endpoint.health_check_path,
        analyze_path=endpoint.analyze_path,
        auth_type=endpoint.auth_type,
        auth_token=endpoint.auth_token,
        is_enabled=True,
        is_default=False,
    )
    db.add(db_endpoint)
    await db.commit()
    await db.refresh(db_endpoint)
    
    return db_endpoint


@router.get("/endpoints/{endpoint_id}", response_model=PIIApiEndpointResponse)
async def get_pii_endpoint(
    endpoint_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific PII API endpoint."""
    result = await db.execute(
        select(PIIApiEndpoint).where(PIIApiEndpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return endpoint


@router.put("/endpoints/{endpoint_id}", response_model=PIIApiEndpointResponse)
async def update_pii_endpoint(
    endpoint_id: UUID,
    update: PIIApiEndpointUpdate,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Update a PII API endpoint."""
    result = await db.execute(
        select(PIIApiEndpoint).where(PIIApiEndpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    # Update fields
    if update.name is not None:
        endpoint.name = update.name
    if update.api_url is not None:
        endpoint.api_url = update.api_url
    if update.api_type is not None:
        endpoint.api_type = update.api_type
    if update.priority is not None:
        endpoint.priority = update.priority
    if update.health_check_path is not None:
        endpoint.health_check_path = update.health_check_path
    if update.analyze_path is not None:
        endpoint.analyze_path = update.analyze_path
    if update.auth_type is not None:
        endpoint.auth_type = update.auth_type
    if update.auth_token is not None:
        endpoint.auth_token = update.auth_token
    if update.is_enabled is not None:
        endpoint.is_enabled = update.is_enabled
    
    await db.commit()
    await db.refresh(endpoint)
    return endpoint


@router.delete("/endpoints/{endpoint_id}")
async def delete_pii_endpoint(
    endpoint_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Delete a PII API endpoint."""
    result = await db.execute(
        select(PIIApiEndpoint).where(PIIApiEndpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    if endpoint.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default endpoint")
    
    await db.delete(endpoint)
    await db.commit()
    return {"message": "Endpoint deleted"}


@router.post("/endpoints/{endpoint_id}/test", response_model=PIIApiTestResponse)
async def test_pii_endpoint(
    endpoint_id: UUID,
    request: PIIApiTestRequest,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Test a PII API endpoint by sending a sample request."""
    result = await db.execute(
        select(PIIApiEndpoint).where(PIIApiEndpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    # Build request headers
    headers = {"Content-Type": "application/json"}
    if endpoint.auth_type == "bearer" and endpoint.auth_token:
        headers["Authorization"] = f"Bearer {endpoint.auth_token}"
    elif endpoint.auth_type == "api_key" and endpoint.auth_token:
        headers["X-API-Key"] = endpoint.auth_token
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test analyze endpoint
            url = f"{endpoint.api_url.rstrip('/')}{endpoint.analyze_path}"
            
            if endpoint.api_type == "presidio":
                # Presidio format
                payload = {
                    "text": request.text,
                    "language": request.language,
                }
            else:
                # Custom format - same as presidio for now
                payload = {
                    "text": request.text,
                    "language": request.language,
                }
            
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                entities = response.json()
                # Update health status
                endpoint.is_healthy = True
                endpoint.last_health_check = datetime.utcnow()
                await db.commit()
                
                return PIIApiTestResponse(
                    success=True,
                    entities=entities if isinstance(entities, list) else [],
                )
            else:
                endpoint.is_healthy = False
                endpoint.last_health_check = datetime.utcnow()
                await db.commit()
                
                return PIIApiTestResponse(
                    success=False,
                    error=f"API returned status {response.status_code}: {response.text[:200]}",
                )
                
    except httpx.TimeoutException:
        endpoint.is_healthy = False
        endpoint.last_health_check = datetime.utcnow()
        await db.commit()
        return PIIApiTestResponse(success=False, error="Connection timeout")
    except httpx.ConnectError as e:
        endpoint.is_healthy = False
        endpoint.last_health_check = datetime.utcnow()
        await db.commit()
        return PIIApiTestResponse(success=False, error=f"Connection failed: {str(e)}")
    except Exception as e:
        return PIIApiTestResponse(success=False, error=f"Error: {str(e)}")


@router.post("/endpoints/{endpoint_id}/health")
async def check_pii_endpoint_health(
    endpoint_id: UUID,
    current_user: User = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Check health of a PII API endpoint."""
    result = await db.execute(
        select(PIIApiEndpoint).where(PIIApiEndpoint.id == endpoint_id)
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{endpoint.api_url.rstrip('/')}{endpoint.health_check_path}"
            response = await client.get(url)
            
            is_healthy = response.status_code == 200
            endpoint.is_healthy = is_healthy
            endpoint.last_health_check = datetime.utcnow()
            await db.commit()
            
            return {
                "healthy": is_healthy,
                "status_code": response.status_code,
                "checked_at": endpoint.last_health_check,
            }
    except Exception as e:
        endpoint.is_healthy = False
        endpoint.last_health_check = datetime.utcnow()
        await db.commit()
        return {
            "healthy": False,
            "error": str(e),
            "checked_at": endpoint.last_health_check,
        }


# ============================================================================
# Runtime Toggle Endpoints (Dynamic PII Enable/Disable)
# ============================================================================

class RuntimeSettingsResponse(BaseModel):
    enabled: bool
    mask_request: bool
    mask_response: bool


class RuntimeSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    mask_request: Optional[bool] = None
    mask_response: Optional[bool] = None


@router.get("/runtime-settings", response_model=RuntimeSettingsResponse)
async def get_pii_runtime_settings(
    current_user: User = Depends(get_current_superuser),
):
    """Get current runtime PII masking settings."""
    return get_runtime_settings()


@router.put("/runtime-settings", response_model=RuntimeSettingsResponse)
async def update_pii_runtime_settings(
    settings: RuntimeSettingsUpdate,
    current_user: User = Depends(get_current_superuser),
):
    """Update runtime PII masking settings (no server restart required)."""
    if settings.enabled is not None:
        set_pii_enabled(settings.enabled)
    if settings.mask_request is not None:
        set_mask_request(settings.mask_request)
    if settings.mask_response is not None:
        set_mask_response(settings.mask_response)
    
    return get_runtime_settings()
