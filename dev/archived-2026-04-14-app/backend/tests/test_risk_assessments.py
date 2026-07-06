"""
Tests for the Risk Assessment module (FWRA + CMRA).

Covers:
  * CMRA scoring derivation — weighted averages, single-high forcing,
    EDD auto-triggers (PEP / FATF call-for-action geography / unusual
    complexity / high overall rating).
  * FWRA approve validation failures (short reasoning, missing
    acknowledgements) and version supersession.
  * CMRA completion validation, review_due cadence by rating, and
    supersession of prior completed assessments.
  * The matter_has_completed_cmra() SoF blocking gate.

Run with: pytest tests/test_risk_assessments.py -v
"""
import os
import sys
from datetime import date

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.matter import Matter
from app.models.user import User, UserRole
from app.models.risk_assessment import (
    FirmRiskAssessment, ClientMatterRiskAssessment,
    FirmRAStatus, CMRAStatus, CMRAType, RiskLevel,
    FWRA_SECTIONS, CMRA_FACTORS,
)
from app.api.v1.endpoints.risk_assessments import (
    compute_cmra_scoring, matter_has_completed_cmra,
    create_firm_risk_assessment, update_firm_risk_assessment,
    approve_firm_risk_assessment, get_firm_risk_assessment,
    export_firm_risk_assessment,
    create_matter_risk_assessment, update_matter_risk_assessment,
    complete_matter_risk_assessment, list_matter_risk_assessments,
    list_overdue_risk_assessments,
    FirmRAUpdateRequest, CMRACreateRequest, CMRAUpdateRequest,
    CMRA_CONFIG_DEFAULTS, _add_months,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Fresh in-memory SQLite per test — no cross-test state."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def admin_user(db_session):
    user = User(
        email="admin@test.com", full_name="Admin User",
        role=UserRole.ADMIN, hashed_password="hash",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def analyst_user(db_session):
    user = User(
        email="analyst@test.com", full_name="Analyst User",
        role=UserRole.ANALYST, hashed_password="hash",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def sample_matter(db_session, analyst_user):
    db_session.execute(text(
        "INSERT INTO matters (id, reference_number, client_name, transaction_type, "
        "target_amount, target_currency, status, risk_rating, created_by_id, is_archived) "
        "VALUES (77, 'RA-TEST-001', 'Test Client', 'PROPERTY_PURCHASE', "
        f"350000.0, 'GBP', 'DRAFT', 'MEDIUM', {analyst_user.id}, 0)"
    ))
    db_session.commit()
    return db_session.query(Matter).filter(Matter.id == 77).first()


def _factors(scores, reasoning="Documented reasoning for this factor."):
    """Build a full five-factor dict from a {factor: score} mapping."""
    return {
        key: {"score": scores.get(key, 1), "reasoning": reasoning}
        for key in CMRA_FACTORS
    }


REG28_OK = {
    "purpose_of_matter": "Purchase of a residential property in Cardiff.",
    "size_of_transaction": "GBP 350,000 — consistent with the client's profile.",
    "regularity_duration": "One-off retainer; no prior relationship.",
}


# ---------------------------------------------------------------------------
# Scoring derivation
# ---------------------------------------------------------------------------

class TestCMRAScoring:
    def test_all_low_scores_give_low_rating(self):
        result = compute_cmra_scoring(_factors({}), {})
        assert result["overall_rating"] == RiskLevel.LOW
        assert result["edd_required"] is False
        assert result["edd_triggers"] == []

    def test_all_high_scores_give_high_rating_and_edd(self):
        scores = {k: 3 for k in CMRA_FACTORS}
        result = compute_cmra_scoring(_factors(scores), {})
        assert result["overall_rating"] == RiskLevel.HIGH
        # High overall rating auto-forces EDD (reg 33(1)(a)).
        assert result["edd_required"] is True
        assert any("HIGH" in t for t in result["edd_triggers"])

    def test_weighted_average_medium(self):
        # client (0.30) and service_matter (0.25) at 2, rest at 1:
        # avg = (2*0.30 + 2*0.25 + 1*0.45) / 1.0 = 1.55 -> below default
        # medium threshold (1.60) -> LOW. Push geography to 2 as well:
        # avg = 1.75 -> MEDIUM.
        result = compute_cmra_scoring(
            _factors({"client": 2, "service_matter": 2, "geography": 2}), {}
        )
        assert result["overall_rating"] == RiskLevel.MEDIUM

    def test_single_high_factor_forces_at_least_medium(self):
        # Only the LOWEST-weighted factor is high (sector_product, 0.10):
        # avg = (3*0.10 + 1*0.90) = 1.20 -> would be LOW by average, but
        # a single high factor must force at least MEDIUM.
        result = compute_cmra_scoring(_factors({"sector_product": 3}), {})
        assert result["weighted_score"] < CMRA_CONFIG_DEFAULTS["cmra_medium_threshold"]
        assert result["overall_rating"] == RiskLevel.MEDIUM

    def test_config_weights_respected(self):
        # Overweight geography so a single 3 there pushes the average high.
        cfg = dict(CMRA_CONFIG_DEFAULTS)
        cfg["cmra_weight_geography"] = 5.0
        result = compute_cmra_scoring(_factors({"geography": 3}), {}, cfg)
        assert result["overall_rating"] == RiskLevel.HIGH

    def test_pep_triggers_edd(self):
        result = compute_cmra_scoring(_factors({}), {"client_is_pep": True})
        assert result["edd_required"] is True
        assert any("PEP" in t for t in result["edd_triggers"])
        # PEP alone does not change the arithmetic rating.
        assert result["overall_rating"] == RiskLevel.LOW

    def test_fatf_call_for_action_country_triggers_edd(self):
        result = compute_cmra_scoring(
            _factors({}), {"geography_countries": ["GB", "ir"]}
        )
        assert result["edd_required"] is True
        assert any("IR" in t for t in result["edd_triggers"])

    def test_safe_country_does_not_trigger_edd(self):
        result = compute_cmra_scoring(
            _factors({}), {"geography_countries": ["GB", "FR"]}
        )
        assert result["edd_required"] is False

    def test_unusual_complexity_triggers_edd(self):
        result = compute_cmra_scoring(_factors({}), {"unusual_complexity": True})
        assert result["edd_required"] is True
        assert any("complex" in t.lower() for t in result["edd_triggers"])

    def test_multiple_triggers_all_listed(self):
        result = compute_cmra_scoring(
            _factors({k: 3 for k in CMRA_FACTORS}),
            {"client_is_pep": True, "geography_countries": ["KP"], "unusual_complexity": True},
        )
        assert result["edd_required"] is True
        assert len(result["edd_triggers"]) == 4  # PEP + FATF + complexity + high rating


# ---------------------------------------------------------------------------
# FWRA lifecycle
# ---------------------------------------------------------------------------

GOOD_SECTION = {
    "risk_level": "medium",
    "reasoning": "Documented, matter-specific reasoning of well over the fifty character minimum.",
    "mitigations": "Standard CDD plus targeted monitoring.",
}


def _fill_fwra_sections(db, admin, fra_id, sections=None):
    payload = FirmRAUpdateRequest(
        sections=sections or {k: dict(GOOD_SECTION) for k in FWRA_SECTIONS},
        sectoral_ra_acknowledged=True,
        sectoral_ra_date=date.today(),
        nra_acknowledged=True,
        nra_date=date.today(),
    )
    return update_firm_risk_assessment(fra_id, payload, admin, db)


class TestFWRA:
    def test_create_draft_v1_has_all_sections(self, db_session, admin_user):
        d = create_firm_risk_assessment(admin_user, db_session)
        assert d["version"] == 1
        assert d["status"] == "draft"
        assert set(d["sections"].keys()) == set(FWRA_SECTIONS)

    def test_second_draft_blocked_while_one_open(self, db_session, admin_user):
        create_firm_risk_assessment(admin_user, db_session)
        with pytest.raises(HTTPException) as exc:
            create_firm_risk_assessment(admin_user, db_session)
        assert exc.value.status_code == 409

    def test_approve_blocked_on_short_reasoning(self, db_session, admin_user):
        d = create_firm_risk_assessment(admin_user, db_session)
        sections = {k: dict(GOOD_SECTION) for k in FWRA_SECTIONS}
        sections["geography"] = {"risk_level": "high", "reasoning": "Too short.", "mitigations": ""}
        _fill_fwra_sections(db_session, admin_user, d["id"], sections)
        with pytest.raises(HTTPException) as exc:
            approve_firm_risk_assessment(d["id"], admin_user, db_session)
        assert exc.value.status_code == 400
        problems = exc.value.detail["problems"]
        assert any("geography" in p and "50 characters" in p for p in problems)

    def test_approve_blocked_without_acknowledgements(self, db_session, admin_user):
        d = create_firm_risk_assessment(admin_user, db_session)
        update_firm_risk_assessment(
            d["id"],
            FirmRAUpdateRequest(sections={k: dict(GOOD_SECTION) for k in FWRA_SECTIONS}),
            admin_user, db_session,
        )
        with pytest.raises(HTTPException) as exc:
            approve_firm_risk_assessment(d["id"], admin_user, db_session)
        problems = exc.value.detail["problems"]
        assert any("sectoral" in p for p in problems)
        assert any("national" in p for p in problems)

    def test_approve_blocked_on_missing_risk_level(self, db_session, admin_user):
        d = create_firm_risk_assessment(admin_user, db_session)
        sections = {k: dict(GOOD_SECTION) for k in FWRA_SECTIONS}
        sections["customers"] = {"risk_level": "", "reasoning": GOOD_SECTION["reasoning"], "mitigations": ""}
        _fill_fwra_sections(db_session, admin_user, d["id"], sections)
        with pytest.raises(HTTPException) as exc:
            approve_firm_risk_assessment(d["id"], admin_user, db_session)
        assert any("customers" in p and "risk level" in p for p in exc.value.detail["problems"])

    def test_approve_sets_review_date_and_supersedes_prior(self, db_session, admin_user):
        # v1: fill and approve.
        v1 = create_firm_risk_assessment(admin_user, db_session)
        _fill_fwra_sections(db_session, admin_user, v1["id"])
        approved = approve_firm_risk_assessment(v1["id"], admin_user, db_session)
        assert approved["status"] == "approved"
        assert approved["approved_by_id"] == admin_user.id
        assert approved["next_review_due"] == _add_months(date.today(), 12).isoformat()

        # v2: carries forward v1 content, approval supersedes v1.
        v2 = create_firm_risk_assessment(admin_user, db_session)
        assert v2["version"] == 2
        assert v2["sections"]["customers"]["reasoning"] == GOOD_SECTION["reasoning"]
        _fill_fwra_sections(db_session, admin_user, v2["id"])
        approve_firm_risk_assessment(v2["id"], admin_user, db_session)

        state = get_firm_risk_assessment(admin_user, db_session)
        assert state["current"]["version"] == 2
        v1_row = db_session.query(FirmRiskAssessment).filter_by(id=v1["id"]).first()
        assert v1_row.status == FirmRAStatus.SUPERSEDED
        assert len(state["history"]) == 2

    def test_approved_version_is_immutable(self, db_session, admin_user):
        v1 = create_firm_risk_assessment(admin_user, db_session)
        _fill_fwra_sections(db_session, admin_user, v1["id"])
        approve_firm_risk_assessment(v1["id"], admin_user, db_session)
        with pytest.raises(HTTPException) as exc:
            update_firm_risk_assessment(v1["id"], FirmRAUpdateRequest(), admin_user, db_session)
        assert exc.value.status_code == 400

    def test_overdue_review_flagged(self, db_session, admin_user):
        v1 = create_firm_risk_assessment(admin_user, db_session)
        _fill_fwra_sections(db_session, admin_user, v1["id"])
        approve_firm_risk_assessment(v1["id"], admin_user, db_session)
        row = db_session.query(FirmRiskAssessment).filter_by(id=v1["id"]).first()
        row.next_review_due = date(2020, 1, 1)
        db_session.commit()
        state = get_firm_risk_assessment(admin_user, db_session)
        assert state["review_overdue"] is True
        assert "01/01/2020" in state["review_overdue_message"]

    def test_export_returns_structured_json(self, db_session, admin_user):
        v1 = create_firm_risk_assessment(admin_user, db_session)
        out = export_firm_risk_assessment(v1["id"], admin_user, db_session)
        assert out["assessment"]["id"] == v1["id"]
        assert "regulation_18" in out["regulatory_basis"]


# ---------------------------------------------------------------------------
# CMRA lifecycle
# ---------------------------------------------------------------------------

class TestCMRA:
    def _create(self, db, user, matter, atype="matter", scores=None, reg28=None, flags=None):
        payload = CMRACreateRequest(
            assessment_type=atype,
            factors=_factors(scores or {}),
            reg28_considerations=reg28 if reg28 is not None else dict(REG28_OK),
            context_flags=flags or {},
        )
        return create_matter_risk_assessment(matter.id, payload, user, db)

    def test_create_draft_computes_rating(self, db_session, analyst_user, sample_matter):
        d = self._create(db_session, analyst_user, sample_matter, scores={"client": 3})
        assert d["status"] == "draft"
        assert d["overall_rating"] in ("medium", "high")

    def test_invalid_score_rejected(self, db_session, analyst_user, sample_matter):
        payload = CMRACreateRequest(
            assessment_type="matter",
            factors={"client": {"score": 5, "reasoning": "x"}},
        )
        with pytest.raises(HTTPException) as exc:
            create_matter_risk_assessment(sample_matter.id, payload, analyst_user, db_session)
        assert exc.value.status_code == 422

    def test_complete_blocked_on_missing_reasoning(self, db_session, analyst_user, sample_matter):
        payload = CMRACreateRequest(
            assessment_type="matter",
            factors={k: {"score": 1, "reasoning": ""} for k in CMRA_FACTORS},
            reg28_considerations=dict(REG28_OK),
        )
        d = create_matter_risk_assessment(sample_matter.id, payload, analyst_user, db_session)
        with pytest.raises(HTTPException) as exc:
            complete_matter_risk_assessment(sample_matter.id, d["id"], analyst_user, db_session)
        assert exc.value.status_code == 400
        assert any("tick-box" in p for p in exc.value.detail["problems"])

    def test_complete_blocked_on_missing_reg28(self, db_session, analyst_user, sample_matter):
        d = self._create(db_session, analyst_user, sample_matter, reg28={})
        with pytest.raises(HTTPException) as exc:
            complete_matter_risk_assessment(sample_matter.id, d["id"], analyst_user, db_session)
        problems = exc.value.detail["problems"]
        assert any("purpose of the matter" in p for p in problems)
        assert any("size of the transaction" in p for p in problems)
        assert any("regularity and duration" in p for p in problems)

    @pytest.mark.parametrize("scores,expected_rating,months", [
        ({}, "low", 24),
        ({"client": 2, "service_matter": 2, "geography": 2}, "medium", 12),
        ({k: 3 for k in CMRA_FACTORS}, "high", 6),
    ])
    def test_review_due_cadence_by_rating(self, db_session, analyst_user, sample_matter,
                                          scores, expected_rating, months):
        d = self._create(db_session, analyst_user, sample_matter, scores=scores)
        done = complete_matter_risk_assessment(sample_matter.id, d["id"], analyst_user, db_session)
        assert done["overall_rating"] == expected_rating
        assert done["review_due"] == _add_months(date.today(), months).isoformat()

    def test_completion_supersedes_prior_of_same_type(self, db_session, analyst_user, sample_matter):
        d1 = self._create(db_session, analyst_user, sample_matter)
        complete_matter_risk_assessment(sample_matter.id, d1["id"], analyst_user, db_session)
        d2 = self._create(db_session, analyst_user, sample_matter, scores={"client": 2})
        complete_matter_risk_assessment(sample_matter.id, d2["id"], analyst_user, db_session)

        row1 = db_session.query(ClientMatterRiskAssessment).filter_by(id=d1["id"]).first()
        row2 = db_session.query(ClientMatterRiskAssessment).filter_by(id=d2["id"]).first()
        assert row1.status == CMRAStatus.SUPERSEDED
        assert row2.status == CMRAStatus.COMPLETED

        listing = list_matter_risk_assessments(sample_matter.id, analyst_user, db_session)
        assert listing["current"]["matter"]["id"] == d2["id"]
        assert len(listing["assessments"]) == 2

    def test_update_recomputes_edd(self, db_session, analyst_user, sample_matter):
        d = self._create(db_session, analyst_user, sample_matter)
        assert d["edd_required"] is False
        updated = update_matter_risk_assessment(
            sample_matter.id, d["id"],
            CMRAUpdateRequest(context_flags={"client_is_pep": True}),
            analyst_user, db_session,
        )
        assert updated["edd_required"] is True
        assert any("PEP" in t for t in updated["edd_triggers"])

    def test_second_draft_of_same_type_blocked(self, db_session, analyst_user, sample_matter):
        self._create(db_session, analyst_user, sample_matter)
        with pytest.raises(HTTPException) as exc:
            self._create(db_session, analyst_user, sample_matter)
        assert exc.value.status_code == 409
        # A draft of the OTHER type is fine.
        d = self._create(db_session, analyst_user, sample_matter, atype="client")
        assert d["assessment_type"] == "client"

    def test_blocking_gate_requires_both_types_completed(self, db_session, analyst_user, sample_matter):
        assert matter_has_completed_cmra(db_session, sample_matter.id) is False
        dm = self._create(db_session, analyst_user, sample_matter, atype="matter")
        complete_matter_risk_assessment(sample_matter.id, dm["id"], analyst_user, db_session)
        # Matter-level alone is not enough — reg 28(12) requires both.
        assert matter_has_completed_cmra(db_session, sample_matter.id) is False
        dc = self._create(db_session, analyst_user, sample_matter, atype="client")
        complete_matter_risk_assessment(sample_matter.id, dc["id"], analyst_user, db_session)
        assert matter_has_completed_cmra(db_session, sample_matter.id) is True

    def test_overdue_list_scoped_to_accessible_matters(self, db_session, analyst_user, admin_user, sample_matter):
        d = self._create(db_session, analyst_user, sample_matter)
        complete_matter_risk_assessment(sample_matter.id, d["id"], analyst_user, db_session)
        row = db_session.query(ClientMatterRiskAssessment).filter_by(id=d["id"]).first()
        row.review_due = date(2020, 1, 1)
        db_session.commit()

        out = list_overdue_risk_assessments(admin_user, db_session)
        assert out["count"] == 1
        assert out["overdue"][0]["matter_reference"] == "RA-TEST-001"
        assert out["overdue"][0]["days_overdue"] > 0

        # Another analyst with no link to the matter — but matter is
        # unassigned so policy still grants access.
        other = User(email="other@test.com", full_name="Other", role=UserRole.ANALYST, hashed_password="h")
        db_session.add(other)
        db_session.commit()
        out_other = list_overdue_risk_assessments(other, db_session)
        assert out_other["count"] == 1

        # Assign the matter to the original analyst — the other analyst
        # loses visibility.
        sample_matter.assigned_analyst_id = analyst_user.id
        db_session.commit()
        assert list_overdue_risk_assessments(other, db_session)["count"] == 0
        assert list_overdue_risk_assessments(analyst_user, db_session)["count"] == 1
