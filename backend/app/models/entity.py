"""
Entity model for tracking parties, accounts, and organizations.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum as SQLEnum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class EntityType(str, enum.Enum):
    """Type of entity."""
    PERSON = "person"
    COMPANY = "company"
    BANK_ACCOUNT = "bank_account"
    TRUST = "trust"
    PARTNERSHIP = "partnership"
    OTHER = "other"


class Entity(Base):
    """Entity model for parties and accounts in funds flow."""
    __tablename__ = "entities"
    
    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    source_document_id = Column(Integer, ForeignKey("documents.id"))
    
    # Entity identification
    entity_type = Column(SQLEnum(EntityType), nullable=False)
    name = Column(String(255), nullable=False, index=True)
    aliases = Column(JSON)  # List of alternative names found
    
    # Additional details
    registration_number = Column(String(100))  # Company number, etc.
    address = Column(Text)
    country = Column(String(100))
    
    # Bank account details (if entity_type is BANK_ACCOUNT)
    account_number_partial = Column(String(50))  # Last 4 digits
    sort_code = Column(String(20))
    iban = Column(String(50))
    swift_bic = Column(String(20))
    bank_name = Column(String(255))
    
    # Confidence & verification
    confidence_score = Column(Integer)  # 0-100
    is_verified = Column(Boolean, default=False)
    verification_notes = Column(Text)
    
    # Metadata
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    matter = relationship("Matter", back_populates="entities")
    source_document = relationship("Document", back_populates="extracted_entities")
    events_as_source = relationship("FundsEvent", foreign_keys="FundsEvent.source_entity_id", back_populates="source_entity")
    events_as_destination = relationship("FundsEvent", foreign_keys="FundsEvent.destination_entity_id", back_populates="destination_entity")
    
    def __repr__(self):
        return f"<Entity {self.name} ({self.entity_type})>"
