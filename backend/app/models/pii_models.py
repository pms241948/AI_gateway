"""PII Configuration Models for NLP models and custom recognizers."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class PIINlpModel(Base):
    """NLP Model configuration for PII detection."""
    
    __tablename__ = "pii_nlp_models"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)  # e.g., "en_core_web_sm"
    lang_code = Column(String(10), nullable=False)  # e.g., "en", "ko"
    model_name = Column(String(100), nullable=False)  # spaCy model name
    description = Column(String(500), nullable=True)
    is_default = Column(Boolean, default=False)  # Default model (cannot be deleted)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<PIINlpModel {self.name} ({self.lang_code})>"


class PIIRecognizer(Base):
    """Custom PII Recognizer with regex patterns."""
    
    __tablename__ = "pii_recognizers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)  # e.g., "KOREAN_PASSPORT"
    display_name = Column(String(100), nullable=False)  # e.g., "한국 여권번호"
    description = Column(String(500), nullable=True)
    pattern = Column(Text, nullable=False)  # Regex pattern
    score = Column(Float, default=0.85)  # Confidence score 0.0-1.0
    context_words = Column(Text, nullable=True)  # JSON array of context words
    is_builtin = Column(Boolean, default=False)  # Built-in recognizers cannot be deleted
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<PIIRecognizer {self.name}>"


class PIIApiEndpoint(Base):
    """External PII API endpoint configuration."""
    
    __tablename__ = "pii_api_endpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)  # Display name
    api_url = Column(String(500), nullable=False)  # e.g., "http://presidio:3000"
    api_type = Column(String(50), default="presidio")  # 'presidio' | 'custom'
    priority = Column(Integer, default=10)  # Lower = higher priority
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    # API paths
    health_check_path = Column(String(100), default="/health")
    analyze_path = Column(String(100), default="/analyze")
    
    # Authentication (optional)
    auth_type = Column(String(50), nullable=True)  # 'bearer' | 'api_key' | None
    auth_token = Column(String(500), nullable=True)
    
    # Status
    last_health_check = Column(DateTime, nullable=True)
    is_healthy = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<PIIApiEndpoint {self.name} ({self.api_url})>"
