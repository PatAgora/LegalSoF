"""
Check model for consistency and risk checks.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class CheckType(str, enum.Enum):
    """Type of automated check."""
    AMOUNT_CONSISTENCY = "amount_consistency"
    DATE_ALIGNMENT = "date_alignment"
    IDENTITY_CONSISTENCY = "identity_consistency"
    SOURCE_LEGITIMACY = "source_legitimacy"
    GAP_DETECTION = "gap_detection"
    CIRCULAR_FLOW = "circular_flow"
    UNEXPLAINED_CREDITS = "unexplained_credits"
    MULTIPLE_SOURCES = "multiple_sources"
    TIMING_ANOMALY = "timing_anomaly"
    CURRENCY_MISMATCH = "currency_mismatch"


class CheckSeverity(str, enum.Enum):
    """Severity level of check findings."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CheckStatus(str, enum.Enum):
    """Status of check resolution."""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    WAIVED = "waived"
    ESCALATED = "escalated"


class Check(Base):
    """Check model for automated consistency and risk checks."""
    __tablename__ = "checks"
    
    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    
    # Check details
    check_type = Column(SQLEnum(CheckType), nullable=False)
    severity = Column(SQLEnum(CheckSeverity), nullable=False)
    status = Column(SQLEnum(CheckStatus), nullable=False, default=CheckStatus.PENDING)
    
    # Description
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    rationale = Column(Text)  # Why this check flagged
    
    # Evidence
    affected_entities = Column(JSON)  # List of entity IDs
    affected_documents = Column(JSON)  # List of document IDs
    affected_events = Column(JSON)  # List of event IDs
    
    # Details
    expected_value = Column(String(255))
    actual_value = Column(String(255))
    variance = Column(String(100))
    
    # Resolution
    resolution_notes = Column(Text)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime(timezone=True))
    waiver_reason = Column(Text)
    
    # Auto-check metadata
    is_auto_generated = Column(Boolean, default=True)
    confidence_score = Column(Integer)  # 0-100
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    matter = relationship("Matter", back_populates="checks")
    
    def __repr__(self):
        return f"<Check {self.check_type} - {self.severity}>"
