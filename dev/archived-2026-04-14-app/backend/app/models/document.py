"""
Document model for uploaded evidence files.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, Enum as SQLEnum, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class DocumentType(str, enum.Enum):
    """Document classification types."""
    BANK_STATEMENT = "bank_statement"
    COMPLETION_STATEMENT = "completion_statement"
    SALE_PURCHASE_AGREEMENT = "sale_purchase_agreement"
    COMPANY_ACCOUNTS = "company_accounts"
    TAX_RETURN = "tax_return"
    INVOICE = "invoice"
    LOAN_AGREEMENT = "loan_agreement"
    PROBATE_LETTER = "probate_letter"
    EXCHANGE_STATEMENT = "exchange_statement"
    PAYSLIP = "payslip"
    DIVIDEND_VOUCHER = "dividend_voucher"
    PROPERTY_DEED = "property_deed"
    GIFT_LETTER = "gift_letter"
    ID_DOCUMENT = "id_document"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    """Document processing status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    REJECTED = "rejected"


class QualityIssue(str, enum.Enum):
    """Document quality issues."""
    BLURRED = "blurred"
    PASSWORD_PROTECTED = "password_protected"
    MISSING_PAGES = "missing_pages"
    INCOMPLETE = "incomplete"
    ILLEGIBLE = "illegible"
    CORRUPTED = "corrupted"


class Document(Base):
    """Document model."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    
    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)  # In bytes
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64))  # SHA-256 hash
    
    # Classification
    document_type = Column(SQLEnum(DocumentType), nullable=False, default=DocumentType.OTHER)
    document_type_confidence = Column(Integer)  # 0-100
    
    # Metadata
    issuer = Column(String(255))  # Bank name, company name, etc.
    date_from = Column(DateTime(timezone=True))
    date_to = Column(DateTime(timezone=True))
    account_holder = Column(String(255))
    account_number_partial = Column(String(50))  # Last 4 digits only
    currency = Column(String(3))
    
    # Processing status
    status = Column(SQLEnum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED)
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    
    # Quality checks
    quality_score = Column(Integer)  # 0-100
    quality_issues = Column(JSON)  # List of QualityIssue enum values
    
    # Extraction results
    extracted_data = Column(JSON)  # Structured extraction results
    extraction_confidence = Column(Integer)  # 0-100
    ocr_performed = Column(Boolean, default=False)
    ai_assisted = Column(Boolean, default=False)
    
    # User corrections
    user_corrections = Column(JSON)  # Track manual corrections for learning
    
    # Page information
    page_count = Column(Integer)
    
    # Notes
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    uploaded_by = Column(String(50))  # 'client' or user_id
    
    # Relationships
    matter = relationship("Matter", back_populates="documents")
    extracted_entities = relationship("Entity", back_populates="source_document")
    linked_events = relationship("FundsEvent", secondary="document_event_links", back_populates="evidence_documents")
    
    def __repr__(self):
        return f"<Document {self.original_filename} ({self.document_type})>"
