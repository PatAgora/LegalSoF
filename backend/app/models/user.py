"""
User model for authentication and authorization.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class UserRole(str, enum.Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    PARTNER = "partner"
    ANALYST = "analyst"


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.ANALYST)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    matters_assigned = relationship("Matter", back_populates="assigned_analyst", foreign_keys="Matter.assigned_analyst_id")
    matters_created = relationship("Matter", back_populates="created_by_user", foreign_keys="Matter.created_by_id")
    audit_logs = relationship("AuditLog", back_populates="user")
    notes = relationship("Note", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
