"""
Unit/integration tests for the MLRO workbench
(app/models/mlro.py + app/api/v1/endpoints/mlro.py).

Covers:
  * UK working-day deadline calculator (Friday filing, weekend spanning)
  * Access control logic at the function level — the reporter can never
    see report status / MLRO notes (POCA s.333A tipping-off control);
    only admin passes the role checker
  * Decision validation — rationale required (>= 30 chars) for BOTH
    outcomes (LSAG 11.7)
  * DAML state machine transitions and the matter-freeze helper

Run with: pytest tests/test_mlro.py -v
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — register all existing mappers (Matter relationships)
from app.db.base import Base
from app.models.user import User, UserRole
from app.models.matter import Matter, MatterStatus, RiskRating, TransactionType
from app.models.mlro import (
    DamlStatus,
    InternalReport,
    InternalReportStatus,
    PolicyStatus,
    SarRecord,
    add_uk_working_days,
)
from app.api.dependencies.auth import require_admin, require_analyst
from app.api.v1.endpoints import mlro as mlro_ep
from app.api.v1.endpoints.mlro import (
    DamlOutcome,
    InternalReportCreate,
    PolicyCreate,
    ReportDecision,
    SarCreate,
    TrainingCreate,
    acknowledge_policy,
    approve_policy,
    create_internal_report,
    create_policy,
    create_training,
    decide_report,
    get_report,
    list_my_reports,
    list_reports,
    matter_freeze_status,
    mlro_dashboard,
    record_daml_outcome,
    record_sar_filing,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    # Wipe MLRO tables between tests so counts stay deterministic.
    for table in ("sar_records", "internal_reports", "training_records",
                  "policy_documents", "audit_logs"):
        from sqlalchemy import text
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()
    session.close()


@pytest.fixture
def users(db):
    """One admin (MLRO stand-in) and one analyst (reporter)."""
    admin = db.query(User).filter(User.email == "mlro@test.com").first()
    analyst = db.query(User).filter(User.email == "feeearner@test.com").first()
    if not admin:
        admin = User(email="mlro@test.com", hashed_password="x",
                     full_name="MLRO Admin", role=UserRole.ADMIN, is_active=True)
        analyst = User(email="feeearner@test.com", hashed_password="x",
                       full_name="Fee Earner", role=UserRole.ANALYST, is_active=True)
        db.add_all([admin, analyst])
        db.commit()
    return admin, analyst


@pytest.fixture
def matter(db, users):
    m = db.query(Matter).filter(Matter.reference_number == "MLRO-TEST-001").first()
    if not m:
        admin, _ = users
        m = Matter(
            reference_number="MLRO-TEST-001",
            client_name="Test Client Ltd",
            transaction_type=TransactionType.PROPERTY_PURCHASE,
            target_amount=500000,
            status=MatterStatus.UNDER_REVIEW,
            risk_rating=RiskRating.MEDIUM,
            created_by_id=admin.id,
        )
        db.add(m)
        db.commit()
    return m


def _submit_report(db, users, matter=None):
    _, analyst = users
    payload = InternalReportCreate(
        matter_id=matter.id if matter else None,
        subject_summary="Client attempting large third-party cash payment",
        suspicion_details="Unexplained third-party funds of £150k from an unrelated overseas company.",
    )
    return create_internal_report(payload, current_user=analyst, db=db)


# ---------------------------------------------------------------------------
# Working-day calculator
# ---------------------------------------------------------------------------

class TestWorkingDayCalculator:
    def test_friday_filing_seven_working_days(self):
        # Friday 06/03/2026. Counting starts Monday: 7 working days end
        # Tuesday 17/03/2026.
        friday = datetime(2026, 3, 6, 14, 0, tzinfo=timezone.utc)
        deadline = add_uk_working_days(friday, 7)
        assert deadline.date() == datetime(2026, 3, 17).date()
        assert deadline.weekday() == 1  # Tuesday

    def test_monday_filing_spans_one_weekend(self):
        # Monday 02/03/2026 + 7 working days -> Wednesday 11/03/2026.
        monday = datetime(2026, 3, 2, tzinfo=timezone.utc)
        deadline = add_uk_working_days(monday, 7)
        assert deadline.date() == datetime(2026, 3, 11).date()

    def test_saturday_filing_starts_next_working_day(self):
        # Saturday 07/03/2026: first counted day is Monday 09/03.
        saturday = datetime(2026, 3, 7, tzinfo=timezone.utc)
        assert add_uk_working_days(saturday, 1).date() == datetime(2026, 3, 9).date()

    def test_result_never_lands_on_weekend(self):
        start = datetime(2026, 3, 2, tzinfo=timezone.utc)
        for n in range(1, 30):
            assert add_uk_working_days(start, n).weekday() < 5

    def test_zero_days_returns_start(self):
        start = datetime(2026, 3, 6, tzinfo=timezone.utc)
        assert add_uk_working_days(start, 0) == start

    def test_negative_days_rejected(self):
        with pytest.raises(ValueError):
            add_uk_working_days(datetime(2026, 3, 6, tzinfo=timezone.utc), -1)


# ---------------------------------------------------------------------------
# Access control — tipping-off (s.333A)
# ---------------------------------------------------------------------------

class TestAccessControl:
    def test_any_authenticated_user_can_create_report(self, db, users, matter):
        result = _submit_report(db, users, matter)
        assert result["id"] > 0
        # Receipt confirms submission WITHOUT any status detail.
        assert "status" not in result
        assert "mlro_notes" not in result

    def test_my_reports_never_exposes_status_or_mlro_fields(self, db, users, matter):
        _, analyst = users
        _submit_report(db, users, matter)
        rows = list_my_reports(current_user=analyst, db=db)
        assert len(rows) >= 1
        for row in rows:
            # s.333A: the reporter sees receipt info only.
            assert "status" not in row
            assert "mlro_notes" not in row
            assert "decision_rationale" not in row
            assert "suspicion_details" not in row
            assert row["submitted_at"] is not None
            assert row["matter_reference"] == "MLRO-TEST-001"

    def test_my_reports_only_shows_own_reports(self, db, users, matter):
        admin, analyst = users
        _submit_report(db, users, matter)
        assert list_my_reports(current_user=admin, db=db) == []

    def test_role_checker_blocks_non_admin(self, users):
        """require_admin (MLRO stand-in) rejects analysts and partners."""
        _, analyst = users
        with pytest.raises(HTTPException) as exc:
            asyncio.run(require_admin(current_user=analyst))
        assert exc.value.status_code == 403

    def test_role_checker_allows_admin(self, users):
        admin, _ = users
        assert asyncio.run(require_admin(current_user=admin)) is admin

    def test_analyst_passes_analyst_checker_but_not_admin(self, users):
        _, analyst = users
        assert asyncio.run(require_analyst(current_user=analyst)) is analyst

    def test_report_audit_row_not_linked_to_matter(self, db, users, matter):
        """The audit entry for a report must not appear in the matter
        audit trail (which the client team can read)."""
        from app.models.audit import AuditLog
        result = _submit_report(db, users, matter)
        row = (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "internal_report",
                    AuditLog.entity_id == result["id"])
            .first()
        )
        assert row is not None
        assert row.matter_id is None


# ---------------------------------------------------------------------------
# Decision validation — LSAG 11.7
# ---------------------------------------------------------------------------

class TestDecisionValidation:
    def test_rationale_required_for_no_sar(self):
        with pytest.raises(ValidationError):
            ReportDecision(outcome="no_sar", rationale="too short")

    def test_rationale_required_for_sar(self):
        with pytest.raises(ValidationError):
            ReportDecision(outcome="sar", rationale="brief")

    def test_outcome_must_be_sar_or_no_sar(self):
        with pytest.raises(ValidationError):
            ReportDecision(outcome="maybe", rationale="x" * 40)

    def test_whitespace_padded_rationale_rejected_at_endpoint(self, db, users, matter):
        admin, _ = users
        report_id = _submit_report(db, users, matter)["id"]
        padded = ("short " + " " * 40)  # >30 raw chars, <30 after strip
        decision = ReportDecision.model_construct(
            outcome="no_sar", rationale=padded,
            privilege_considered=False, privilege_notes=None, mlro_notes=None,
        )
        with pytest.raises(HTTPException) as exc:
            decide_report(report_id, decision, current_user=admin, db=db)
        assert exc.value.status_code == 400

    def test_no_sar_decision_is_documented(self, db, users, matter):
        """LSAG 11.7 — the decision NOT to file is fully recorded."""
        admin, _ = users
        report_id = _submit_report(db, users, matter)["id"]
        rationale = "Funds fully traced to a verified property sale; no suspicion remains."
        out = decide_report(
            report_id,
            ReportDecision(outcome="no_sar", rationale=rationale,
                           privilege_considered=True,
                           privilege_notes="No LPP material involved."),
            current_user=admin, db=db,
        )
        assert out["status"] == "no_sar_decision"
        r = db.get(InternalReport, report_id)
        assert r.decision_rationale == rationale
        assert r.decided_by_id == admin.id
        assert r.decided_at is not None
        assert r.privilege_considered is True

    def test_cannot_decide_twice(self, db, users, matter):
        admin, _ = users
        report_id = _submit_report(db, users, matter)["id"]
        decision = ReportDecision(
            outcome="no_sar",
            rationale="Explained by documented inheritance with grant of probate on file.",
        )
        decide_report(report_id, decision, current_user=admin, db=db)
        with pytest.raises(HTTPException) as exc:
            decide_report(report_id, decision, current_user=admin, db=db)
        assert exc.value.status_code == 400

    def test_sar_recording_requires_prior_decision(self, db, users, matter):
        admin, _ = users
        report_id = _submit_report(db, users, matter)["id"]
        with pytest.raises(HTTPException) as exc:
            record_sar_filing(
                report_id, SarCreate(sar_reference="NCA-REF-1"),
                current_user=admin, db=db,
            )
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# DAML state machine
# ---------------------------------------------------------------------------

def _file_sar_with_daml(db, users, matter):
    admin, _ = users
    report_id = _submit_report(db, users, matter)["id"]
    decide_report(
        report_id,
        ReportDecision(outcome="sar",
                       rationale="Suspicion of laundering via layered third-party payments."),
        current_user=admin, db=db,
    )
    sar = record_sar_filing(
        report_id,
        SarCreate(sar_reference="NCA-2026-000123", daml_requested=True),
        current_user=admin, db=db,
    )
    return report_id, sar


class TestDamlStateMachine:
    def test_filing_with_daml_starts_notice_clock(self, db, users, matter):
        admin, _ = users
        report_id, sar = _file_sar_with_daml(db, users, matter)
        assert sar["daml_status"] == "awaiting_consent"
        assert sar["consent_deadline"] is not None
        row = db.get(SarRecord, sar["id"])
        expected = add_uk_working_days(row.daml_filed_at, 7)
        assert row.consent_deadline == expected
        # Report itself is now sar_filed.
        r = db.get(InternalReport, report_id)
        assert r.status == InternalReportStatus.SAR_FILED

    def test_filing_without_daml_has_no_clock(self, db, users, matter):
        admin, _ = users
        report_id = _submit_report(db, users, matter)["id"]
        decide_report(
            report_id,
            ReportDecision(outcome="sar",
                           rationale="Suspicion of laundering via unexplained overseas funds."),
            current_user=admin, db=db,
        )
        sar = record_sar_filing(report_id, SarCreate(sar_reference="NCA-REF-2"),
                                current_user=admin, db=db)
        assert sar["daml_status"] == "none"
        assert sar["consent_deadline"] is None

    def test_consent_granted_transition(self, db, users, matter):
        admin, _ = users
        _, sar = _file_sar_with_daml(db, users, matter)
        out = record_daml_outcome(sar["id"], DamlOutcome(status="consent_granted"),
                                  current_user=admin, db=db)
        assert out["daml_status"] == "consent_granted"

    def test_refusal_starts_31_calendar_day_moratorium(self, db, users, matter):
        admin, _ = users
        _, sar = _file_sar_with_daml(db, users, matter)
        out = record_daml_outcome(
            sar["id"], DamlOutcome(status="consent_refused_moratorium"),
            current_user=admin, db=db,
        )
        assert out["daml_status"] == "consent_refused_moratorium"
        row = db.get(SarRecord, sar["id"])
        delta = row.moratorium_end - datetime.now(timezone.utc).replace(tzinfo=row.moratorium_end.tzinfo)
        assert 30 <= delta.days <= 31  # 31 calendar days, allow test runtime skew

    def test_cannot_grant_after_refusal(self, db, users, matter):
        admin, _ = users
        _, sar = _file_sar_with_daml(db, users, matter)
        record_daml_outcome(sar["id"], DamlOutcome(status="consent_refused_moratorium"),
                            current_user=admin, db=db)
        with pytest.raises(HTTPException) as exc:
            record_daml_outcome(sar["id"], DamlOutcome(status="consent_granted"),
                                current_user=admin, db=db)
        assert exc.value.status_code == 400

    def test_moratorium_expiry_blocked_before_31_days(self, db, users, matter):
        admin, _ = users
        _, sar = _file_sar_with_daml(db, users, matter)
        record_daml_outcome(sar["id"], DamlOutcome(status="consent_refused_moratorium"),
                            current_user=admin, db=db)
        with pytest.raises(HTTPException) as exc:
            record_daml_outcome(sar["id"], DamlOutcome(status="moratorium_expired"),
                                current_user=admin, db=db)
        assert exc.value.status_code == 400

    def test_moratorium_expiry_allowed_after_31_days(self, db, users, matter):
        admin, _ = users
        _, sar = _file_sar_with_daml(db, users, matter)
        record_daml_outcome(sar["id"], DamlOutcome(status="consent_refused_moratorium"),
                            current_user=admin, db=db)
        row = db.get(SarRecord, sar["id"])
        row.moratorium_end = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
        out = record_daml_outcome(sar["id"], DamlOutcome(status="moratorium_expired"),
                                  current_user=admin, db=db)
        assert out["daml_status"] == "moratorium_expired"

    def test_cannot_transition_from_none(self, db, users, matter):
        admin, _ = users
        report_id = _submit_report(db, users, matter)["id"]
        decide_report(
            report_id,
            ReportDecision(outcome="sar",
                           rationale="Suspicion of laundering; SAR prepared for portal filing."),
            current_user=admin, db=db,
        )
        sar = record_sar_filing(report_id, SarCreate(sar_reference="NCA-REF-3"),
                                current_user=admin, db=db)
        with pytest.raises(HTTPException) as exc:
            record_daml_outcome(sar["id"], DamlOutcome(status="consent_granted"),
                                current_user=admin, db=db)
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Matter freeze helper (DAML pending → work must not proceed)
# ---------------------------------------------------------------------------

class TestMatterFreeze:
    def test_frozen_while_awaiting_consent_with_generic_reason(self, db, users, matter):
        _, analyst = users
        _file_sar_with_daml(db, users, matter)
        out = matter_freeze_status(matter.id, current_user=analyst, db=db)
        assert out["frozen"] is True
        # Tipping-off control: the reason must not mention SAR/DAML/NCA.
        for word in ("SAR", "DAML", "NCA", "suspicious", "moratorium"):
            assert word.lower() not in out["reason"].lower()

    def test_frozen_during_active_moratorium(self, db, users, matter):
        admin, analyst = users
        _, sar = _file_sar_with_daml(db, users, matter)
        record_daml_outcome(sar["id"], DamlOutcome(status="consent_refused_moratorium"),
                            current_user=admin, db=db)
        out = matter_freeze_status(matter.id, current_user=analyst, db=db)
        assert out["frozen"] is True

    def test_unfrozen_after_consent_granted(self, db, users, matter):
        admin, analyst = users
        _, sar = _file_sar_with_daml(db, users, matter)
        record_daml_outcome(sar["id"], DamlOutcome(status="consent_granted"),
                            current_user=admin, db=db)
        out = matter_freeze_status(matter.id, current_user=analyst, db=db)
        assert out["frozen"] is False

    def test_unfrozen_with_no_reports(self, db, users, matter):
        _, analyst = users
        out = matter_freeze_status(matter.id, current_user=analyst, db=db)
        assert out == {"frozen": False, "reason": None}


# ---------------------------------------------------------------------------
# MLRO queue / dashboard / policies sanity
# ---------------------------------------------------------------------------

class TestMlroWorkbench:
    def test_admin_queue_shows_status_and_opening_marks_under_review(self, db, users, matter):
        admin, _ = users
        report_id = _submit_report(db, users, matter)["id"]
        rows = list_reports(status=None, matter_id=None, current_user=admin, db=db)
        assert any(r["id"] == report_id and r["status"] == "received" for r in rows)
        detail = get_report(report_id, current_user=admin, db=db)
        assert detail["status"] == "under_review"
        assert detail["suspicion_details"]
        assert isinstance(detail["matter_context"], dict)

    def test_dashboard_counts(self, db, users, matter):
        admin, _ = users
        _, sar = _file_sar_with_daml(db, users, matter)
        _submit_report(db, users, matter)

        # A fresh 7-WORKING-day deadline is 9+ calendar days out, so it
        # does not yet appear in the 7-calendar-day lookahead.
        out = mlro_dashboard(current_user=admin, db=db)
        assert out["report_counts"]["sar_filed"] == 1
        assert out["open_reports"] >= 1
        assert out["daml_deadlines_within_7_days"] == []

        # Bring the deadline within the lookahead window.
        row = db.get(SarRecord, sar["id"])
        row.consent_deadline = datetime.now(timezone.utc) + timedelta(days=2)
        db.commit()
        out = mlro_dashboard(current_user=admin, db=db)
        assert len(out["daml_deadlines_within_7_days"]) == 1
        assert out["daml_deadlines_within_7_days"][0]["overdue"] is False

    def test_policy_approve_supersede_and_acknowledge(self, db, users):
        admin, analyst = users
        v1 = create_policy(PolicyCreate(title="AML Policy", version="1.0"),
                           current_user=admin, db=db)
        approve_policy(v1["id"], current_user=admin, db=db)
        v2 = create_policy(PolicyCreate(title="AML Policy", version="2.0"),
                           current_user=admin, db=db)
        approved = approve_policy(v2["id"], current_user=admin, db=db)
        assert approved["status"] == "approved"
        from app.models.mlro import PolicyDocument
        old = db.get(PolicyDocument, v1["id"])
        assert old.status == PolicyStatus.SUPERSEDED

        out = acknowledge_policy(v2["id"], current_user=analyst, db=db)
        assert out["acknowledged"] is True
        # Idempotent.
        acknowledge_policy(v2["id"], current_user=analyst, db=db)
        row = db.get(PolicyDocument, v2["id"])
        assert len(row.acknowledgements) == 1

    def test_cannot_acknowledge_draft_policy(self, db, users):
        admin, analyst = users
        draft = create_policy(PolicyCreate(title="Draft Policy", version="0.1"),
                              current_user=admin, db=db)
        with pytest.raises(HTTPException) as exc:
            acknowledge_policy(draft["id"], current_user=analyst, db=db)
        assert exc.value.status_code == 400

    def test_training_create(self, db, users):
        admin, analyst = users
        t = create_training(
            TrainingCreate(
                user_id=analyst.id,
                course_name="AML Annual Refresher",
                provider="SRA-approved provider",
                completed_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            ),
            current_user=admin, db=db,
        )
        assert t["user_name"] == "Fee Earner"
