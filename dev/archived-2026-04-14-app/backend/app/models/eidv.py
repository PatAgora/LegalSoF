"""
E-IDV (Electronic Identity Verification) models.

Each row is one identity verification of one natural person (the
client, a beneficial owner, or a giftor) on a matter, performed via a
pluggable provider (see app/services/eidv_providers.py).

diatf_certified: HM Treasury guidance (Feb 2026) — only digital
identity services certified under the UK Digital Identity and
Attributes Trust Framework satisfy MLR 2017 reg 28(19) automatically.
Manual (traditional) verification is always diatf_certified=False.

String-valued fields (no PostgreSQL enum types):
    subject_type: client | beneficial_owner | giftor
    provider:     manual | complycube
    status:       pending | passed | failed | review
"""
import enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class EidvSubjectType(str, enum.Enum):
    CLIENT = "client"
    BENEFICIAL_OWNER = "beneficial_owner"
    GIFTOR = "giftor"


class EidvStatus(str, enum.Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    REVIEW = "review"


class EidvCheck(Base):
    """One identity verification of one person on a matter."""

    __tablename__ = "eidv_checks"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)

    subject_type = Column(String(30), nullable=False)  # client | beneficial_owner | giftor
    subject_name = Column(String(255), nullable=False)
    subject_dob = Column(String(10), nullable=True)  # ISO date string YYYY-MM-DD
    subject_email = Column(String(255), nullable=True)

    provider = Column(String(30), nullable=False, default="manual")  # manual | complycube
    provider_ref = Column(String(255), nullable=True, index=True)
    method = Column(String(30), nullable=True)  # manual | electronic

    status = Column(String(20), nullable=False, default=EidvStatus.PENDING.value)

    # HMT Feb 2026: only DIATF-certified services satisfy reg 28(19)
    # automatically. Always False for manual verification.
    diatf_certified = Column(Boolean, nullable=False, default=False)

    # Per-check outcomes: {document, liveness, nfc_chip, address}
    checks = Column(JSON)
    evidence_notes = Column(Text)

    completed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # One-way relationships (Matter/User owned elsewhere — no back_populates).
    matter = relationship("Matter", foreign_keys=[matter_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    completed_by = relationship("User", foreign_keys=[completed_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "matter_id": self.matter_id,
            "subject_type": self.subject_type,
            "subject_name": self.subject_name,
            "subject_dob": self.subject_dob,
            "subject_email": self.subject_email,
            "provider": self.provider,
            "provider_ref": self.provider_ref,
            "method": self.method,
            "status": self.status,
            "diatf_certified": self.diatf_certified,
            "checks": self.checks,
            "evidence_notes": self.evidence_notes,
            "completed_by_id": self.completed_by_id,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<EidvCheck {self.subject_name} ({self.subject_type}) on Matter {self.matter_id} ({self.status})>"
