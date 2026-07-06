"""
KYB (Know Your Business) endpoints — company due diligence via the
Companies House Public Data API.

Routes:
- GET  /kyb/search?q=                                — company search
- POST /matters/{matter_id}/kyb                      — run a KYB check
- GET  /matters/{matter_id}/kyb                      — list checks
- POST /matters/{matter_id}/kyb/{check_id}/refresh   — re-fetch snapshot
- POST /matters/{matter_id}/kyb/{check_id}/psc-discrepancy
       — record a material PSC discrepancy (reg 30A)

Compliance posture:
- reg 28(9): every response carries REG_28_9_NOTE — the PSC register
  alone is NOT verification of beneficial owners; BOs >25% must be
  verified individually (E-IDV).
- reg 30A: recording a PSC discrepancy reminds the caller that the
  firm must report it to Companies House; the platform records, a
  human reports.
- Missing COMPANIES_HOUSE_API_KEY → 409 with setup guidance.
- Companies House rate limit (600/5min) → clean 429.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_analyst, require_matter_access
from app.db.session import get_sync_db
from app.models.audit import AuditLog, AuditLogAction
from app.models.kyb import KybCheck, KybCheckStatus
from app.models.user import User
from app.services import companies_house
from app.services.companies_house import (
    CompaniesHouseAPIError,
    ConfigurationError,
    RateLimitError,
    REG_28_9_NOTE,
    REG_30A_NOTE,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class KybCheckCreateRequest(BaseModel):
    company_number: str = Field(..., min_length=1, max_length=20)
    ownership_notes: Optional[str] = None


class PscDiscrepancyRequest(BaseModel):
    # reg 30A record — substance required, not a tick-box.
    details: str = Field(
        ...,
        min_length=20,
        description=(
            "What was found (the material discrepancy between CDD findings "
            "and the PSC register) and confirmation the firm has reported "
            "it to Companies House."
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _translate_ch_error(exc: Exception) -> HTTPException:
    """Map Companies House client errors onto clean HTTP responses."""
    if isinstance(exc, ConfigurationError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, RateLimitError):
        return HTTPException(status_code=429, detail=str(exc))
    if isinstance(exc, CompaniesHouseAPIError):
        if exc.status_code == 404:
            return HTTPException(status_code=404, detail="Company not found at Companies House.")
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=502, detail="Companies House lookup failed.")


def _fetch_snapshot(client, company_number: str) -> dict:
    """Fetch and summarise profile + officers + PSCs for a company."""
    profile = companies_house.summarise_profile(client.get_company(company_number))
    officers = companies_house.summarise_officers(client.get_officers(company_number))
    pscs = companies_house.summarise_pscs(client.get_pscs(company_number))
    return {"profile": profile, "officers": officers, "pscs": pscs}


# ---------------------------------------------------------------------------
# GET /kyb/search — company search (not matter-scoped)
# ---------------------------------------------------------------------------

@router.get("/kyb/search", tags=["kyb"])
def search_companies(
    q: str = Query(..., min_length=2, description="Company name or number"),
    current_user: User = Depends(require_analyst),
):
    try:
        client = companies_house.get_client()
        raw = client.search_companies(q)
    except (ConfigurationError, RateLimitError, CompaniesHouseAPIError) as exc:
        raise _translate_ch_error(exc)
    return {
        **companies_house.summarise_search_results(raw),
        "reg_28_9_note": REG_28_9_NOTE,
    }


# ---------------------------------------------------------------------------
# POST /matters/{matter_id}/kyb — run a check and persist the snapshot
# ---------------------------------------------------------------------------

@router.post("/matters/{matter_id}/kyb", status_code=201, tags=["kyb"])
def create_kyb_check(
    matter_id: int,
    body: KybCheckCreateRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)

    company_number = companies_house.normalise_company_number(body.company_number)

    try:
        client = companies_house.get_client()
        snapshot = _fetch_snapshot(client, company_number)
    except (ConfigurationError, RateLimitError, CompaniesHouseAPIError) as exc:
        raise _translate_ch_error(exc)

    check = KybCheck(
        matter_id=matter_id,
        company_number=company_number,
        company_name=snapshot["profile"].get("company_name"),
        status=KybCheckStatus.COMPLETE.value,
        profile=snapshot["profile"],
        officers=snapshot["officers"],
        pscs=snapshot["pscs"],
        ownership_notes=body.ownership_notes,
        created_by_id=current_user.id,
    )
    db.add(check)
    db.flush()

    db.add(
        AuditLog(
            matter_id=matter_id,
            user_id=current_user.id,
            action=AuditLogAction.CREATED,
            entity_type="kyb_check",
            entity_id=check.id,
            description=(
                f"KYB check run against Companies House for "
                f"{check.company_name or company_number} ({company_number})"
            ),
            details={
                "company_number": company_number,
                "active_pscs": snapshot["pscs"].get("active_count"),
                "active_officers": snapshot["officers"].get("active_count"),
            },
        )
    )
    db.commit()
    db.refresh(check)

    return {**check.to_dict(), "reg_28_9_note": REG_28_9_NOTE}


# ---------------------------------------------------------------------------
# GET /matters/{matter_id}/kyb — list checks for a matter
# ---------------------------------------------------------------------------

@router.get("/matters/{matter_id}/kyb", tags=["kyb"])
def list_kyb_checks(
    matter_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)
    checks = (
        db.query(KybCheck)
        .filter(KybCheck.matter_id == matter_id)
        .order_by(KybCheck.created_at.desc())
        .all()
    )
    return {
        "items": [c.to_dict() for c in checks],
        "reg_28_9_note": REG_28_9_NOTE,
    }


# ---------------------------------------------------------------------------
# POST /matters/{matter_id}/kyb/{check_id}/refresh — re-fetch snapshot
# ---------------------------------------------------------------------------

@router.post("/matters/{matter_id}/kyb/{check_id}/refresh", tags=["kyb"])
def refresh_kyb_check(
    matter_id: int,
    check_id: int,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)
    check = (
        db.query(KybCheck)
        .filter(KybCheck.id == check_id, KybCheck.matter_id == matter_id)
        .first()
    )
    if not check:
        raise HTTPException(404, "KYB check not found")

    try:
        client = companies_house.get_client()
        snapshot = _fetch_snapshot(client, check.company_number)
    except (ConfigurationError, RateLimitError, CompaniesHouseAPIError) as exc:
        raise _translate_ch_error(exc)

    check.profile = snapshot["profile"]
    check.officers = snapshot["officers"]
    check.pscs = snapshot["pscs"]
    check.company_name = snapshot["profile"].get("company_name") or check.company_name
    check.refreshed_at = datetime.now(timezone.utc)
    # A recorded discrepancy stays recorded — refresh never clears it.
    if check.status != KybCheckStatus.DISCREPANCY_REPORTED.value:
        check.status = KybCheckStatus.COMPLETE.value

    db.add(
        AuditLog(
            matter_id=matter_id,
            user_id=current_user.id,
            action=AuditLogAction.UPDATED,
            entity_type="kyb_check",
            entity_id=check.id,
            description=(
                f"KYB check refreshed from Companies House for "
                f"{check.company_name or check.company_number} ({check.company_number})"
            ),
        )
    )
    db.commit()
    db.refresh(check)

    return {**check.to_dict(), "reg_28_9_note": REG_28_9_NOTE}


# ---------------------------------------------------------------------------
# POST /matters/{matter_id}/kyb/{check_id}/psc-discrepancy — reg 30A record
# ---------------------------------------------------------------------------

@router.post("/matters/{matter_id}/kyb/{check_id}/psc-discrepancy", tags=["kyb"])
def record_psc_discrepancy(
    matter_id: int,
    check_id: int,
    body: PscDiscrepancyRequest,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db),
):
    require_matter_access(matter_id, current_user, db)
    check = (
        db.query(KybCheck)
        .filter(KybCheck.id == check_id, KybCheck.matter_id == matter_id)
        .first()
    )
    if not check:
        raise HTTPException(404, "KYB check not found")

    check.psc_discrepancy = body.details.strip()
    check.psc_discrepancy_reported_at = datetime.now(timezone.utc)
    check.psc_discrepancy_reported_by_id = current_user.id
    check.status = KybCheckStatus.DISCREPANCY_REPORTED.value

    db.add(
        AuditLog(
            matter_id=matter_id,
            user_id=current_user.id,
            action=AuditLogAction.UPDATED,
            entity_type="kyb_check",
            entity_id=check.id,
            description=(
                f"Material PSC discrepancy recorded (reg 30A) for "
                f"{check.company_name or check.company_number} ({check.company_number})"
            ),
            details={"psc_discrepancy": check.psc_discrepancy},
        )
    )
    db.commit()
    db.refresh(check)

    return {
        **check.to_dict(),
        "reg_30a_note": REG_30A_NOTE,
        "reg_28_9_note": REG_28_9_NOTE,
    }
