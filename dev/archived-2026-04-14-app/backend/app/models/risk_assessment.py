"""
Risk assessment models.

Two regimes, two tables:

  * FirmRiskAssessment — the firm-wide risk assessment required by
    MLR 2017 reg 18 (plus reg 18A proliferation financing). Written,
    versioned, approved, and kept up to date. Each version carries one
    section per mandatory risk-factor set (customers, geography,
    products/services, transactions, delivery channels, proliferation
    financing), each with a risk level, REASONED narrative, and
    mitigations. The SRA penalises unreasoned template assessments, so
    reasoning is mandatory (>= 50 chars) before approval.

  * ClientMatterRiskAssessment — the written client AND matter level
    risk assessments required by MLR 2017 reg 28(12)-(13) and the SRA
    warning notice (51% of firm assessments were found ineffective;
    tick-box approaches are penalised). Five LSAG factor sets scored
    1-3 with mandatory reasoning, plus the reg 28(13) mandatory
    considerations (purpose, size, regularity/duration).
"""
import enum

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Boolean, Text, JSON,
    ForeignKey, Enum as SQLEnum, Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FirmRAStatus(str, enum.Enum):
    """Lifecycle of a firm-wide risk assessment version."""
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class CMRAStatus(str, enum.Enum):
    """Lifecycle of a client/matter risk assessment."""
    DRAFT = "draft"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"


class CMRAType(str, enum.Enum):
    """Reg 28(12) requires BOTH a client-level and a matter-level
    written assessment — modelled as two rows of different types."""
    CLIENT = "client"
    MATTER = "matter"


class RiskLevel(str, enum.Enum):
    """Low / medium / high — used for FWRA section levels and the CMRA
    overall rating."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# The six mandatory FWRA factor sections. Five from reg 18(2)(a) plus
# proliferation financing from reg 18A.
FWRA_SECTIONS = (
    "customers",
    "geography",
    "products_services",
    "transactions",
    "delivery_channels",
    "proliferation_financing",
)

# The five LSAG factor sets scored on every client/matter assessment.
CMRA_FACTORS = (
    "client",
    "service_matter",
    "geography",
    "delivery_channel",
    "sector_product",
)

# The mandatory reg 28(13) considerations — all three must be addressed
# in writing before a CMRA can be completed.
REG28_CONSIDERATIONS = (
    "purpose_of_matter",
    "size_of_transaction",
    "regularity_duration",
)


# ---------------------------------------------------------------------------
# Firm-Wide Risk Assessment (MLR 2017 reg 18 / 18A)
# ---------------------------------------------------------------------------

class FirmRiskAssessment(Base):
    """A version of the firm-wide risk assessment.

    Exactly one version may be APPROVED at a time (the "current" FWRA);
    approving a new version supersedes the previous approved one. All
    versions are retained for the audit trail.
    """
    __tablename__ = "firm_risk_assessments"

    id = Column(Integer, primary_key=True, index=True)
    # Monotonic per-firm version number (single-tenant platform — the
    # sequence is global). Assigned on creation as max(version) + 1.
    version = Column(Integer, nullable=False, index=True)
    status = Column(SQLEnum(FirmRAStatus), nullable=False, default=FirmRAStatus.DRAFT, index=True)

    # {section_key: {"risk_level": "low|medium|high",
    #                "reasoning": str,      # REQUIRED >= 50 chars at approval
    #                "mitigations": str}}
    # One entry per FWRA_SECTIONS key.
    sections = Column(JSON, nullable=False, default=dict)

    # Reg 18(6): the firm must take account of the supervisor's sectoral
    # risk assessment (SRA) and the national risk assessment (NRA).
    # Approval is blocked until both are acknowledged WITH a date.
    sectoral_ra_acknowledged = Column(Boolean, nullable=False, default=False)
    sectoral_ra_date = Column(Date, nullable=True)
    nra_acknowledged = Column(Boolean, nullable=False, default=False)
    nra_date = Column(Date, nullable=True)

    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Reg 18(4): keep the assessment up to date — default review cycle
    # is 12 months from approval. Past this date the GET response
    # carries a review_overdue warning.
    next_review_due = Column(Date, nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    approved_by = relationship("User", foreign_keys=[approved_by_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "version": self.version,
            "status": self.status.value if self.status else None,
            "sections": self.sections or {},
            "sectoral_ra_acknowledged": bool(self.sectoral_ra_acknowledged),
            "sectoral_ra_date": self.sectoral_ra_date.isoformat() if self.sectoral_ra_date else None,
            "nra_acknowledged": bool(self.nra_acknowledged),
            "nra_date": self.nra_date.isoformat() if self.nra_date else None,
            "approved_by_id": self.approved_by_id,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "next_review_due": self.next_review_due.isoformat() if self.next_review_due else None,
            "created_by_id": self.created_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<FirmRiskAssessment v{self.version} {self.status}>"


# ---------------------------------------------------------------------------
# Client & Matter Risk Assessment (MLR 2017 reg 28(12)-(13))
# ---------------------------------------------------------------------------

class ClientMatterRiskAssessment(Base):
    """A written client-level or matter-level risk assessment.

    One matter carries up to one CURRENT (completed) assessment of each
    type; completing a new assessment of a type supersedes the previous
    completed one of that type. Draft rows may be edited freely.
    """
    __tablename__ = "client_matter_risk_assessments"
    __table_args__ = (
        Index("ix_cmra_matter_type_status", "matter_id", "assessment_type", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)
    assessment_type = Column(SQLEnum(CMRAType), nullable=False)

    # {factor_key: {"score": 1|2|3, "reasoning": str}} — one entry per
    # CMRA_FACTORS key. Reasoning is mandatory on completion: a bare
    # score with no narrative is exactly the tick-box approach the SRA
    # warning notice penalises.
    factors = Column(JSON, nullable=False, default=dict)

    # {"purpose_of_matter": str, "size_of_transaction": str,
    #  "regularity_duration": str} — the reg 28(13) mandatory items,
    # all required at completion.
    reg28_considerations = Column(JSON, nullable=False, default=dict)

    # Structured context used by the scoring engine so a recompute on
    # edit stays consistent: {"client_is_pep": bool,
    # "geography_countries": ["GB", ...], "unusual_complexity": bool}.
    context_flags = Column(JSON, nullable=False, default=dict)

    # Derived server-side — never trusted from the client.
    overall_rating = Column(SQLEnum(RiskLevel), nullable=True)
    edd_required = Column(Boolean, nullable=False, default=False)
    edd_triggers = Column(JSON, nullable=False, default=list)  # list[str]

    status = Column(SQLEnum(CMRAStatus), nullable=False, default=CMRAStatus.DRAFT, index=True)
    completed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # Set at completion from the overall rating: high = 6 months,
    # medium = 12 months, low = 24 months.
    review_due = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    matter = relationship("Matter", foreign_keys=[matter_id])
    completed_by = relationship("User", foreign_keys=[completed_by_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "matter_id": self.matter_id,
            "assessment_type": self.assessment_type.value if self.assessment_type else None,
            "factors": self.factors or {},
            "reg28_considerations": self.reg28_considerations or {},
            "context_flags": self.context_flags or {},
            "overall_rating": self.overall_rating.value if self.overall_rating else None,
            "edd_required": bool(self.edd_required),
            "edd_triggers": self.edd_triggers or [],
            "status": self.status.value if self.status else None,
            "completed_by_id": self.completed_by_id,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "review_due": self.review_due.isoformat() if self.review_due else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<ClientMatterRiskAssessment {self.assessment_type} matter={self.matter_id} {self.status}>"
