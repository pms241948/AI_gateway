"""PII Masking configuration and testing API."""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_superuser
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services.masking import get_masking_service, PIIMaskingService

router = APIRouter(prefix="/pii", tags=["PII Masking"])

settings = get_settings()


class PIIConfigResponse(BaseModel):
    """PII configuration response."""
    enabled: bool
    mask_request: bool
    mask_response: bool
    mask_type: str
    language: str
    supported_entities: List[str]


class PIITestRequest(BaseModel):
    """Request for PII masking test."""
    text: str
    language: Optional[str] = "en"


class PIIEntityResult(BaseModel):
    """Single PII entity detection result."""
    entity_type: str
    start: int
    end: int
    score: float
    original: str


class PIITestResponse(BaseModel):
    """Response for PII masking test."""
    original_text: str
    masked_text: str
    entities_found: List[PIIEntityResult]
    entities_count: int


@router.get("/config", response_model=PIIConfigResponse)
async def get_pii_config(
    current_user: User = Depends(get_current_superuser),
):
    """Get current PII masking configuration."""
    masking_service = get_masking_service()
    
    return PIIConfigResponse(
        enabled=settings.pii_masking_enabled,
        mask_request=settings.pii_mask_request,
        mask_response=settings.pii_mask_response,
        mask_type=settings.pii_mask_type,
        language=settings.pii_language,
        supported_entities=masking_service.entities,
    )


@router.post("/test", response_model=PIITestResponse)
async def test_pii_masking(
    request: PIITestRequest,
    current_user: User = Depends(get_current_superuser),
):
    """Test PII masking on sample text.
    
    This endpoint allows administrators to test PII detection
    and masking on sample text before enabling it in production.
    """
    masking_service = get_masking_service()
    
    result = masking_service.mask(
        text=request.text,
        language=request.language or settings.pii_language,
    )
    
    return PIITestResponse(
        original_text=result.original_text,
        masked_text=result.masked_text,
        entities_found=[
            PIIEntityResult(
                entity_type=e["entity_type"],
                start=e["start"],
                end=e["end"],
                score=e["score"],
                original=e["original"],
            )
            for e in result.entities_found
        ],
        entities_count=len(result.entities_found),
    )


@router.get("/entities")
async def get_supported_entities(
    current_user: User = Depends(get_current_superuser),
):
    """Get list of supported PII entity types."""
    return {
        "entities": [
            {
                "id": "EMAIL_ADDRESS",
                "name": "이메일 주소",
                "description": "이메일 주소 (예: user@example.com)",
            },
            {
                "id": "PHONE_NUMBER",
                "name": "전화번호 (국제)",
                "description": "국제 전화번호 형식",
            },
            {
                "id": "KOREAN_PHONE",
                "name": "전화번호 (한국)",
                "description": "한국 휴대폰/유선 전화번호 (예: 010-1234-5678)",
            },
            {
                "id": "KOREAN_RRN",
                "name": "주민등록번호",
                "description": "한국 주민등록번호 (예: 901231-1234567)",
            },
            {
                "id": "CREDIT_CARD",
                "name": "신용카드 번호",
                "description": "신용카드 번호 16자리",
            },
            {
                "id": "IP_ADDRESS",
                "name": "IP 주소",
                "description": "IPv4 또는 IPv6 주소",
            },
            {
                "id": "PERSON",
                "name": "이름/인명",
                "description": "사람 이름 (NLP 기반 탐지)",
            },
        ]
    }
