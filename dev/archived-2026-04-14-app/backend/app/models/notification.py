"""
Notification model - stores user-facing notifications for the platform.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Notification(Base):
    """User notification for status changes, assessment completions, alerts, etc."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=True)
    type = Column(String(50), nullable=False)  # e.g. "assessment_complete", "status_change", "high_risk_alert"
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="notifications")
    matter = relationship("Matter")

    def __repr__(self):
        return f"<Notification {self.id} type={self.type} user={self.user_id}>"
