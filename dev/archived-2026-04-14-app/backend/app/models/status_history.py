"""
MatterStatusHistory model - tracks all status transitions for audit purposes.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class MatterStatusHistory(Base):
    """Records every status change on a matter with who, when, from/to, and reason."""
    __tablename__ = "matter_status_history"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)
    old_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    matter = relationship("Matter", back_populates="status_history")
    user = relationship("User")

    def __repr__(self):
        return f"<MatterStatusHistory {self.old_status} -> {self.new_status} on Matter {self.matter_id}>"
