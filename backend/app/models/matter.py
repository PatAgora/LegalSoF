"""
Matter (case) model - the core entity for SoF reviews.
"""
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Numeric, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class MatterStatus(str, enum.Enum):
    """Matter workflow status."""
    DRAFT = "DRAFT"
    AWAITING_CLIENT = "AWAITING_CLIENT"
    CLIENT_UPLOADING = "CLIENT_UPLOADING"
    UNDER_REVIEW = "UNDER_REVIEW"
    QUERIES_RAISED = "QUERIES_RAISED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class RiskRating(str, enum.Enum):
    """Risk rating levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransactionType(str, enum.Enum):
    """Type of business transaction."""
    BUSINESS_PURCHASE = "BUSINESS_PURCHASE"
    PROPERTY_PURCHASE = "PROPERTY_PURCHASE"
    INVESTMENT = "INVESTMENT"
    OTHER = "OTHER"


class Matter(Base):
    """Matter (case) model."""
    __tablename__ = "matters"
    
    id = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String(50), unique=True, index=True, nullable=False)
    
    # Client & Transaction Details
    client_name = Column(String(255), nullable=False, index=True)
    client_entity_name = Column(String(255))  # If buying entity differs from client
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, default=TransactionType.BUSINESS_PURCHASE)
    target_business_name = Column(String(255))
    target_amount = Column(Numeric(15, 2), nullable=False)
    target_currency = Column(String(3), default="GBP", nullable=False)
    transaction_date = Column(DateTime(timezone=True))
    
    # Status & Risk
    status = Column(SQLEnum(MatterStatus), nullable=False, default=MatterStatus.DRAFT)
    risk_rating = Column(SQLEnum(RiskRating), nullable=False, default=RiskRating.MEDIUM)
    risk_rating_auto = Column(SQLEnum(RiskRating))  # Auto-calculated risk
    risk_rating_override = Column(Boolean, default=False)  # Manual override flag
    risk_notes = Column(Text)
    
    # Assignment
    assigned_analyst_id = Column(Integer, ForeignKey("users.id"))
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Portal
    portal_token = Column(String(500), unique=True, index=True)
    portal_token_expires = Column(DateTime(timezone=True))
    portal_accessed_at = Column(DateTime(timezone=True))
    
    # Metadata
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    assigned_analyst = relationship("User", back_populates="matters_assigned", foreign_keys=[assigned_analyst_id])
    created_by_user = relationship("User", back_populates="matters_created", foreign_keys=[created_by_id])
    
    questionnaire_responses = relationship("QuestionnaireResponse", back_populates="matter", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="matter", cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="matter", cascade="all, delete-orphan")
    funds_events = relationship("FundsEvent", back_populates="matter", cascade="all, delete-orphan")
    checks = relationship("Check", back_populates="matter", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="matter", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="matter", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="matter", cascade="all, delete-orphan")
    
    # Transaction Review relationships
    transactions = relationship("Transaction", back_populates="matter", cascade="all, delete-orphan")
    transaction_alerts = relationship("TransactionAlert", back_populates="matter", cascade="all, delete-orphan")
    kyc_profile = relationship("KYCProfile", back_populates="matter", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Matter {self.reference_number}: {self.client_name}>"
