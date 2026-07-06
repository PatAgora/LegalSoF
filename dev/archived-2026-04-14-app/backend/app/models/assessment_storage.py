"""
AssessmentStorage model — persists SoF assessment data in PostgreSQL
instead of /tmp JSON files. Supports multi-worker / multi-process deployments.
"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from app.db.base import Base


class AssessmentStorage(Base):
    __tablename__ = "assessment_storage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), unique=True, nullable=False, index=True)
    data = Column(JSON, nullable=False)  # stores the full assessment dict
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
