"""
FundsEvent model for tracking the funds chain.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Boolean, JSON, Enum as SQLEnum, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class EventType(str, enum.Enum):
    """Type of funds event."""
    SOURCE_GENERATION = "source_generation"  # Original source (sale, inheritance, etc.)
    TRANSFER = "transfer"  # Movement between accounts
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    PAYMENT = "payment"  # Final payment for purchase
    FEE_DEDUCTION = "fee_deduction"
    CURRENCY_CONVERSION = "currency_conversion"
    OTHER = "other"


# Association table for many-to-many relationship between documents and events
document_event_links = Table(
    "document_event_links",
    Base.metadata,
    Column("document_id", Integer, ForeignKey("documents.id"), primary_key=True),
    Column("funds_event_id", Integer, ForeignKey("fundsevents.id"), primary_key=True),
)


class FundsEvent(Base):
    """Funds event model for tracking money flow."""
    __tablename__ = "fundsevents"
    
    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    
    # Event classification
    event_type = Column(SQLEnum(EventType), nullable=False)
    description = Column(Text, nullable=False)
    
    # Amount details
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="GBP")
    fees = Column(Numeric(15, 2), default=0)
    net_amount = Column(Numeric(15, 2))  # Amount minus fees
    
    # Exchange rate (if currency conversion)
    exchange_rate = Column(Numeric(10, 6))
    converted_amount = Column(Numeric(15, 2))
    converted_currency = Column(String(3))
    
    # Timing
    event_date = Column(DateTime(timezone=True), nullable=False)
    value_date = Column(DateTime(timezone=True))  # When funds actually available
    
    # Parties involved
    source_entity_id = Column(Integer, ForeignKey("entities.id"))
    destination_entity_id = Column(Integer, ForeignKey("entities.id"))
    
    # Transaction details
    reference = Column(String(255))
    transaction_id = Column(String(255))
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verification_method = Column(String(100))  # manual, document_match, etc.
    confidence_score = Column(Integer)  # 0-100
    
    # Chain position
    sequence_order = Column(Integer)  # Order in the funds chain
    is_originating_event = Column(Boolean, default=False)
    is_final_payment = Column(Boolean, default=False)
    
    # Flags
    has_issues = Column(Boolean, default=False)
    issue_description = Column(Text)
    
    # Manual entry
    is_manual = Column(Boolean, default=False)
    added_by_user_id = Column(Integer, ForeignKey("users.id"))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    matter = relationship("Matter", back_populates="funds_events")
    source_entity = relationship("Entity", foreign_keys=[source_entity_id], back_populates="events_as_source")
    destination_entity = relationship("Entity", foreign_keys=[destination_entity_id], back_populates="events_as_destination")
    evidence_documents = relationship("Document", secondary=document_event_links, back_populates="linked_events")
    
    def __repr__(self):
        return f"<FundsEvent {self.event_type}: {self.amount} {self.currency}>"
