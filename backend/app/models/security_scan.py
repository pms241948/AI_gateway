"""Security Scan database models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class ScanStatus(str, enum.Enum):
    """Scan execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanType(str, enum.Enum):
    """Type of security scan."""
    QUICK = "quick"           # Fast basic checks
    STANDARD = "standard"     # Standard probe set
    COMPREHENSIVE = "comprehensive"  # Full scan with all probes


class VulnerabilitySeverity(str, enum.Enum):
    """Vulnerability severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SecurityScanProfile(Base):
    """Scan configuration profile (reusable scan settings)."""
    __tablename__ = "security_scan_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    scan_type = Column(SQLEnum(ScanType), default=ScanType.STANDARD)
    
    # Probe configuration (which tests to run)
    probes_config = Column(JSON, default=dict)
    # Categories to test: prompt_injection, jailbreak, data_leakage, toxicity, hallucination
    enabled_categories = Column(JSON, default=list)
    
    # Limits
    max_probes = Column(Integer, default=100)
    timeout_seconds = Column(Integer, default=300)
    
    is_default = Column(Boolean, default=False)
    is_enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    scan_results = relationship("SecurityScanResult", back_populates="profile")


class SecurityScanResult(Base):
    """Security scan execution result."""
    __tablename__ = "security_scan_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Target model
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=True)
    model_alias = Column(String(255), nullable=False)  # Store alias for history
    
    # Scan configuration
    profile_id = Column(UUID(as_uuid=True), ForeignKey("security_scan_profiles.id"), nullable=True)
    scan_type = Column(SQLEnum(ScanType), default=ScanType.STANDARD)
    
    # Status
    status = Column(SQLEnum(ScanStatus), default=ScanStatus.PENDING)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Results summary
    total_probes = Column(Integer, default=0)
    passed_probes = Column(Integer, default=0)
    failed_probes = Column(Integer, default=0)
    
    # Vulnerability counts by severity
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    
    # Overall score (0-100, higher is more secure)
    security_score = Column(Integer, nullable=True)
    
    # Detailed results (JSON array of individual probe results)
    detailed_results = Column(JSON, default=list)
    
    # Error message if failed
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = relationship("SecurityScanProfile", back_populates="scan_results")
    model = relationship("LLMModel", back_populates="security_scans")


class SecurityVulnerability(Base):
    """Individual vulnerability finding from a scan."""
    __tablename__ = "security_vulnerabilities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    scan_result_id = Column(UUID(as_uuid=True), ForeignKey("security_scan_results.id"), nullable=False)
    
    # Vulnerability details
    category = Column(String(100), nullable=False)  # prompt_injection, jailbreak, etc.
    probe_name = Column(String(255), nullable=False)
    severity = Column(SQLEnum(VulnerabilitySeverity), default=VulnerabilitySeverity.MEDIUM)
    
    # Input/Output
    probe_input = Column(Text, nullable=True)
    model_output = Column(Text, nullable=True)
    
    # Detection details
    detection_reason = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    
    # Is it a false positive? (can be marked by admin)
    is_false_positive = Column(Boolean, default=False)
    false_positive_note = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    scan_result = relationship("SecurityScanResult", backref="vulnerabilities")
