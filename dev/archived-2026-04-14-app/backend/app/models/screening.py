"""
PEP / sanctions screening models.

Sanctions screening is a STRICT-LIABILITY regime under the Sanctions and
Anti-Money Laundering Act 2018 — it is separate from risk-based AML, so
every party is screened regardless of the matter's risk rating.

Tables:
- sanctions_datasets  — one row per imported UK Sanctions List publication.
- sanctions_entries   — the designations from the current dataset.
- screening_checks    — one row per screening run against a subject.
- screening_hits      — candidate matches for a check, individually
                        adjudicated (true match / false positive) with a
                        mandatory rationale. Rows survive re-screens so the
                        remediation decision trail is preserved.
"""
import enum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum as SQLEnum, ForeignKey, Integer,
    JSON, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


# ---------------------------------------------------------------------------
# Sanctions list data (UK Sanctions List, FCDO)
# ---------------------------------------------------------------------------

class SanctionsDataset(Base):
    """A single imported publication of the UK Sanctions List."""
    __tablename__ = "sanctions_datasets"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, default="uk_fcdo")
    # Version string — the list's DateGenerated (DD/MM/YYYY) as published.
    version = Column(String(50), nullable=False)
    date_generated = Column(Date, nullable=True)
    entry_count = Column(Integer, nullable=False, default=0)
    source_url = Column(String(500))
    imported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    entries = relationship(
        "SanctionsEntry", back_populates="dataset", cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<SanctionsDataset {self.source} v{self.version} ({self.entry_count} entries)>"


class SanctionsEntry(Base):
    """A single designation from the UK Sanctions List."""
    __tablename__ = "sanctions_entries"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(
        Integer, ForeignKey("sanctions_datasets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source = Column(String(50), nullable=False, default="uk_fcdo")
    # FCDO UniqueID, e.g. "AFG0001".
    external_id = Column(String(50), nullable=False, index=True)
    # individual | entity | ship
    entity_type = Column(String(20), nullable=False, index=True)
    primary_name = Column(String(500), nullable=False, index=True)
    aliases = Column(JSON, default=list)          # list[str]
    # First listed DOB (as published, may contain dd/mm placeholders);
    # all DOBs are kept in raw["dobs"].
    dob = Column(String(50))
    nationalities = Column(JSON, default=list)    # list[str]
    regimes = Column(JSON, default=list)          # list[str]
    listed_on = Column(Date)
    raw = Column(JSON, default=dict)
    imported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dataset = relationship("SanctionsDataset", back_populates="entries")

    def __repr__(self):
        return f"<SanctionsEntry {self.external_id}: {self.primary_name}>"


# ---------------------------------------------------------------------------
# Screening checks & hits
# ---------------------------------------------------------------------------

class ScreeningSubjectType(str, enum.Enum):
    CLIENT = "client"
    BENEFICIAL_OWNER = "beneficial_owner"
    COUNTERPARTY = "counterparty"
    GIFTOR = "giftor"


class ScreeningCheckStatus(str, enum.Enum):
    CLEAR = "clear"
    POTENTIAL_MATCH = "potential_match"
    CONFIRMED_MATCH = "confirmed_match"
    FALSE_POSITIVE = "false_positive"


class HitAdjudicationStatus(str, enum.Enum):
    PENDING = "pending"
    TRUE_MATCH = "true_match"
    FALSE_POSITIVE = "false_positive"


class ScreeningCheck(Base):
    """One screening run of a subject against the active providers."""
    __tablename__ = "screening_checks"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)

    subject_type = Column(SQLEnum(ScreeningSubjectType), nullable=False)
    subject_name = Column(String(255), nullable=False)
    subject_dob = Column(Date)

    status = Column(
        SQLEnum(ScreeningCheckStatus), nullable=False,
        default=ScreeningCheckStatus.CLEAR,
    )
    # Set when any hit is adjudicated a true match — a sanctions freeze
    # situation requiring MLRO escalation and consideration of OFSI reporting.
    requires_escalation = Column(Boolean, nullable=False, default=False)

    dataset_version = Column(String(50))
    providers_used = Column(JSON, default=list)   # list[str]

    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    matter = relationship("Matter")
    created_by = relationship("User", foreign_keys=[created_by_id])
    hits = relationship(
        "ScreeningHit", back_populates="check", cascade="all, delete-orphan",
        order_by="ScreeningHit.score.desc()",
    )

    def __repr__(self):
        return f"<ScreeningCheck {self.id} matter={self.matter_id} {self.subject_name!r} {self.status}>"


class ScreeningHit(Base):
    """A candidate match returned by a provider, awaiting adjudication."""
    __tablename__ = "screening_hits"

    id = Column(Integer, primary_key=True, index=True)
    check_id = Column(
        Integer, ForeignKey("screening_checks.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    source = Column(String(50), nullable=False)          # e.g. uk_fcdo, dilisense
    category = Column(String(30), nullable=False)        # sanctions | pep | adverse_media
    matched_name = Column(String(500), nullable=False)
    external_ref = Column(String(100))                   # provider's ref (FCDO UniqueID etc.)
    score = Column(Integer, nullable=False, default=0)   # 0-100
    raw = Column(JSON, default=dict)

    adjudication_status = Column(
        SQLEnum(HitAdjudicationStatus), nullable=False,
        default=HitAdjudicationStatus.PENDING,
    )
    adjudicated_by_id = Column(Integer, ForeignKey("users.id"))
    adjudication_rationale = Column(Text)
    adjudicated_at = Column(DateTime(timezone=True))

    check = relationship("ScreeningCheck", back_populates="hits")
    adjudicated_by = relationship("User", foreign_keys=[adjudicated_by_id])

    def __repr__(self):
        return f"<ScreeningHit {self.id} {self.matched_name!r} score={self.score} {self.adjudication_status}>"
