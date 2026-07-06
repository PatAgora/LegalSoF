"""
KYB (Know Your Business) models — company due diligence checks
performed against the Companies House Public Data API.

Statuses are plain strings (matching the Matter.compliance_status
pattern) so no PostgreSQL enum types are needed:
    pending | complete | discrepancy_reported

reg 30A (MLR 2017): firms MUST report material discrepancies between
their CDD findings and the Companies House PSC register. The
psc_discrepancy column records what was found and that the firm
reported it — the platform records, a human makes the report.
"""
import enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class KybCheckStatus(str, enum.Enum):
    """Lifecycle of a KYB check (stored as plain strings)."""

    PENDING = "pending"
    COMPLETE = "complete"
    DISCREPANCY_REPORTED = "discrepancy_reported"


class KybCheck(Base):
    """A Companies House due-diligence snapshot for a company on a matter."""

    __tablename__ = "kyb_checks"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)

    company_number = Column(String(20), nullable=False, index=True)
    company_name = Column(String(255))

    status = Column(String(30), nullable=False, default=KybCheckStatus.PENDING.value)

    # Trimmed snapshots of the Companies House responses (see
    # app/services/companies_house.py summarise_* helpers).
    profile = Column(JSON)
    officers = Column(JSON)
    pscs = Column(JSON)

    # Analyst commentary on the ownership/control structure.
    ownership_notes = Column(Text)

    # reg 30A: material PSC discrepancy — what was found, and the
    # firm's confirmation that it reported the discrepancy to
    # Companies House. NULL = no discrepancy recorded.
    psc_discrepancy = Column(Text, nullable=True)
    psc_discrepancy_reported_at = Column(DateTime(timezone=True), nullable=True)
    psc_discrepancy_reported_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    refreshed_at = Column(DateTime(timezone=True), nullable=True)

    # One-way relationships (Matter/User are owned elsewhere and are
    # not modified — no back_populates).
    matter = relationship("Matter", foreign_keys=[matter_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "matter_id": self.matter_id,
            "company_number": self.company_number,
            "company_name": self.company_name,
            "status": self.status,
            "profile": self.profile,
            "officers": self.officers,
            "pscs": self.pscs,
            "ownership_notes": self.ownership_notes,
            "psc_discrepancy": self.psc_discrepancy,
            "psc_discrepancy_reported_at": (
                self.psc_discrepancy_reported_at.isoformat()
                if self.psc_discrepancy_reported_at
                else None
            ),
            "created_by_id": self.created_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "refreshed_at": self.refreshed_at.isoformat() if self.refreshed_at else None,
        }

    def __repr__(self):
        return f"<KybCheck {self.company_number} on Matter {self.matter_id} ({self.status})>"
