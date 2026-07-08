"""
PEP / Sanctions Screening API endpoints.

- POST /matters/{id}/screening/run                      – screen a subject
- GET  /matters/{id}/screening                          – checks with hits
- POST /matters/{id}/screening/hits/{hit_id}/adjudicate – remediation workflow
- POST /screening/rescreen-all                          – admin batch re-screen
- GET  /screening/dataset-status                        – dataset freshness

Sanctions screening is a STRICT-LIABILITY regime (SAMLA 2018), separate
from risk-based AML: every party is screened regardless of matter risk.
"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.auth import require_admin, require_analyst, require_matter_access
from app.db.session import get_sync_db
from app.models.audit import AuditLog, AuditLogAction
from app.models.matter import Matter
from app.models.screening import (
    HitAdjudicationStatus,
    SanctionsEntry,
    ScreeningCheck,
    ScreeningCheckStatus,
    ScreeningHit,
    ScreeningSubjectType,
)
from app.models.user import User
from app.services.sanctions_screening import derive_check_status, get_latest_dataset
from app.services.screening_providers import CompositeScreener, LocalUKListProvider

router = APIRouter()

DATASET_STALE_AFTER_DAYS = 7

OFSI_GUIDANCE = (
    "A hit has been confirmed as a true sanctions match. This is a sanctions "
    "freeze situation: stop all work on this matter immediately, do not deal "
    "with any funds or assets, and consult your MLRO without delay. Consider "
    "your reporting obligations to OFSI under the Sanctions and Anti-Money "
    "Laundering Act 2018 — dealing with a designated person's assets is a "
    "strict-liability offence."
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ScreeningRunRequest(BaseModel):
    subject_name: str = Field(min_length=2, max_length=255)
    subject_type: ScreeningSubjectType
    subject_dob: Optional[date] = None


class AdjudicationRequest(BaseModel):
    status: Literal["true_match", "false_positive"]
    rationale: str = Field(min_length=10)


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------

def _hit_to_dict(hit: ScreeningHit) -> dict:
    return {
        "id": hit.id,
        "check_id": hit.check_id,
        "source": hit.source,
        "category": hit.category,
        "matched_name": hit.matched_name,
        "external_ref": hit.external_ref,
        "score": hit.score,
        "raw": hit.raw or {},
        "adjudication_status": hit.adjudication_status.value if hit.adjudication_status else "pending",
        "adjudicated_by_id": hit.adjudicated_by_id,
        "adjudication_rationale": hit.adjudication_rationale,
        "adjudicated_at": hit.adjudicated_at.isoformat() if hit.adjudicated_at else None,
    }


def _check_to_dict(check: ScreeningCheck) -> dict:
    return {
        "id": check.id,
        "matter_id": check.matter_id,
        "subject_type": check.subject_type.value if check.subject_type else None,
        "subject_name": check.subject_name,
        "subject_dob": check.subject_dob.isoformat() if check.subject_dob else None,
        "status": check.status.value if check.status else None,
        "requires_escalation": bool(check.requires_escalation),
        "dataset_version": check.dataset_version,
        "providers_used": check.providers_used or [],
        "created_by_id": check.created_by_id,
        "created_at": check.created_at.isoformat() if check.created_at else None,
        "hits": [_hit_to_dict(h) for h in check.hits],
    }


def _persist_check(
    db: Session,
    matter_id: int,
    subject_name: str,
    subject_type: ScreeningSubjectType,
    subject_dob: Optional[date],
    hits: list,
    providers_used: List[str],
    dataset_version: Optional[str],
    created_by_id: Optional[int],
) -> ScreeningCheck:
    """Create a ScreeningCheck + ScreeningHit rows from provider hits."""
    check = ScreeningCheck(
        matter_id=matter_id,
        subject_type=subject_type,
        subject_name=subject_name,
        subject_dob=subject_dob,
        status=(
            ScreeningCheckStatus.POTENTIAL_MATCH if hits else ScreeningCheckStatus.CLEAR
        ),
        dataset_version=dataset_version,
        providers_used=providers_used,
        created_by_id=created_by_id,
    )
    db.add(check)
    db.flush()
    for hit in hits:
        for category in (hit.categories or ["sanctions"]):
            db.add(ScreeningHit(
                check_id=check.id,
                source=hit.source,
                category=category,
                matched_name=hit.name,
                external_ref=hit.external_ref,
                score=hit.score,
                raw=hit.raw or {},
            ))
    return check


def _hit_signature(check: ScreeningCheck) -> frozenset:
    return frozenset((h.source, h.external_ref or h.matched_name) for h in check.hits)


# ---------------------------------------------------------------------------
# Run a screening check
# ---------------------------------------------------------------------------

@router.post("/matters/{matter_id}/screening/run", tags=["screening"])
def run_screening(
    matter_id: int,
    body: ScreeningRunRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)

    dataset = get_latest_dataset(db)
    # Subjects are people by default, but a counterparty (or client) may be
    # a company — entity_type is left unconstrained so both are matched.
    screener = CompositeScreener(db)
    hits, providers_used = screener.screen(
        body.subject_name, dob=body.subject_dob, entity_type=None,
    )

    check = _persist_check(
        db,
        matter_id=matter_id,
        subject_name=body.subject_name.strip(),
        subject_type=body.subject_type,
        subject_dob=body.subject_dob,
        hits=hits,
        providers_used=providers_used,
        dataset_version=dataset.version if dataset else None,
        created_by_id=current_user.id,
    )

    db.add(AuditLog(
        matter_id=matter_id,
        user_id=current_user.id,
        action=AuditLogAction.CREATED,
        entity_type="screening_check",
        entity_id=check.id,
        description=(
            f"PEP/sanctions screening run for {body.subject_type.value} "
            f"'{check.subject_name}': {len(check.hits)} hit(s), status {check.status.value}"
        ),
        details={
            "subject_name": check.subject_name,
            "subject_type": body.subject_type.value,
            "subject_dob": body.subject_dob.isoformat() if body.subject_dob else None,
            "providers_used": providers_used,
            "dataset_version": check.dataset_version,
            "hit_count": len(check.hits),
        },
    ))
    db.commit()
    db.refresh(check)

    result = _check_to_dict(check)
    if dataset is None:
        result["warning"] = (
            "No UK Sanctions List dataset is imported — only external providers "
            "(if configured) were used. Run scripts/update_sanctions_list.py."
        )
    return result


# ---------------------------------------------------------------------------
# List checks for a matter
# ---------------------------------------------------------------------------

@router.get("/matters/{matter_id}/screening", tags=["screening"])
def list_screening_checks(
    matter_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)
    checks = (
        db.query(ScreeningCheck)
        .options(selectinload(ScreeningCheck.hits))
        .filter(ScreeningCheck.matter_id == matter_id)
        .order_by(ScreeningCheck.created_at.desc(), ScreeningCheck.id.desc())
        .all()
    )
    return {"checks": [_check_to_dict(c) for c in checks]}


# ---------------------------------------------------------------------------
# Adjudicate a hit (the remediation workflow)
# ---------------------------------------------------------------------------

@router.post("/matters/{matter_id}/screening/hits/{hit_id}/adjudicate", tags=["screening"])
def adjudicate_hit(
    matter_id: int,
    hit_id: int,
    body: AdjudicationRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)

    hit = (
        db.query(ScreeningHit)
        .join(ScreeningCheck, ScreeningHit.check_id == ScreeningCheck.id)
        .filter(ScreeningHit.id == hit_id, ScreeningCheck.matter_id == matter_id)
        .first()
    )
    if not hit:
        raise HTTPException(404, "Screening hit not found on this matter")

    new_status = HitAdjudicationStatus(body.status)
    previous = hit.adjudication_status.value if hit.adjudication_status else "pending"

    # Actor is ALWAYS the authenticated user.
    hit.adjudication_status = new_status
    hit.adjudicated_by_id = current_user.id
    hit.adjudication_rationale = body.rationale.strip()
    hit.adjudicated_at = datetime.now(timezone.utc)

    check = hit.check
    derived = derive_check_status(h.adjudication_status for h in check.hits)
    check.status = ScreeningCheckStatus(derived)
    check.requires_escalation = derived == "confirmed_match"

    db.add(AuditLog(
        matter_id=matter_id,
        user_id=current_user.id,
        action=AuditLogAction.UPDATED,
        entity_type="screening_hit",
        entity_id=hit.id,
        description=(
            f"Screening hit '{hit.matched_name}' adjudicated "
            f"{previous} -> {new_status.value}; check status now {derived}"
        ),
        details={
            "check_id": check.id,
            "hit_id": hit.id,
            "matched_name": hit.matched_name,
            "source": hit.source,
            "previous_status": previous,
            "new_status": new_status.value,
            "rationale": hit.adjudication_rationale,
            "check_status": derived,
            "requires_escalation": check.requires_escalation,
        },
    ))
    db.commit()
    db.refresh(check)

    result = {
        "hit": _hit_to_dict(hit),
        "check": _check_to_dict(check),
    }
    if check.requires_escalation:
        result["guidance"] = OFSI_GUIDANCE
    return result


# ---------------------------------------------------------------------------
# Batch re-screen (admin) — the cron story after a dataset update
# ---------------------------------------------------------------------------

def rescreen_all_matters(db: Session, actor_user_id: int | None) -> dict:
    """Re-run every non-archived matter's latest screening subjects against
    the CURRENT dataset. A new check is created only where the hit set
    differs from the subject's latest check (quiet re-screens leave no
    noise). Local UK-list provider only.

    Shared by the admin endpoint and the daily cron script;
    `actor_user_id` is the audit actor (None for an automated system run).
    Raises RuntimeError if no dataset is imported.
    """
    dataset = get_latest_dataset(db)
    if dataset is None:
        raise RuntimeError("No sanctions dataset imported — run the update script first")

    provider = LocalUKListProvider(db)
    matters_scanned = 0
    subjects_screened = 0
    new_checks: list = []

    matter_ids = [
        row[0]
        for row in db.query(Matter.id)
        .filter(Matter.is_archived.is_(False))
        .all()
    ]
    for matter_id in matter_ids:
        checks = (
            db.query(ScreeningCheck)
            .options(selectinload(ScreeningCheck.hits))
            .filter(ScreeningCheck.matter_id == matter_id)
            .order_by(ScreeningCheck.created_at.desc(), ScreeningCheck.id.desc())
            .all()
        )
        if not checks:
            continue
        matters_scanned += 1

        # Latest check per distinct subject.
        latest_by_subject: dict = {}
        for check in checks:  # newest first
            key = (check.subject_type, check.subject_name, check.subject_dob)
            latest_by_subject.setdefault(key, check)

        for (subject_type, subject_name, subject_dob), latest in latest_by_subject.items():
            subjects_screened += 1
            hits = provider.screen(subject_name, dob=subject_dob)
            new_signature = frozenset(
                (h.source, h.external_ref or h.name) for h in hits
            )
            if new_signature == _hit_signature(latest):
                continue

            check = _persist_check(
                db,
                matter_id=matter_id,
                subject_name=subject_name,
                subject_type=subject_type,
                subject_dob=subject_dob,
                hits=hits,
                providers_used=[provider.name],
                dataset_version=dataset.version,
                created_by_id=actor_user_id,
            )
            db.add(AuditLog(
                matter_id=matter_id,
                user_id=actor_user_id,
                action=AuditLogAction.CREATED,
                entity_type="screening_check",
                entity_id=check.id,
                description=(
                    f"Batch re-screen against dataset {dataset.version}: hit set changed "
                    f"for {subject_type.value} '{subject_name}' ({len(check.hits)} hit(s))"
                ),
                details={
                    "trigger": "rescreen_all",
                    "dataset_version": dataset.version,
                    "previous_check_id": latest.id,
                    "hit_count": len(check.hits),
                },
            ))
            new_checks.append({
                "matter_id": matter_id,
                "check_id": check.id,
                "subject_name": subject_name,
                "subject_type": subject_type.value,
                "status": check.status.value,
                "hit_count": len(check.hits),
            })

    db.commit()
    return {
        "dataset_version": dataset.version,
        "matters_scanned": matters_scanned,
        "subjects_screened": subjects_screened,
        "new_checks_created": len(new_checks),
        "new_checks": new_checks,
    }


@router.post("/screening/rescreen-all", tags=["screening"])
def rescreen_all(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db),
):
    """Admin-triggered batch re-screen of every non-archived matter against
    the current dataset (see rescreen_all_matters for the logic)."""
    try:
        return rescreen_all_matters(db, actor_user_id=current_user.id)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


# ---------------------------------------------------------------------------
# Dataset status
# ---------------------------------------------------------------------------

@router.get("/screening/dataset-status", tags=["screening"])
def dataset_status(
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    dataset = get_latest_dataset(db)
    if dataset is None:
        return {
            "available": False,
            "warning": (
                "No UK Sanctions List dataset has been imported. Screening is "
                "limited to external providers. Run scripts/update_sanctions_list.py."
            ),
        }

    entry_count = (
        db.query(SanctionsEntry)
        .filter(SanctionsEntry.dataset_id == dataset.id)
        .count()
    )
    imported_at = dataset.imported_at
    now = datetime.now(timezone.utc)
    if imported_at is not None and imported_at.tzinfo is None:
        imported_at = imported_at.replace(tzinfo=timezone.utc)
    age_days = (now - imported_at).days if imported_at else None
    stale = age_days is None or age_days > DATASET_STALE_AFTER_DAYS

    result = {
        "available": True,
        "source": dataset.source,
        "version": dataset.version,
        "date_generated": dataset.date_generated.isoformat() if dataset.date_generated else None,
        "imported_at": dataset.imported_at.isoformat() if dataset.imported_at else None,
        "entry_count": entry_count,
        "age_days": age_days,
        "stale": stale,
    }
    if stale:
        result["warning"] = (
            f"The UK Sanctions List dataset is more than {DATASET_STALE_AFTER_DAYS} "
            "days old. Update it (scripts/update_sanctions_list.py) and re-screen "
            "open matters — designations change frequently."
        )
    return result
