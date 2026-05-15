"""
Questionnaire models for dynamic SoF evidence collection.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class SourceType(str, enum.Enum):
    """Source of funds types."""
    BUSINESS_SALE = "business_sale"
    SAVINGS = "savings"
    DIVIDENDS = "dividends"
    LOAN = "loan"
    INHERITANCE = "inheritance"
    GIFT = "gift"
    CRYPTO = "crypto"
    PROPERTY_SALE = "property_sale"
    EMPLOYMENT = "employment"
    INVESTMENT_INCOME = "investment_income"
    OTHER = "other"


class QuestionnaireResponse(Base):
    """Client questionnaire responses."""
    __tablename__ = "questionnaire_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    
    # Source identification
    source_type = Column(SQLEnum(SourceType), nullable=False)
    source_description = Column(Text)
    amount = Column(String(50))  # Store as string to preserve client input
    currency = Column(String(3), default="GBP")
    date_received = Column(String(50))  # Store as string, validate later
    
    # Structured responses (JSON for flexibility)
    questions = Column(JSON)  # {question_id: question_text}
    answers = Column(JSON)    # {question_id: answer}
    
    # Completeness tracking
    is_complete = Column(Boolean, default=False)
    completeness_percentage = Column(Integer, default=0)
    missing_items = Column(JSON)  # List of missing required items
    
    # Required documents for this source type
    required_documents = Column(JSON)  # List of document types needed
    uploaded_document_types = Column(JSON)  # List of types already uploaded
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    matter = relationship("Matter", back_populates="questionnaire_responses")
    
    def __repr__(self):
        return f"<QuestionnaireResponse {self.source_type} - {self.completeness_percentage}%>"
