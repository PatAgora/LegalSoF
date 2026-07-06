"""
MLRO workbench models — internal suspicion reports, SAR records, DAML
timers, training records, and the AML policy repository.

Legal context (UK):
  * POCA 2002 s.330 — staff in the regulated sector have a duty to report
    knowledge/suspicion of money laundering to the firm's nominated
    officer (MLRO). Any authenticated user may therefore CREATE an
    internal report; only the MLRO may see its status or content
    thereafter.
  * POCA 2002 s.333A — tipping off. After submission, the reporting fee
    earner and the wider client team must NEVER see the report's status,
    the MLRO's notes, or whether a SAR was filed. The models below keep
    all post-submission state in MLRO-only columns; the API layer
    enforces the visibility split.
  * LSAG ch.11 (11.7) — a decision NOT to file a SAR must be documented
    as thoroughly as a decision to file. `decision_rationale` is
    mandatory for BOTH outcomes.
  * SAR filing is HUMAN-ONLY via the NCA SAR Portal. The platform
    prepares and records; `sar_reference` is the NCA-issued reference
    entered by the human after filing.
  * DAML (defence against money laundering) consent: 7 WORKING DAYS
    notice period from filing, then a 31-CALENDAR-DAY moratorium if
    consent is refused. Work on the matter must not proceed while
    awaiting DAML or during an active moratorium.
"""
from datetime import date, datetime, timedelta
from typing import Union

import enum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, Integer,
    JSON, String, Text,
)
from sqlalchemy.sql import func

from app.db.base import Base


# ---------------------------------------------------------------------------
# UK working-day calculator
# ---------------------------------------------------------------------------

def add_uk_working_days(start: Union[datetime, date], working_days: int) -> Union[datetime, date]:
    """Return the date/datetime `working_days` UK working days after `start`.

    Counting starts on the first working day AFTER `start` (the filing
    day itself is not counted), matching how the DAML notice period runs
    from the day of filing.

    NOTE: weekends-only implementation. UK bank holidays (England &
    Wales) need a data source — e.g. the gov.uk bank-holidays JSON feed
    (https://www.gov.uk/bank-holidays.json) — before this is fully
    accurate. Flagged as a follow-up; until then a deadline that spans a
    bank holiday will be computed one day early, which errs on the safe
    (conservative) side for the MLRO.
    """
    if working_days < 0:
        raise ValueError("working_days must be >= 0")
    current = start
    remaining = working_days
    while remaining > 0:
        current = current + timedelta(days=1)
        if current.weekday() < 5:  # Mon=0 .. Fri=4
            remaining -= 1
    return current


MORATORIUM_CALENDAR_DAYS = 31   # POCA 2002 s.335(6) — 31 calendar days
DAML_NOTICE_WORKING_DAYS = 7    # POCA 2002 s.335(5) — 7 working days


# ---------------------------------------------------------------------------
# Internal suspicion reports (s.330 route to the MLRO)
# ---------------------------------------------------------------------------

class InternalReportStatus(str, enum.Enum):
    """Lifecycle of an internal suspicion report. NEVER exposed to the
    reporter or the client team after submission (s.333A tipping off)."""
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    SAR_FILED = "sar_filed"
    NO_SAR_DECISION = "no_sar_decision"


class InternalReport(Base):
    """An internal report of suspicion made to the nominated officer.

    matter_id is nullable — suspicion can be client-level or arise
    outside any specific matter.
    """
    __tablename__ = "internal_reports"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    subject_summary = Column(Text)                      # who/what the suspicion concerns
    suspicion_details = Column(Text, nullable=False)    # the substance of the report

    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- MLRO-only fields below this line (s.333A: never shown to the
    # --- reporter or the client team) -----------------------------------
    status = Column(
        SQLEnum(InternalReportStatus),
        nullable=False,
        default=InternalReportStatus.RECEIVED,
    )
    mlro_notes = Column(Text)

    # LSAG 11.7 — REQUIRED for both outcomes: the decision NOT to file
    # must be documented as thoroughly as the decision to file.
    decision_rationale = Column(Text)
    decided_by_id = Column(Integer, ForeignKey("users.id"))
    decided_at = Column(DateTime(timezone=True))

    # Legal professional privilege analysis — the MLRO must consider
    # whether the information is privileged (s.330(6)/(10) defence)
    # before any external disclosure.
    privilege_considered = Column(Boolean, nullable=False, default=False)
    privilege_notes = Column(Text)

    def __repr__(self):
        return f"<InternalReport {self.id} ({self.status})>"


# ---------------------------------------------------------------------------
# SAR records — the platform PREPARES; a human FILES via the NCA SAR Portal
# ---------------------------------------------------------------------------

class DamlStatus(str, enum.Enum):
    """DAML consent state machine.

    none → (daml requested at filing) awaiting_consent
    awaiting_consent → consent_granted            (NCA consents, or the
                                                   7-working-day notice
                                                   period expires silently)
    awaiting_consent → consent_refused_moratorium (NCA refuses — the
                                                   31-calendar-day
                                                   moratorium starts)
    consent_refused_moratorium → moratorium_expired
    """
    NONE = "none"
    AWAITING_CONSENT = "awaiting_consent"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REFUSED_MORATORIUM = "consent_refused_moratorium"
    MORATORIUM_EXPIRED = "moratorium_expired"


class SarRecord(Base):
    """Record of a SAR filed by a HUMAN on the NCA SAR Portal.

    The platform never submits to the NCA. `sar_reference` is the
    NCA-issued reference the MLRO enters after filing on the portal.
    """
    __tablename__ = "sar_records"

    id = Column(Integer, primary_key=True, index=True)
    internal_report_id = Column(
        Integer, ForeignKey("internal_reports.id"), nullable=False, index=True
    )

    sar_reference = Column(String(100))     # NCA-issued reference (post-portal-filing)
    filed_at = Column(DateTime(timezone=True))
    filed_by_id = Column(Integer, ForeignKey("users.id"))

    daml_requested = Column(Boolean, nullable=False, default=False)
    daml_filed_at = Column(DateTime(timezone=True))
    daml_status = Column(SQLEnum(DamlStatus), nullable=False, default=DamlStatus.NONE)

    # 7 working days from daml_filed_at (see add_uk_working_days above —
    # weekends-only; bank holidays are a noted follow-up).
    consent_deadline = Column(DateTime(timezone=True))
    # 31 calendar days from the refusal that started the moratorium.
    moratorium_end = Column(DateTime(timezone=True))

    notes = Column(Text)

    def __repr__(self):
        return f"<SarRecord {self.id} report={self.internal_report_id} daml={self.daml_status}>"


# ---------------------------------------------------------------------------
# AML training records
# ---------------------------------------------------------------------------

class TrainingRecord(Base):
    """AML training completed by a member of staff (MLR 2017 reg 24)."""
    __tablename__ = "training_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    course_name = Column(String(255), nullable=False)
    provider = Column(String(255))
    completed_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    certificate_note = Column(Text)   # certificate ref / storage location

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<TrainingRecord {self.id} user={self.user_id} {self.course_name!r}>"


# ---------------------------------------------------------------------------
# Policy repository
# ---------------------------------------------------------------------------

class PolicyStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class PolicyDocument(Base):
    """A versioned firm AML policy/procedure (MLR 2017 reg 19).

    Firms often keep the document itself elsewhere (DMS/intranet);
    `content_note` holds a summary and/or its location.
    `acknowledgements` is a JSON list of {user_id, acknowledged_at}.
    """
    __tablename__ = "policy_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    status = Column(SQLEnum(PolicyStatus), nullable=False, default=PolicyStatus.DRAFT)

    content_note = Column(Text)

    approved_by_id = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime(timezone=True))
    review_due = Column(DateTime(timezone=True))

    acknowledgements = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<PolicyDocument {self.title!r} v{self.version} ({self.status})>"
