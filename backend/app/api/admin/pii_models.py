"""PII Model Management API endpoints."""
import json
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_superuser
from app.database import get_db
from app.models.user import User
from app.models.pii_models import PIINlpModel, PIIRecognizer
from app.services.masking import (
    get_masking_service,
    reload_masking_service,
    BUILTIN_RECOGNIZERS,
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
    
    # If no models in DB, return the default
    if not models:
        return [{
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "English (Default)",
            "lang_code": "en",
            "model_name": "en_core_web_sm",
            "description": "Built-in English NLP model (lightweight)",
            "is_default": True,
            "is_enabled": True,
        }]
    
    return models


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
