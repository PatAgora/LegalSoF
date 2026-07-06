"""
Risk Assessment API endpoints.

FWRA — Firm-Wide Risk Assessment (MLR 2017 reg 18 / 18A):
  POST /firm-risk-assessment                    - create draft (admin)
  PUT  /firm-risk-assessment/{id}               - update draft (admin)
  POST /firm-risk-assessment/{id}/approve       - approve + supersede (admin)
  GET  /firm-risk-assessment                    - current + history (analyst)
  GET  /firm-risk-assessment/{id}/export        - structured JSON export

CMRA — Client & Matter Risk Assessment (MLR 2017 reg 28(12)-(13)):
  POST /matters/{matter_id}/risk-assessments                 - create draft
  PUT  /matters/{matter_id}/risk-assessments/{assessment_id} - update draft
  POST /matters/{matter_id}/risk-assessments/{assessment_id}/complete
  GET  /matters/{matter_id}/risk-assessments                 - both types + history
  GET  /risk-assessments/overdue                             - review dashboard

Also exposes matter_has_completed_cmra() — the blocking gate the SoF
assessment run checks before it will execute (wired in separately).
"""
import calendar
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.api.dependencies.auth import require_admin, require_analyst, require_matter_access
from app.models.user import User, UserRole
from app.models.matter import Matter
from app.models.audit import AuditLog, AuditLogAction
from app.models.transaction import TransactionConfig
from app.models.risk_assessment import (
    FirmRiskAssessment, ClientMatterRiskAssessment,
    FirmRAStatus, CMRAStatus, CMRAType, RiskLevel,
    FWRA_SECTIONS, CMRA_FACTORS, REG28_CONSIDERATIONS,
)
from app.services.config_resolver import map_risk_tier, resolve_value

logger = logging.getLogger(__name__)

router = APIRouter()

# The SRA penalises unreasoned template FWRAs — every section must
# carry a substantive narrative before approval.
FWRA_MIN_REASONING_CHARS = 50

# FATF "call for action" (black-list) jurisdictions. MLR 2017 reg 33(1)(b)
# mandates EDD for any business relationship or transaction involving a
# high-risk third country; the call-for-action list is the hard floor.
# UPDATE after each FATF plenary (February / June / October):
#   KP = North Korea (DPRK), IR = Iran, MM = Myanmar.
FATF_CALL_FOR_ACTION_COUNTRIES = ["KP", "IR", "MM"]

# CMRA scoring configuration — resolved through the transaction_config
# table via the standard config_resolver pattern; these in-code values
# are the safe defaults when the keys are not seeded.
# Seed keys to add to the config catalogue (init_transaction_tables):
#   cmra_weight_client            (float, default 0.30)
#   cmra_weight_service_matter    (float, default 0.25)
#   cmra_weight_geography         (float, default 0.20)
#   cmra_weight_delivery_channel  (float, default 0.15)
#   cmra_weight_sector_product    (float, default 0.10)
#   cmra_medium_threshold         (float, default 1.60)
#   cmra_high_threshold           (float, default 2.40)
CMRA_CONFIG_DEFAULTS: Dict[str, float] = {
    "cmra_weight_client": 0.30,
    "cmra_weight_service_matter": 0.25,
    "cmra_weight_geography": 0.20,
    "cmra_weight_delivery_channel": 0.15,
    "cmra_weight_sector_product": 0.10,
    # Weighted-average (1-3 scale) thresholds for medium / high.
    "cmra_medium_threshold": 1.60,
    "cmra_high_threshold": 2.40,
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _add_months(d: date, months: int) -> date:
    """Return d + months, clamped to the last day of the target month."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _load_cmra_config(db: Session, matter: Optional[Matter] = None) -> Dict[str, float]:
    """Resolve CMRA scoring config through the tiered config_resolver.

    Falls back to CMRA_CONFIG_DEFAULTS for missing or unparseable keys
    so an unseeded database degrades to documented behaviour.
    """
    out = dict(CMRA_CONFIG_DEFAULTS)
    try:
        tier = map_risk_tier(
            matter.risk_rating.value if (matter is not None and matter.risk_rating) else "medium"
        )
        rows = db.query(TransactionConfig).filter(
            TransactionConfig.key.in_(CMRA_CONFIG_DEFAULTS.keys())
        ).all()
        for row in rows:
            out[row.key] = resolve_value(
                row.value, row.value_type, tier,
                default=CMRA_CONFIG_DEFAULTS.get(row.key), key=row.key,
            )
    except Exception as exc:
        logger.warning("CMRA config load failed (%s); using built-in defaults", exc)
    return out


def compute_cmra_scoring(
    factors: Dict[str, Any],
    context_flags: Dict[str, Any],
    config: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Derive overall_rating, edd_required and edd_triggers.

    Rules:
      * overall_rating comes from the weighted average of the 1-3 factor
        scores (weights from config, normalised over factors present).
      * A HIGH (3) score in ANY single factor forces at least MEDIUM
        overall — one severe risk cannot be averaged away.
      * EDD is auto-forced when: the client is a PEP (reg 35), the
        geography includes a FATF call-for-action country (reg 33(1)(b)),
        the caller flags unusual complexity (reg 33(6)(b)), or the
        overall rating is HIGH (reg 33(1)(a)).
    """
    cfg = config if config is not None else dict(CMRA_CONFIG_DEFAULTS)

    weighted_sum = 0.0
    weight_total = 0.0
    any_high = False
    for key in CMRA_FACTORS:
        entry = (factors or {}).get(key) or {}
        try:
            score = int(entry.get("score"))
        except (TypeError, ValueError):
            continue
        if score not in (1, 2, 3):
            continue
        weight = float(cfg.get(f"cmra_weight_{key}", 0.0)) or 0.0
        weighted_sum += score * weight
        weight_total += weight
        if score == 3:
            any_high = True

    weighted_avg = (weighted_sum / weight_total) if weight_total > 0 else 0.0

    high_threshold = float(cfg.get("cmra_high_threshold", 2.40))
    medium_threshold = float(cfg.get("cmra_medium_threshold", 1.60))

    if weighted_avg >= high_threshold:
        rating = RiskLevel.HIGH
    elif weighted_avg >= medium_threshold:
        rating = RiskLevel.MEDIUM
    else:
        rating = RiskLevel.LOW

    # A single high factor cannot be diluted below medium.
    if any_high and rating == RiskLevel.LOW:
        rating = RiskLevel.MEDIUM

    triggers: List[str] = []
    flags = context_flags or {}
    if flags.get("client_is_pep"):
        triggers.append("Client is a politically exposed person (PEP) — reg 35 EDD applies")
    countries = [str(c).strip().upper() for c in (flags.get("geography_countries") or [])]
    hits = sorted(set(countries) & set(FATF_CALL_FOR_ACTION_COUNTRIES))
    if hits:
        triggers.append(
            "Geography includes FATF call-for-action jurisdiction(s): "
            + ", ".join(hits) + " — reg 33(1)(b) EDD applies"
        )
    if flags.get("unusual_complexity"):
        triggers.append("Transaction flagged as unusually large or complex — reg 33(6)(b)")
    if rating == RiskLevel.HIGH:
        triggers.append("Overall risk rating is HIGH — reg 33(1)(a) EDD applies")

    return {
        "overall_rating": rating,
        "weighted_score": round(weighted_avg, 4),
        "edd_required": bool(triggers),
        "edd_triggers": triggers,
    }


def matter_has_completed_cmra(db: Session, matter_id: int) -> bool:
    """Blocking gate for the SoF assessment run.

    Reg 28(12)/(13) requires BOTH a written client-level and a written
    matter-level risk assessment, so this returns True only when the
    matter has a COMPLETED assessment of each type.
    """
    completed_types = {
        row[0]
        for row in db.query(ClientMatterRiskAssessment.assessment_type)
        .filter(
            ClientMatterRiskAssessment.matter_id == matter_id,
            ClientMatterRiskAssessment.status == CMRAStatus.COMPLETED,
        )
        .distinct()
        .all()
    }
    return CMRAType.CLIENT in completed_types and CMRAType.MATTER in completed_types


def _audit(
    db: Session,
    user: User,
    action: AuditLogAction,
    entity_type: str,
    entity_id: int,
    description: str,
    matter_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    db.add(AuditLog(
        matter_id=matter_id,
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        details=details,
    ))


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class FirmRAUpdateRequest(BaseModel):
    sections: Optional[Dict[str, Any]] = None
    sectoral_ra_acknowledged: Optional[bool] = None
    sectoral_ra_date: Optional[date] = None
    nra_acknowledged: Optional[bool] = None
    nra_date: Optional[date] = None
    next_review_due: Optional[date] = None


class CMRACreateRequest(BaseModel):
    assessment_type: str = Field(..., description="'client' or 'matter'")
    factors: Dict[str, Any] = Field(default_factory=dict)
    reg28_considerations: Dict[str, Any] = Field(default_factory=dict)
    context_flags: Dict[str, Any] = Field(default_factory=dict)


class CMRAUpdateRequest(BaseModel):
    factors: Optional[Dict[str, Any]] = None
    reg28_considerations: Optional[Dict[str, Any]] = None
    context_flags: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# FWRA validation
# ---------------------------------------------------------------------------

def _validate_fwra_for_approval(fra: FirmRiskAssessment) -> List[str]:
    """Return a list of human-readable problems blocking approval."""
    problems: List[str] = []
    sections = fra.sections or {}
    for key in FWRA_SECTIONS:
        entry = sections.get(key) or {}
        label = key.replace("_", " ")
        level = str(entry.get("risk_level") or "").strip().lower()
        if level not in ("low", "medium", "high"):
            problems.append(f"Section '{label}': a risk level (low/medium/high) is required.")
        reasoning = str(entry.get("reasoning") or "").strip()
        if len(reasoning) < FWRA_MIN_REASONING_CHARS:
            problems.append(
                f"Section '{label}': reasoning must be at least "
                f"{FWRA_MIN_REASONING_CHARS} characters (currently {len(reasoning)}). "
                "Unreasoned template assessments are penalised by the SRA."
            )
    if not fra.sectoral_ra_acknowledged or not fra.sectoral_ra_date:
        problems.append("The SRA sectoral risk assessment must be acknowledged with a date (reg 18(6)).")
    if not fra.nra_acknowledged or not fra.nra_date:
        problems.append("The national risk assessment must be acknowledged with a date (reg 18(6)).")
    return problems


# ---------------------------------------------------------------------------
# FWRA endpoints
# ---------------------------------------------------------------------------

@router.post("/firm-risk-assessment", tags=["risk-assessments"])
def create_firm_risk_assessment(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Create a new draft FWRA version, carrying forward the content of
    the most recent version so a review starts from the current text."""
    existing_draft = (
        db.query(FirmRiskAssessment)
        .filter(FirmRiskAssessment.status == FirmRAStatus.DRAFT)
        .first()
    )
    if existing_draft:
        raise HTTPException(
            status_code=409,
            detail=f"A draft (version {existing_draft.version}) already exists. "
                   "Edit or approve it before creating another.",
        )

    latest = (
        db.query(FirmRiskAssessment)
        .order_by(FirmRiskAssessment.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    if latest is not None:
        sections = dict(latest.sections or {})
    else:
        sections = {}
    # Ensure every mandatory section key exists.
    for key in FWRA_SECTIONS:
        sections.setdefault(key, {"risk_level": "", "reasoning": "", "mitigations": ""})

    fra = FirmRiskAssessment(
        version=next_version,
        status=FirmRAStatus.DRAFT,
        sections=sections,
        created_by_id=current_user.id,
    )
    db.add(fra)
    db.flush()
    _audit(
        db, current_user, AuditLogAction.CREATED, "firm_risk_assessment", fra.id,
        f"Firm-wide risk assessment draft v{next_version} created",
    )
    db.commit()
    db.refresh(fra)
    return fra.to_dict()


@router.put("/firm-risk-assessment/{assessment_id}", tags=["risk-assessments"])
def update_firm_risk_assessment(
    assessment_id: int,
    payload: FirmRAUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Update a DRAFT FWRA. Approved/superseded versions are immutable."""
    fra = db.query(FirmRiskAssessment).filter(FirmRiskAssessment.id == assessment_id).first()
    if not fra:
        raise HTTPException(status_code=404, detail="Firm risk assessment not found")
    if fra.status != FirmRAStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft assessments can be edited")

    if payload.sections is not None:
        unknown = set(payload.sections.keys()) - set(FWRA_SECTIONS)
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown section keys: {', '.join(sorted(unknown))}",
            )
        merged = dict(fra.sections or {})
        for key, entry in payload.sections.items():
            if not isinstance(entry, dict):
                raise HTTPException(status_code=422, detail=f"Section '{key}' must be an object")
            merged[key] = {
                "risk_level": str(entry.get("risk_level") or "").strip().lower(),
                "reasoning": str(entry.get("reasoning") or ""),
                "mitigations": str(entry.get("mitigations") or ""),
            }
        fra.sections = merged

    if payload.sectoral_ra_acknowledged is not None:
        fra.sectoral_ra_acknowledged = payload.sectoral_ra_acknowledged
    if payload.sectoral_ra_date is not None:
        fra.sectoral_ra_date = payload.sectoral_ra_date
    if payload.nra_acknowledged is not None:
        fra.nra_acknowledged = payload.nra_acknowledged
    if payload.nra_date is not None:
        fra.nra_date = payload.nra_date
    if payload.next_review_due is not None:
        fra.next_review_due = payload.next_review_due

    _audit(
        db, current_user, AuditLogAction.UPDATED, "firm_risk_assessment", fra.id,
        f"Firm-wide risk assessment draft v{fra.version} updated",
    )
    db.commit()
    db.refresh(fra)
    return fra.to_dict()


@router.post("/firm-risk-assessment/{assessment_id}/approve", tags=["risk-assessments"])
def approve_firm_risk_assessment(
    assessment_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Approve a draft FWRA. Validates every section is reasoned and
    both external assessments are acknowledged, then supersedes the
    previously approved version."""
    fra = db.query(FirmRiskAssessment).filter(FirmRiskAssessment.id == assessment_id).first()
    if not fra:
        raise HTTPException(status_code=404, detail="Firm risk assessment not found")
    if fra.status != FirmRAStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft assessments can be approved")

    problems = _validate_fwra_for_approval(fra)
    if problems:
        raise HTTPException(status_code=400, detail={"message": "Approval blocked", "problems": problems})

    # Supersede the previously approved version(s).
    prior_approved = (
        db.query(FirmRiskAssessment)
        .filter(FirmRiskAssessment.status == FirmRAStatus.APPROVED)
        .all()
    )
    for prior in prior_approved:
        prior.status = FirmRAStatus.SUPERSEDED

    now = datetime.now(timezone.utc)
    fra.status = FirmRAStatus.APPROVED
    fra.approved_by_id = current_user.id
    fra.approved_at = now
    if not fra.next_review_due:
        fra.next_review_due = _add_months(now.date(), 12)

    _audit(
        db, current_user, AuditLogAction.APPROVED, "firm_risk_assessment", fra.id,
        f"Firm-wide risk assessment v{fra.version} approved"
        + (f", superseding v{prior_approved[0].version}" if prior_approved else ""),
        details={
            "version": fra.version,
            "superseded_versions": [p.version for p in prior_approved],
            "next_review_due": fra.next_review_due.isoformat() if fra.next_review_due else None,
        },
    )
    db.commit()
    db.refresh(fra)
    return fra.to_dict()


@router.get("/firm-risk-assessment", tags=["risk-assessments"])
def get_firm_risk_assessment(
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Current approved FWRA, any open draft, and full version history.
    Flags an overdue review (past next_review_due) prominently."""
    all_versions = (
        db.query(FirmRiskAssessment)
        .order_by(FirmRiskAssessment.version.desc())
        .all()
    )
    current = next((f for f in all_versions if f.status == FirmRAStatus.APPROVED), None)
    draft = next((f for f in all_versions if f.status == FirmRAStatus.DRAFT), None)

    review_overdue = bool(
        current and current.next_review_due and current.next_review_due < date.today()
    )
    return {
        "current": current.to_dict() if current else None,
        "draft": draft.to_dict() if draft else None,
        "history": [f.to_dict() for f in all_versions],
        "review_overdue": review_overdue,
        "review_overdue_message": (
            f"The firm-wide risk assessment review was due on "
            f"{current.next_review_due.strftime('%d/%m/%Y')} — reg 18(4) requires it to be kept up to date."
            if review_overdue else None
        ),
    }


@router.get("/firm-risk-assessment/{assessment_id}/export", tags=["risk-assessments"])
def export_firm_risk_assessment(
    assessment_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Structured JSON export of one FWRA version — the written record
    reg 18 requires the firm to be able to produce. PDF rendering is a
    follow-up (route shape kept stable for it)."""
    fra = db.query(FirmRiskAssessment).filter(FirmRiskAssessment.id == assessment_id).first()
    if not fra:
        raise HTTPException(status_code=404, detail="Firm risk assessment not found")

    _audit(
        db, current_user, AuditLogAction.EXPORTED, "firm_risk_assessment", fra.id,
        f"Firm-wide risk assessment v{fra.version} exported",
    )
    db.commit()

    approver = db.query(User).filter(User.id == fra.approved_by_id).first() if fra.approved_by_id else None
    return {
        "document": "Firm-Wide Risk Assessment (MLR 2017 regulations 18 and 18A)",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": current_user.full_name or current_user.email,
        "assessment": fra.to_dict(),
        "approved_by": (approver.full_name or approver.email) if approver else None,
        "regulatory_basis": {
            "regulation_18": "Risk assessment by relevant persons — customers, countries/geographic areas, products/services, transactions, delivery channels",
            "regulation_18A": "Proliferation financing risk assessment",
            "regulation_18_6": "Sectoral (SRA) and national (NRA) risk assessments taken into account",
        },
        "export_format_note": "Structured JSON. PDF rendering is a planned follow-up.",
    }


# ---------------------------------------------------------------------------
# CMRA validation
# ---------------------------------------------------------------------------

def _normalise_cmra_factors(factors: Dict[str, Any]) -> Dict[str, Any]:
    unknown = set((factors or {}).keys()) - set(CMRA_FACTORS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown factor keys: {', '.join(sorted(unknown))}")
    out: Dict[str, Any] = {}
    for key, entry in (factors or {}).items():
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail=f"Factor '{key}' must be an object")
        score = entry.get("score")
        if score is not None:
            try:
                score = int(score)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"Factor '{key}': score must be 1, 2 or 3")
            if score not in (1, 2, 3):
                raise HTTPException(status_code=422, detail=f"Factor '{key}': score must be 1, 2 or 3")
        out[key] = {"score": score, "reasoning": str(entry.get("reasoning") or "")}
    return out


def _validate_cmra_for_completion(cmra: ClientMatterRiskAssessment) -> List[str]:
    problems: List[str] = []
    factors = cmra.factors or {}
    for key in CMRA_FACTORS:
        entry = factors.get(key) or {}
        label = key.replace("_", " ")
        score = entry.get("score")
        if score not in (1, 2, 3):
            problems.append(f"Factor '{label}': a score of 1-3 is required.")
        if not str(entry.get("reasoning") or "").strip():
            problems.append(
                f"Factor '{label}': written reasoning is required — a score without "
                "reasoning is a tick-box assessment, which the SRA penalises."
            )
    reg28 = cmra.reg28_considerations or {}
    labels = {
        "purpose_of_matter": "purpose of the matter",
        "size_of_transaction": "size of the transaction",
        "regularity_duration": "regularity and duration of the relationship",
    }
    for key in REG28_CONSIDERATIONS:
        if not str(reg28.get(key) or "").strip():
            problems.append(
                f"Regulation 28(13) consideration '{labels[key]}' must be addressed in writing."
            )
    return problems


def _recompute_cmra(db: Session, cmra: ClientMatterRiskAssessment, matter: Matter) -> None:
    cfg = _load_cmra_config(db, matter)
    result = compute_cmra_scoring(cmra.factors or {}, cmra.context_flags or {}, cfg)
    cmra.overall_rating = result["overall_rating"]
    cmra.edd_required = result["edd_required"]
    cmra.edd_triggers = result["edd_triggers"]


# Review cadence by rating (months) — set at completion.
CMRA_REVIEW_MONTHS = {RiskLevel.HIGH: 6, RiskLevel.MEDIUM: 12, RiskLevel.LOW: 24}


# ---------------------------------------------------------------------------
# CMRA endpoints
# ---------------------------------------------------------------------------

@router.post("/matters/{matter_id}/risk-assessments", tags=["risk-assessments"])
def create_matter_risk_assessment(
    matter_id: int,
    payload: CMRACreateRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    matter = require_matter_access(matter_id, current_user, db)

    try:
        assessment_type = CMRAType(str(payload.assessment_type).strip().lower())
    except ValueError:
        raise HTTPException(status_code=422, detail="assessment_type must be 'client' or 'matter'")

    existing_draft = (
        db.query(ClientMatterRiskAssessment)
        .filter(
            ClientMatterRiskAssessment.matter_id == matter_id,
            ClientMatterRiskAssessment.assessment_type == assessment_type,
            ClientMatterRiskAssessment.status == CMRAStatus.DRAFT,
        )
        .first()
    )
    if existing_draft:
        raise HTTPException(
            status_code=409,
            detail=f"A draft {assessment_type.value} assessment already exists for this matter.",
        )

    cmra = ClientMatterRiskAssessment(
        matter_id=matter_id,
        assessment_type=assessment_type,
        factors=_normalise_cmra_factors(payload.factors),
        reg28_considerations=payload.reg28_considerations or {},
        context_flags=payload.context_flags or {},
        status=CMRAStatus.DRAFT,
    )
    _recompute_cmra(db, cmra, matter)
    db.add(cmra)
    db.flush()
    _audit(
        db, current_user, AuditLogAction.CREATED, "client_matter_risk_assessment", cmra.id,
        f"{assessment_type.value.capitalize()} risk assessment draft created",
        matter_id=matter_id,
    )
    db.commit()
    db.refresh(cmra)
    return cmra.to_dict()


@router.put("/matters/{matter_id}/risk-assessments/{assessment_id}", tags=["risk-assessments"])
def update_matter_risk_assessment(
    matter_id: int,
    assessment_id: int,
    payload: CMRAUpdateRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    matter = require_matter_access(matter_id, current_user, db)
    cmra = (
        db.query(ClientMatterRiskAssessment)
        .filter(
            ClientMatterRiskAssessment.id == assessment_id,
            ClientMatterRiskAssessment.matter_id == matter_id,
        )
        .first()
    )
    if not cmra:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    if cmra.status != CMRAStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft assessments can be edited")

    if payload.factors is not None:
        merged = dict(cmra.factors or {})
        merged.update(_normalise_cmra_factors(payload.factors))
        cmra.factors = merged
    if payload.reg28_considerations is not None:
        merged28 = dict(cmra.reg28_considerations or {})
        merged28.update(payload.reg28_considerations)
        cmra.reg28_considerations = merged28
    if payload.context_flags is not None:
        mergedcf = dict(cmra.context_flags or {})
        mergedcf.update(payload.context_flags)
        cmra.context_flags = mergedcf

    _recompute_cmra(db, cmra, matter)
    _audit(
        db, current_user, AuditLogAction.UPDATED, "client_matter_risk_assessment", cmra.id,
        f"{cmra.assessment_type.value.capitalize()} risk assessment draft updated",
        matter_id=matter_id,
    )
    db.commit()
    db.refresh(cmra)
    return cmra.to_dict()


@router.post("/matters/{matter_id}/risk-assessments/{assessment_id}/complete", tags=["risk-assessments"])
def complete_matter_risk_assessment(
    matter_id: int,
    assessment_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Complete a draft assessment. Validates all reasoning and reg 28(13)
    considerations are present, derives the final rating/EDD position,
    supersedes any prior completed assessment of the same type, and sets
    the review date by rating (high 6mo / medium 12mo / low 24mo)."""
    matter = require_matter_access(matter_id, current_user, db)
    cmra = (
        db.query(ClientMatterRiskAssessment)
        .filter(
            ClientMatterRiskAssessment.id == assessment_id,
            ClientMatterRiskAssessment.matter_id == matter_id,
        )
        .first()
    )
    if not cmra:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    if cmra.status != CMRAStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft assessments can be completed")

    problems = _validate_cmra_for_completion(cmra)
    if problems:
        raise HTTPException(status_code=400, detail={"message": "Completion blocked", "problems": problems})

    _recompute_cmra(db, cmra, matter)

    prior_completed = (
        db.query(ClientMatterRiskAssessment)
        .filter(
            ClientMatterRiskAssessment.matter_id == matter_id,
            ClientMatterRiskAssessment.assessment_type == cmra.assessment_type,
            ClientMatterRiskAssessment.status == CMRAStatus.COMPLETED,
            ClientMatterRiskAssessment.id != cmra.id,
        )
        .all()
    )
    for prior in prior_completed:
        prior.status = CMRAStatus.SUPERSEDED

    now = datetime.now(timezone.utc)
    cmra.status = CMRAStatus.COMPLETED
    cmra.completed_by_id = current_user.id
    cmra.completed_at = now
    cmra.review_due = _add_months(now.date(), CMRA_REVIEW_MONTHS[cmra.overall_rating])

    _audit(
        db, current_user, AuditLogAction.APPROVED, "client_matter_risk_assessment", cmra.id,
        f"{cmra.assessment_type.value.capitalize()} risk assessment completed — "
        f"overall rating {cmra.overall_rating.value.upper()}"
        + (", EDD required" if cmra.edd_required else ""),
        matter_id=matter_id,
        details={
            "overall_rating": cmra.overall_rating.value,
            "edd_required": cmra.edd_required,
            "edd_triggers": cmra.edd_triggers,
            "review_due": cmra.review_due.isoformat(),
            "superseded_ids": [p.id for p in prior_completed],
        },
    )
    db.commit()
    db.refresh(cmra)
    return cmra.to_dict()


@router.get("/matters/{matter_id}/risk-assessments", tags=["risk-assessments"])
def list_matter_risk_assessments(
    matter_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """All assessments for a matter (both types, full history), plus the
    current (completed) assessment per type and the SoF blocking-gate
    state."""
    require_matter_access(matter_id, current_user, db)
    rows = (
        db.query(ClientMatterRiskAssessment)
        .filter(ClientMatterRiskAssessment.matter_id == matter_id)
        .order_by(ClientMatterRiskAssessment.created_at.desc(), ClientMatterRiskAssessment.id.desc())
        .all()
    )
    current_by_type = {}
    draft_by_type = {}
    for row in rows:
        t = row.assessment_type.value
        if row.status == CMRAStatus.COMPLETED and t not in current_by_type:
            current_by_type[t] = row.to_dict()
        if row.status == CMRAStatus.DRAFT and t not in draft_by_type:
            draft_by_type[t] = row.to_dict()
    return {
        "assessments": [r.to_dict() for r in rows],
        "current": current_by_type,
        "drafts": draft_by_type,
        "cmra_complete": matter_has_completed_cmra(db, matter_id),
    }


@router.get("/risk-assessments/overdue", tags=["risk-assessments"])
def list_overdue_risk_assessments(
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    """Completed assessments past their review_due date, across matters
    the caller may access — the periodic-review dashboard feed."""
    today = date.today()
    q = (
        db.query(ClientMatterRiskAssessment, Matter)
        .join(Matter, Matter.id == ClientMatterRiskAssessment.matter_id)
        .filter(
            ClientMatterRiskAssessment.status == CMRAStatus.COMPLETED,
            ClientMatterRiskAssessment.review_due.isnot(None),
            ClientMatterRiskAssessment.review_due < today,
            Matter.is_archived.is_(False),
        )
    )
    # Analysts see only their accessible matters (same policy as
    # require_matter_access); admins/partners/superusers see all.
    if not (current_user.is_superuser or current_user.role in (UserRole.ADMIN, UserRole.PARTNER)):
        q = q.filter(
            (Matter.assigned_analyst_id.is_(None))
            | (Matter.assigned_analyst_id == current_user.id)
            | (Matter.created_by_id == current_user.id)
        )

    items = []
    for cmra, matter in q.order_by(ClientMatterRiskAssessment.review_due.asc()).all():
        d = cmra.to_dict()
        d["matter_reference"] = matter.reference_number
        d["client_name"] = matter.client_name
        d["days_overdue"] = (today - cmra.review_due).days
        items.append(d)
    return {"overdue": items, "count": len(items)}
