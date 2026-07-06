"""
MLRO Workbench API Endpoints

Internal suspicion reports (POCA 2002 s.330), SAR preparation/recording
(human-only filing via the NCA SAR Portal), DAML consent timers, AML
training records, and the policy repository.

ACCESS CONTROL MODEL — the critical part:

  * ANY authenticated user may CREATE an internal report (s.330 duty to
    report suspicion to the nominated officer).
  * ONLY the admin role may list/read/update reports, record decisions,
    and manage SARs. Admin stands in for the MLRO here — a dedicated
    MLRO role (nominated officer + deputies) is a follow-up.
  * A reporter may see only "you submitted a report on <date>" via
    GET /mlro/my-reports — NO status, NO MLRO notes, NO outcome. This is
    a tipping-off control (POCA 2002 s.333A): the client team must never
    learn whether a SAR was or was not filed.
  * Audit entries for internal reports are deliberately NOT linked to
    the matter's audit trail (matter_id is left NULL on the AuditLog
    row) — the matter audit trail is visible to the client team, and a
    "suspicion report created" line against the matter would tip off.

Every material action is audited with the actor taken from
current_user — never client-supplied.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.dependencies.auth import get_current_active_user, require_admin
from app.db.session import get_sync_db
from app.models.audit import AuditLog, AuditLogAction
from app.models.matter import Matter
from app.models.mlro import (
    DAML_NOTICE_WORKING_DAYS,
    MORATORIUM_CALENDAR_DAYS,
    DamlStatus,
    InternalReport,
    InternalReportStatus,
    PolicyDocument,
    PolicyStatus,
    SarRecord,
    TrainingRecord,
    add_uk_working_days,
)
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    db: Session,
    user: User,
    action: AuditLogAction,
    entity_type: str,
    entity_id: Optional[int],
    description: str,
    details: Optional[dict] = None,
    matter_id: Optional[int] = None,
) -> None:
    """Write an AuditLog row. Actor comes from current_user, NEVER from
    the request body.

    For internal-report entities, callers must leave matter_id=None so
    the entry never surfaces in the (client-team-visible) matter audit
    trail — s.333A tipping-off control.
    """
    db.add(AuditLog(
        matter_id=matter_id,
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        details=details,
    ))


def _matter_ref(db: Session, matter_id: Optional[int]) -> Optional[str]:
    if not matter_id:
        return None
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    return matter.reference_number if matter else None


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    return u.full_name if u else None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Treat naive datetimes from the DB as UTC so comparisons work."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _gather_firm_context(db: Session, matter_id: int) -> dict:
    """Pull the firm-held information the MLRO must weigh the report
    against (MLR 2017 reg 21(5): the nominated officer considers an
    internal report in the light of ALL relevant information held by
    the firm).

    Screening / risk / KYB modules are being built concurrently by
    other teams, so their models are imported DEFENSIVELY — if a module
    does not exist yet the section is simply omitted.
    """
    context: dict = {}

    # Existing modules (present in this codebase today) — still guarded
    # so a refactor elsewhere cannot break the MLRO view.
    try:
        from app.models.check import Check
        checks = db.query(Check).filter(Check.matter_id == matter_id).all()
        context["checks"] = [
            {
                "id": c.id,
                "check_type": getattr(getattr(c, "check_type", None), "value", None),
                "status": getattr(getattr(c, "status", None), "value", None),
                "severity": getattr(getattr(c, "severity", None), "value", None),
                "title": getattr(c, "title", None),
            }
            for c in checks
        ]
    except Exception:
        pass

    try:
        from app.models.document_verification import DocumentVerification
        verifications = (
            db.query(DocumentVerification)
            .filter(DocumentVerification.matter_id == matter_id)
            .all()
        )
        context["document_verifications"] = [
            {
                "id": v.id,
                "verdict": getattr(getattr(v, "verdict", None), "value", None)
                or getattr(v, "verdict", None),
                "created_at": _iso(getattr(v, "created_at", None)),
            }
            for v in verifications
        ]
    except Exception:
        pass

    # Concurrently-built modules — may not exist yet.
    try:
        from app.models.screening import ScreeningCheck  # type: ignore
        rows = db.query(ScreeningCheck).filter(
            ScreeningCheck.matter_id == matter_id
        ).all()
        context["screening_checks"] = [
            {"id": r.id, "status": str(getattr(r, "status", None)),
             "result": str(getattr(r, "result", None))}
            for r in rows
        ]
    except ImportError:
        pass
    except Exception:
        pass

    try:
        from app.models.risk import RiskAssessment  # type: ignore
        rows = db.query(RiskAssessment).filter(
            RiskAssessment.matter_id == matter_id
        ).all()
        context["risk_assessments"] = [
            {"id": r.id, "rating": str(getattr(r, "rating", None)),
             "assessed_at": _iso(getattr(r, "assessed_at", None))}
            for r in rows
        ]
    except ImportError:
        pass
    except Exception:
        pass

    return context


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InternalReportCreate(BaseModel):
    matter_id: Optional[int] = None
    subject_summary: str = Field(..., min_length=3, max_length=2000)
    suspicion_details: str = Field(..., min_length=10)


class ReportDecision(BaseModel):
    outcome: str = Field(..., pattern="^(sar|no_sar)$")
    # LSAG 11.7 — the decision NOT to file must be documented as
    # thoroughly as the decision to file: rationale required BOTH ways.
    rationale: str = Field(..., min_length=30)
    privilege_considered: bool = False
    privilege_notes: Optional[str] = None
    mlro_notes: Optional[str] = None


class SarCreate(BaseModel):
    # The NCA-issued reference, entered by the HUMAN who filed on the
    # NCA SAR Portal. The platform never submits to the NCA itself.
    sar_reference: str = Field(..., min_length=3, max_length=100)
    daml_requested: bool = False
    notes: Optional[str] = None


class DamlOutcome(BaseModel):
    status: str = Field(
        ...,
        pattern="^(consent_granted|consent_refused_moratorium|moratorium_expired)$",
    )
    notes: Optional[str] = None


class TrainingCreate(BaseModel):
    user_id: int
    course_name: str = Field(..., min_length=2, max_length=255)
    provider: Optional[str] = Field(None, max_length=255)
    completed_at: datetime
    expires_at: Optional[datetime] = None
    certificate_note: Optional[str] = None


class TrainingUpdate(BaseModel):
    course_name: Optional[str] = Field(None, min_length=2, max_length=255)
    provider: Optional[str] = Field(None, max_length=255)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    certificate_note: Optional[str] = None


class PolicyCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    version: str = Field(..., min_length=1, max_length=50)
    content_note: Optional[str] = None
    review_due: Optional[datetime] = None


class PolicyUpdate(BaseModel):
    content_note: Optional[str] = None
    review_due: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Internal reports — CREATE is open to ANY authenticated user (s.330)
# ---------------------------------------------------------------------------

@router.post("/mlro/internal-reports", tags=["mlro"], status_code=201)
def create_internal_report(
    payload: InternalReportCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_sync_db),
):
    """File an internal suspicion report with the nominated officer.

    Open to ANY authenticated user — POCA 2002 s.330 places the duty to
    report on every member of staff, so no role or matter-assignment
    gate may block it.

    The response confirms RECEIPT ONLY. It carries no status and never
    will — after this point the reporter must not learn what the MLRO
    does with the report (s.333A tipping off).
    """
    if payload.matter_id is not None:
        matter = db.query(Matter).filter(Matter.id == payload.matter_id).first()
        if not matter:
            raise HTTPException(status_code=404, detail="Matter not found")

    report = InternalReport(
        matter_id=payload.matter_id,
        reporter_id=current_user.id,   # actor from token, never the body
        subject_summary=payload.subject_summary,
        suspicion_details=payload.suspicion_details,
        status=InternalReportStatus.RECEIVED,
        submitted_at=_now(),
    )
    db.add(report)
    db.flush()

    # matter_id deliberately NOT set on the audit row — the matter audit
    # trail is visible to the client team and must not reveal that an
    # internal report exists (s.333A).
    _audit(
        db, current_user, AuditLogAction.CREATED,
        "internal_report", report.id,
        "Internal suspicion report submitted to the nominated officer",
    )
    db.commit()

    return {
        "id": report.id,
        "submitted_at": _iso(report.submitted_at),
        "message": (
            "Your report has been received by the nominated officer (MLRO). "
            "You will not be updated on its progress. Do not discuss this "
            "report with the client or colleagues."
        ),
    }


@router.get("/mlro/my-reports", tags=["mlro"])
def list_my_reports(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_sync_db),
):
    """The reporter's own submissions — receipt info ONLY.

    Returns id, submission date and matter reference. Deliberately NO
    status, NO outcome, NO MLRO notes: revealing that a SAR was (or was
    not) filed to the client team is the s.333A tipping-off offence.
    """
    reports = (
        db.query(InternalReport)
        .filter(InternalReport.reporter_id == current_user.id)
        .order_by(InternalReport.submitted_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "submitted_at": _iso(r.submitted_at),
            "matter_id": r.matter_id,
            "matter_reference": _matter_ref(db, r.matter_id),
            "subject_summary": r.subject_summary,
        }
        for r in reports
    ]


# ---------------------------------------------------------------------------
# Internal reports — MLRO (admin) only from here down
# ---------------------------------------------------------------------------

def _report_summary(db: Session, r: InternalReport) -> dict:
    return {
        "id": r.id,
        "matter_id": r.matter_id,
        "matter_reference": _matter_ref(db, r.matter_id),
        "reporter_name": _user_name(db, r.reporter_id),
        "subject_summary": r.subject_summary,
        "status": r.status.value if r.status else None,
        "submitted_at": _iso(r.submitted_at),
        "decided_at": _iso(r.decided_at),
        "privilege_considered": bool(r.privilege_considered),
    }


@router.get("/mlro/reports", tags=["mlro"])
def list_reports(
    status: Optional[str] = None,
    matter_id: Optional[int] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """MLRO queue of internal reports. Admin (MLRO) only."""
    q = db.query(InternalReport)
    if status:
        try:
            q = q.filter(InternalReport.status == InternalReportStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown status '{status}'")
    if matter_id is not None:
        q = q.filter(InternalReport.matter_id == matter_id)
    reports = q.order_by(InternalReport.submitted_at.desc()).all()
    return [_report_summary(db, r) for r in reports]


@router.get("/mlro/reports/{report_id}", tags=["mlro"])
def get_report(
    report_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Full report detail plus the firm-held context for the matter
    (reg 21(5): the MLRO weighs the report against ALL information held
    by the firm). Admin (MLRO) only.

    Opening a freshly received report moves it to under_review so the
    queue reflects that the MLRO has picked it up.
    """
    r = db.query(InternalReport).filter(InternalReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")

    if r.status == InternalReportStatus.RECEIVED:
        r.status = InternalReportStatus.UNDER_REVIEW
        _audit(
            db, current_user, AuditLogAction.STATUS_CHANGED,
            "internal_report", r.id,
            "Internal report opened by MLRO — status moved to under_review",
        )
        db.commit()

    sars = (
        db.query(SarRecord)
        .filter(SarRecord.internal_report_id == r.id)
        .order_by(SarRecord.id.asc())
        .all()
    )

    detail = _report_summary(db, r)
    detail.update({
        "suspicion_details": r.suspicion_details,
        "mlro_notes": r.mlro_notes,
        "decision_rationale": r.decision_rationale,
        "decided_by_name": _user_name(db, r.decided_by_id),
        "privilege_notes": r.privilege_notes,
        "sars": [_sar_dict(db, s) for s in sars],
        "matter_context": (
            _gather_firm_context(db, r.matter_id) if r.matter_id else {}
        ),
    })
    return detail


@router.post("/mlro/reports/{report_id}/decide", tags=["mlro"])
def decide_report(
    report_id: int,
    payload: ReportDecision,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Record the MLRO's decision on an internal report. Admin only.

    LSAG 11.7: rationale (>= 30 chars) is REQUIRED for both outcomes —
    the decision NOT to file must be documented as thoroughly as the
    decision to file.

      outcome = "no_sar" → status becomes no_sar_decision (terminal).
      outcome = "sar"    → the decision is recorded but status stays
                           under_review until the HUMAN files on the
                           NCA SAR Portal and records it via
                           POST /mlro/reports/{id}/sar.
    """
    r = db.query(InternalReport).filter(InternalReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    if r.status in (InternalReportStatus.SAR_FILED, InternalReportStatus.NO_SAR_DECISION):
        raise HTTPException(status_code=400, detail="Report has already been decided")

    rationale = payload.rationale.strip()
    if len(rationale) < 30:
        raise HTTPException(
            status_code=400,
            detail="Decision rationale must be at least 30 characters (LSAG 11.7)",
        )

    r.decision_rationale = rationale
    r.decided_by_id = current_user.id
    r.decided_at = _now()
    r.privilege_considered = payload.privilege_considered
    if payload.privilege_notes is not None:
        r.privilege_notes = payload.privilege_notes
    if payload.mlro_notes is not None:
        r.mlro_notes = payload.mlro_notes

    if payload.outcome == "no_sar":
        r.status = InternalReportStatus.NO_SAR_DECISION
        description = "MLRO decision: no SAR to be filed (rationale recorded, LSAG 11.7)"
    else:
        # Status flips to sar_filed only when the human filing is recorded.
        r.status = InternalReportStatus.UNDER_REVIEW
        description = "MLRO decision: SAR to be filed via the NCA SAR Portal"

    _audit(
        db, current_user, AuditLogAction.UPDATED,
        "internal_report", r.id, description,
        details={"outcome": payload.outcome},
    )
    db.commit()
    return {"id": r.id, "status": r.status.value, "decided_at": _iso(r.decided_at)}


# ---------------------------------------------------------------------------
# SAR records & DAML
# ---------------------------------------------------------------------------

def _sar_dict(db: Session, s: SarRecord) -> dict:
    return {
        "id": s.id,
        "internal_report_id": s.internal_report_id,
        "sar_reference": s.sar_reference,
        "filed_at": _iso(s.filed_at),
        "filed_by_name": _user_name(db, s.filed_by_id),
        "daml_requested": bool(s.daml_requested),
        "daml_filed_at": _iso(s.daml_filed_at),
        "daml_status": s.daml_status.value if s.daml_status else None,
        "consent_deadline": _iso(s.consent_deadline),
        "moratorium_end": _iso(s.moratorium_end),
        "notes": s.notes,
    }


@router.post("/mlro/reports/{report_id}/sar", tags=["mlro"], status_code=201)
def record_sar_filing(
    report_id: int,
    payload: SarCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Record that a SAR has been FILED BY A HUMAN on the NCA SAR Portal.

    The platform prepares and records — it does not and must not submit
    to the NCA. `sar_reference` is the NCA-issued reference. Requires a
    prior recorded decision to file (POST .../decide with outcome=sar).

    If DAML consent was requested, the 7-working-day notice clock starts
    now (weekends-only calculator; bank holidays are a noted follow-up).
    """
    r = db.query(InternalReport).filter(InternalReport.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    if r.status == InternalReportStatus.NO_SAR_DECISION:
        raise HTTPException(
            status_code=400, detail="This report was decided as no-SAR"
        )
    if not r.decision_rationale or not r.decided_at:
        raise HTTPException(
            status_code=400,
            detail="Record the MLRO decision (with rationale) before recording a SAR filing",
        )

    now = _now()
    sar = SarRecord(
        internal_report_id=r.id,
        sar_reference=payload.sar_reference.strip(),
        filed_at=now,
        filed_by_id=current_user.id,
        daml_requested=payload.daml_requested,
        notes=payload.notes,
    )
    if payload.daml_requested:
        sar.daml_filed_at = now
        sar.daml_status = DamlStatus.AWAITING_CONSENT
        sar.consent_deadline = add_uk_working_days(now, DAML_NOTICE_WORKING_DAYS)
    else:
        sar.daml_status = DamlStatus.NONE

    r.status = InternalReportStatus.SAR_FILED
    db.add(sar)
    db.flush()

    _audit(
        db, current_user, AuditLogAction.CREATED,
        "sar_record", sar.id,
        f"SAR filing recorded (NCA ref {sar.sar_reference}); "
        + ("DAML consent requested — matter work frozen pending consent"
           if payload.daml_requested else "no DAML requested"),
        details={"internal_report_id": r.id, "daml_requested": payload.daml_requested},
    )
    db.commit()
    return _sar_dict(db, sar)


# Legal DAML state machine — enforced on every transition.
_DAML_TRANSITIONS = {
    DamlStatus.AWAITING_CONSENT: {
        DamlStatus.CONSENT_GRANTED,
        DamlStatus.CONSENT_REFUSED_MORATORIUM,
    },
    DamlStatus.CONSENT_REFUSED_MORATORIUM: {
        DamlStatus.MORATORIUM_EXPIRED,
    },
}


@router.post("/mlro/sars/{sar_id}/daml-outcome", tags=["mlro"])
def record_daml_outcome(
    sar_id: int,
    payload: DamlOutcome,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Record the NCA's DAML response. Admin (MLRO) only.

    awaiting_consent → consent_granted (work may proceed) or
    consent_refused_moratorium (31-CALENDAR-day moratorium starts —
    work must NOT proceed until it ends or consent is later given).
    consent_refused_moratorium → moratorium_expired (only once the
    31 days have actually elapsed).
    """
    s = db.query(SarRecord).filter(SarRecord.id == sar_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="SAR record not found")

    target = DamlStatus(payload.status)
    allowed = _DAML_TRANSITIONS.get(s.daml_status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid DAML transition: {s.daml_status.value} → {target.value}"
            ),
        )

    now = _now()
    if target == DamlStatus.CONSENT_REFUSED_MORATORIUM:
        # POCA s.335(6): 31 CALENDAR days from refusal.
        s.moratorium_end = now + timedelta(days=MORATORIUM_CALENDAR_DAYS)
    if target == DamlStatus.MORATORIUM_EXPIRED:
        end = _as_aware(s.moratorium_end)
        if end and now < end:
            raise HTTPException(
                status_code=400,
                detail="The 31-day moratorium has not yet expired",
            )

    s.daml_status = target
    if payload.notes:
        s.notes = ((s.notes + "\n") if s.notes else "") + payload.notes

    _audit(
        db, current_user, AuditLogAction.STATUS_CHANGED,
        "sar_record", s.id,
        f"DAML status → {target.value}",
        details={"moratorium_end": _iso(s.moratorium_end)},
    )
    db.commit()
    return _sar_dict(db, s)


@router.get("/mlro/sars", tags=["mlro"])
def list_sars(
    daml_status: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """All SAR records, optionally filtered by DAML status. Admin only."""
    q = db.query(SarRecord)
    if daml_status:
        try:
            q = q.filter(SarRecord.daml_status == DamlStatus(daml_status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown daml_status '{daml_status}'")
    sars = q.order_by(SarRecord.filed_at.desc()).all()
    out = []
    for s in sars:
        d = _sar_dict(db, s)
        r = db.query(InternalReport).filter(InternalReport.id == s.internal_report_id).first()
        d["matter_id"] = r.matter_id if r else None
        d["matter_reference"] = _matter_ref(db, r.matter_id) if r else None
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Matter freeze helper — for the integration pass to gate matter progression
# ---------------------------------------------------------------------------

@router.get("/mlro/matter-freeze-status/{matter_id}", tags=["mlro"])
def matter_freeze_status(
    matter_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_sync_db),
):
    """Is work on this matter frozen pending DAML?

    Frozen when any SAR linked to this matter has daml_requested and is
    awaiting_consent, or is inside an active 31-day moratorium — work on
    the matter must not proceed (POCA s.335/s.336).

    Readable by any authenticated user so the integration pass can gate
    matter progression, but the reason is DELIBERATELY GENERIC — it must
    not reveal that a SAR exists or that DAML was sought (s.333A
    tipping off). It reads as a compliance hold, nothing more.
    """
    now = _now()
    reports = db.query(InternalReport).filter(InternalReport.matter_id == matter_id).all()
    for r in reports:
        sars = db.query(SarRecord).filter(SarRecord.internal_report_id == r.id).all()
        for s in sars:
            if not s.daml_requested:
                continue
            if s.daml_status == DamlStatus.AWAITING_CONSENT:
                return {
                    "frozen": True,
                    "reason": (
                        "Compliance hold — do not progress this matter. "
                        "Contact the compliance team before taking any further step."
                    ),
                }
            end = _as_aware(s.moratorium_end)
            if s.daml_status == DamlStatus.CONSENT_REFUSED_MORATORIUM and end and now < end:
                return {
                    "frozen": True,
                    "reason": (
                        "Compliance hold — do not progress this matter. "
                        "Contact the compliance team before taking any further step."
                    ),
                }
    return {"frozen": False, "reason": None}


def is_matter_frozen(db: Session, matter_id: int) -> bool:
    """Pure in-process check for the DAML freeze — used by other modules
    to gate matter progression (e.g. the SoF assessment run). Mirrors the
    matter-freeze-status route's logic without the HTTP layer."""
    now = _now()
    reports = db.query(InternalReport).filter(InternalReport.matter_id == matter_id).all()
    for r in reports:
        sars = db.query(SarRecord).filter(SarRecord.internal_report_id == r.id).all()
        for s in sars:
            if not s.daml_requested:
                continue
            if s.daml_status == DamlStatus.AWAITING_CONSENT:
                return True
            end = _as_aware(s.moratorium_end)
            if s.daml_status == DamlStatus.CONSENT_REFUSED_MORATORIUM and end and now < end:
                return True
    return False


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/mlro/dashboard", tags=["mlro"])
def mlro_dashboard(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """MLRO workbench dashboard. Admin only."""
    now = _now()
    soon = now + timedelta(days=7)
    training_horizon = now + timedelta(days=60)

    reports = db.query(InternalReport).all()
    counts = {s.value: 0 for s in InternalReportStatus}
    for r in reports:
        counts[r.status.value] += 1

    sars = db.query(SarRecord).all()
    daml_deadlines = []
    moratoria = []
    for s in sars:
        deadline = _as_aware(s.consent_deadline)
        end = _as_aware(s.moratorium_end)
        if s.daml_status == DamlStatus.AWAITING_CONSENT and deadline and deadline <= soon:
            daml_deadlines.append({
                "sar_id": s.id,
                "sar_reference": s.sar_reference,
                "consent_deadline": _iso(s.consent_deadline),
                "overdue": deadline < now,
            })
        if s.daml_status == DamlStatus.CONSENT_REFUSED_MORATORIUM and end:
            moratoria.append({
                "sar_id": s.id,
                "sar_reference": s.sar_reference,
                "moratorium_end": _iso(s.moratorium_end),
                "days_remaining": max(0, (end - now).days),
                "active": end > now,
            })

    overdue_policies = (
        db.query(PolicyDocument)
        .filter(
            PolicyDocument.status == PolicyStatus.APPROVED,
            PolicyDocument.review_due != None,  # noqa: E711
            PolicyDocument.review_due < now,
        )
        .count()
    )

    expiring_training = (
        db.query(TrainingRecord)
        .filter(
            TrainingRecord.expires_at != None,  # noqa: E711
            TrainingRecord.expires_at <= training_horizon,
        )
        .count()
    )

    return {
        "report_counts": counts,
        "open_reports": counts["received"] + counts["under_review"],
        "daml_deadlines_within_7_days": daml_deadlines,
        "active_moratoria": moratoria,
        "overdue_policy_reviews": overdue_policies,
        "training_expiring_within_60_days": expiring_training,
    }


# ---------------------------------------------------------------------------
# Training records
# ---------------------------------------------------------------------------

def _training_dict(db: Session, t: TrainingRecord) -> dict:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "user_name": _user_name(db, t.user_id),
        "course_name": t.course_name,
        "provider": t.provider,
        "completed_at": _iso(t.completed_at),
        "expires_at": _iso(t.expires_at),
        "certificate_note": t.certificate_note,
    }


@router.get("/mlro/training", tags=["mlro"])
def list_training(
    user_id: Optional[int] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """All training records (admin manages the register)."""
    q = db.query(TrainingRecord)
    if user_id is not None:
        q = q.filter(TrainingRecord.user_id == user_id)
    return [_training_dict(db, t) for t in q.order_by(TrainingRecord.completed_at.desc()).all()]


@router.get("/mlro/training/mine", tags=["mlro"])
def my_training(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_sync_db),
):
    """A user's own training records — any authenticated user."""
    rows = (
        db.query(TrainingRecord)
        .filter(TrainingRecord.user_id == current_user.id)
        .order_by(TrainingRecord.completed_at.desc())
        .all()
    )
    return [_training_dict(db, t) for t in rows]


@router.post("/mlro/training", tags=["mlro"], status_code=201)
def create_training(
    payload: TrainingCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    t = TrainingRecord(
        user_id=payload.user_id,
        course_name=payload.course_name,
        provider=payload.provider,
        completed_at=payload.completed_at,
        expires_at=payload.expires_at,
        certificate_note=payload.certificate_note,
    )
    db.add(t)
    db.flush()
    _audit(db, current_user, AuditLogAction.CREATED, "training_record", t.id,
           f"Training record added for {user.full_name}: {t.course_name}")
    db.commit()
    return _training_dict(db, t)


@router.put("/mlro/training/{training_id}", tags=["mlro"])
def update_training(
    training_id: int,
    payload: TrainingUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    t = db.query(TrainingRecord).filter(TrainingRecord.id == training_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Training record not found")
    for field in ("course_name", "provider", "completed_at", "expires_at", "certificate_note"):
        value = getattr(payload, field)
        if value is not None:
            setattr(t, field, value)
    _audit(db, current_user, AuditLogAction.UPDATED, "training_record", t.id,
           f"Training record updated: {t.course_name}")
    db.commit()
    return _training_dict(db, t)


@router.delete("/mlro/training/{training_id}", tags=["mlro"])
def delete_training(
    training_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    t = db.query(TrainingRecord).filter(TrainingRecord.id == training_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Training record not found")
    _audit(db, current_user, AuditLogAction.DELETED, "training_record", t.id,
           f"Training record deleted: {t.course_name} (user_id={t.user_id})")
    db.delete(t)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Policy repository
# ---------------------------------------------------------------------------

def _policy_dict(db: Session, p: PolicyDocument, include_acks: bool, current_user: User) -> dict:
    acks = p.acknowledgements or []
    d = {
        "id": p.id,
        "title": p.title,
        "version": p.version,
        "status": p.status.value if p.status else None,
        "content_note": p.content_note,
        "approved_by_name": _user_name(db, p.approved_by_id),
        "approved_at": _iso(p.approved_at),
        "review_due": _iso(p.review_due),
        "acknowledged_by_me": any(a.get("user_id") == current_user.id for a in acks),
        "acknowledgement_count": len(acks),
    }
    if include_acks:
        # Admin view: who has and hasn't acknowledged.
        active_users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
        acked_ids = {a.get("user_id") for a in acks}
        d["acknowledgements"] = [
            {
                "user_id": a.get("user_id"),
                "user_name": _user_name(db, a.get("user_id")),
                "acknowledged_at": a.get("acknowledged_at"),
            }
            for a in acks
        ]
        d["not_acknowledged"] = [
            {"user_id": u.id, "user_name": u.full_name}
            for u in active_users if u.id not in acked_ids
        ]
    return d


@router.get("/mlro/policies", tags=["mlro"])
def list_policies(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_sync_db),
):
    """Policy list. Any authenticated user may read (they must be able
    to acknowledge); the full acknowledgement breakdown is admin-only."""
    is_admin = current_user.is_superuser or str(current_user.role.value).lower() == "admin"
    q = db.query(PolicyDocument)
    if not is_admin:
        # Non-admin staff see approved policies only (drafts are MLRO WIP).
        q = q.filter(PolicyDocument.status == PolicyStatus.APPROVED)
    policies = q.order_by(PolicyDocument.title.asc(), PolicyDocument.id.desc()).all()
    return [_policy_dict(db, p, include_acks=is_admin, current_user=current_user) for p in policies]


@router.post("/mlro/policies", tags=["mlro"], status_code=201)
def create_policy(
    payload: PolicyCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    p = PolicyDocument(
        title=payload.title,
        version=payload.version,
        status=PolicyStatus.DRAFT,
        content_note=payload.content_note,
        review_due=payload.review_due,
        acknowledgements=[],
    )
    db.add(p)
    db.flush()
    _audit(db, current_user, AuditLogAction.CREATED, "policy_document", p.id,
           f"Policy created: {p.title} v{p.version} (draft)")
    db.commit()
    return _policy_dict(db, p, include_acks=True, current_user=current_user)


@router.put("/mlro/policies/{policy_id}", tags=["mlro"])
def update_policy(
    policy_id: int,
    payload: PolicyUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    p = db.query(PolicyDocument).filter(PolicyDocument.id == policy_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    if payload.content_note is not None:
        p.content_note = payload.content_note
    if payload.review_due is not None:
        p.review_due = payload.review_due
    _audit(db, current_user, AuditLogAction.UPDATED, "policy_document", p.id,
           f"Policy updated: {p.title} v{p.version}")
    db.commit()
    return _policy_dict(db, p, include_acks=True, current_user=current_user)


@router.post("/mlro/policies/{policy_id}/approve", tags=["mlro"])
def approve_policy(
    policy_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Approve a draft policy; earlier approved versions of the same
    title are marked superseded. Admin only."""
    p = db.query(PolicyDocument).filter(PolicyDocument.id == policy_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    if p.status != PolicyStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft policies can be approved")

    previous = (
        db.query(PolicyDocument)
        .filter(
            PolicyDocument.title == p.title,
            PolicyDocument.status == PolicyStatus.APPROVED,
            PolicyDocument.id != p.id,
        )
        .all()
    )
    for old in previous:
        old.status = PolicyStatus.SUPERSEDED

    p.status = PolicyStatus.APPROVED
    p.approved_by_id = current_user.id
    p.approved_at = _now()

    _audit(db, current_user, AuditLogAction.APPROVED, "policy_document", p.id,
           f"Policy approved: {p.title} v{p.version}"
           + (f" ({len(previous)} prior version(s) superseded)" if previous else ""))
    db.commit()
    return _policy_dict(db, p, include_acks=True, current_user=current_user)


@router.post("/mlro/policies/{policy_id}/acknowledge", tags=["mlro"])
def acknowledge_policy(
    policy_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_sync_db),
):
    """Any authenticated user acknowledges they have read an APPROVED
    policy. Idempotent — acknowledging twice keeps the first timestamp."""
    p = db.query(PolicyDocument).filter(PolicyDocument.id == policy_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    if p.status != PolicyStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Only approved policies can be acknowledged")

    acks = list(p.acknowledgements or [])
    if not any(a.get("user_id") == current_user.id for a in acks):
        acks.append({
            "user_id": current_user.id,
            "acknowledged_at": _iso(_now()),
        })
        p.acknowledgements = acks
        flag_modified(p, "acknowledgements")
        _audit(db, current_user, AuditLogAction.UPDATED, "policy_document", p.id,
               f"Policy acknowledged: {p.title} v{p.version}")
        db.commit()

    return {"acknowledged": True, "policy_id": p.id}
