"""
Note, Approval, and AuditLog models.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON, Enum as SQLEnum, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class Note(Base):
    """Note model for matter commentary."""
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=True)  # Internal vs client-visible
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    matter = relationship("Matter", back_populates="notes")
    user = relationship("User", back_populates="notes")
    
    def __repr__(self):
        return f"<Note {self.id} on Matter {self.matter_id}>"


class ApprovalType(str, enum.Enum):
    """Type of approval."""
    RISK_RATING = "risk_rating"
    SOF_ASSESSMENT = "sof_assessment"
    MATTER_COMPLETION = "matter_completion"
    CHECK_WAIVER = "check_waiver"


class ApprovalStatus(str, enum.Enum):
    """Approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Approval(Base):
    """Approval model for partner/senior review."""
    __tablename__ = "approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False)
    
    approval_type = Column(SQLEnum(ApprovalType), nullable=False)
    status = Column(SQLEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING)
    
    requested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    
    comments = Column(Text)
    
    # Relationships
    matter = relationship("Matter", back_populates="approvals")
    
    def __repr__(self):
        return f"<Approval {self.approval_type} - {self.status}>"


class AuditLogAction(str, enum.Enum):
    """Audit log action types."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    VIEWED = "viewed"
    EXPORTED = "exported"
    APPROVED = "approved"
    REJECTED = "rejected"
    UPLOADED = "uploaded"
    DOWNLOADED = "downloaded"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    PORTAL_ACCESSED = "portal_accessed"
    MATTER_CREATED = "matter_created"
    REPORT_GENERATED = "report_generated"
    ALERT_REVIEWED = "alert_reviewed"
    ARCHIVED = "archived"
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"


class AuditLog(Base):
    """Audit log for tracking all actions.

    Rows are immutable and must survive the archival of their matter —
    the matter_id FK is nullable and the Matter relationship does NOT
    cascade deletes onto this table.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    
    action = Column(SQLEnum(AuditLogAction), nullable=False)
    entity_type = Column(String(50))  # document, check, event, etc.
    entity_id = Column(Integer)
    
    description = Column(Text, nullable=False)
    details = Column(JSON)  # Additional structured data
    
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    matter = relationship("Matter", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog {self.action} - {self.entity_type}>"
