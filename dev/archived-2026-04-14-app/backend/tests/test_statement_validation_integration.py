"""
Integration tests for Statement Validation API endpoints.

Tests the full flow:
  1. Create tables via SQLAlchemy
  2. Insert a StatementValidation + flags + transactions
  3. Hit API endpoints to verify CRUD + admin override

Run with: pytest tests/test_statement_validation_integration.py -v
"""
import pytest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.statement_validation import (
    StatementValidation, StatementValidationFlag, StatementValidationTransaction,
    ValidationStatus, FlagSeverity,
)
from app.models.matter import Matter, MatterStatus, RiskRating, TransactionType
from app.models.audit import AuditLog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_engine():
    """In-memory SQLite for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_matter(db_session):
    """Create a test matter via raw SQL to satisfy all NOT NULL constraints."""
    from sqlalchemy import text
    # Create a user first (required FK)
    db_session.execute(text(
        "INSERT OR IGNORE INTO users (id, email, full_name, role, hashed_password) "
        "VALUES (1, 'test@test.com', 'Test User', 'ANALYST', 'hash')"
    ))
    db_session.execute(text(
        "INSERT OR IGNORE INTO matters (id, reference_number, client_name, transaction_type, "
        "target_amount, status, risk_rating, created_by_id) "
        "VALUES (99, 'TEST-001', 'Test Client', 'PROPERTY_PURCHASE', "
        "500000.0, 'DRAFT', 'MEDIUM', 1)"
    ))
    db_session.commit()
    return db_session.query(Matter).filter(Matter.id == 99).first()


# ---------------------------------------------------------------------------
# Model layer tests
# ---------------------------------------------------------------------------

class TestStatementValidationModel:
    def test_create_validation(self, db_session, sample_matter):
        sv = StatementValidation(
            matter_id=99,
            filename="test_statement.csv",
            file_hash_sha256="abc123def456" * 4,
            file_size_bytes=1024,
            mime_type="text/csv",
            authenticity_score=82.5,
            status=ValidationStatus.TRUSTED,
            identified_bank_template="HSBC",
        )
        db_session.add(sv)
        db_session.commit()

        assert sv.id is not None
        assert sv.matter_id == 99
        assert sv.status == ValidationStatus.TRUSTED

    def test_create_with_flags(self, db_session, sample_matter):
        sv = StatementValidation(
            matter_id=99,
            filename="flagged.csv",
            file_hash_sha256="ffffffff" * 8,
            file_size_bytes=500,
            authenticity_score=35.0,
            status=ValidationStatus.HIGH_RISK,
            blocked=True,
        )
        db_session.add(sv)
        db_session.flush()

        flag1 = StatementValidationFlag(
            validation_id=sv.id,
            pipeline_stage="file_integrity",
            code="FILE_TOO_SMALL",
            severity=FlagSeverity.CRITICAL,
            message="File is suspiciously small",
        )
        flag2 = StatementValidationFlag(
            validation_id=sv.id,
            pipeline_stage="anomaly_check",
            code="ROUND_NUMBER_BIAS",
            severity=FlagSeverity.MEDIUM,
            message="70% round numbers",
        )
        db_session.add_all([flag1, flag2])
        db_session.commit()

        assert len(sv.flags) == 2
        assert sv.flags[0].code in ("FILE_TOO_SMALL", "ROUND_NUMBER_BIAS")

    def test_create_with_transactions(self, db_session, sample_matter):
        sv = StatementValidation(
            matter_id=99,
            filename="txns.csv",
            file_hash_sha256="11111111" * 8,
            file_size_bytes=2048,
            authenticity_score=90.0,
            status=ValidationStatus.TRUSTED,
        )
        db_session.add(sv)
        db_session.flush()

        txn = StatementValidationTransaction(
            validation_id=sv.id,
            date="01/01/2025",
            description="SALARY",
            amount=3500.0,
            direction="credit",
            balance=3500.0,
        )
        db_session.add(txn)
        db_session.commit()

        assert len(sv.transactions) == 1
        assert sv.transactions[0].amount == 3500.0

    def test_to_dict(self, db_session, sample_matter):
        sv = StatementValidation(
            matter_id=99,
            filename="dict_test.csv",
            file_hash_sha256="22222222" * 8,
            file_size_bytes=512,
            authenticity_score=55.0,
            status=ValidationStatus.REVIEW,
        )
        db_session.add(sv)
        db_session.commit()

        d = sv.to_dict()
        assert d["filename"] == "dict_test.csv"
        assert d["status"] == "Review"
        assert d["authenticity_score"] == 55.0
        assert isinstance(d["flags"], list)

    def test_admin_override(self, db_session, sample_matter):
        sv = StatementValidation(
            matter_id=99,
            filename="override.csv",
            file_hash_sha256="33333333" * 8,
            file_size_bytes=1000,
            authenticity_score=30.0,
            status=ValidationStatus.HIGH_RISK,
            blocked=True,
        )
        db_session.add(sv)
        db_session.commit()

        # Simulate admin override
        sv.admin_override = True
        sv.admin_override_by = "admin_user"
        sv.admin_override_rationale = "Verified with client directly"
        sv.blocked = False
        db_session.commit()

        assert sv.admin_override is True
        assert sv.blocked is False

    def test_cascade_delete(self, db_session, sample_matter):
        sv = StatementValidation(
            matter_id=99,
            filename="cascade.csv",
            file_hash_sha256="44444444" * 8,
            file_size_bytes=1000,
            authenticity_score=50.0,
            status=ValidationStatus.REVIEW,
        )
        db_session.add(sv)
        db_session.flush()

        flag = StatementValidationFlag(
            validation_id=sv.id,
            pipeline_stage="test",
            code="TEST_FLAG",
            severity=FlagSeverity.LOW,
            message="Test flag",
        )
        txn = StatementValidationTransaction(
            validation_id=sv.id,
            date="01/01/2025",
            description="Test",
            amount=100.0,
            direction="credit",
        )
        db_session.add_all([flag, txn])
        db_session.commit()

        sv_id = sv.id
        db_session.delete(sv)
        db_session.commit()

        # Verify cascade deleted children
        remaining_flags = db_session.query(StatementValidationFlag).filter_by(validation_id=sv_id).all()
        remaining_txns = db_session.query(StatementValidationTransaction).filter_by(validation_id=sv_id).all()
        assert len(remaining_flags) == 0
        assert len(remaining_txns) == 0


# ---------------------------------------------------------------------------
# Pipeline → DB integration test
# ---------------------------------------------------------------------------

class TestPipelineToDbIntegration:
    def test_pipeline_result_to_db(self, db_session, sample_matter):
        """Run the pipeline and persist results to DB."""
        from app.services.statement_validation_pipeline import StatementValidationPipeline

        pipeline = StatementValidationPipeline()

        # Build a simple CSV
        csv_content = (
            "Date,Description,Amount,Balance\n"
            "01/01/2025,SALARY,3500.00,3500.00\n"
            "05/01/2025,RENT,-1200.00,2300.00\n"
            "10/01/2025,GROCERIES,-85.50,2214.50\n"
        ).encode("utf-8")

        result = pipeline.validate_statement(csv_content, bank_hint=None)

        # Map to DB model
        status_map = {"Trusted": ValidationStatus.TRUSTED, "Review": ValidationStatus.REVIEW, "HighRisk": ValidationStatus.HIGH_RISK}
        sev_map = {"info": FlagSeverity.INFO, "low": FlagSeverity.LOW, "medium": FlagSeverity.MEDIUM, "high": FlagSeverity.HIGH, "critical": FlagSeverity.CRITICAL}

        sv = StatementValidation(
            matter_id=99,
            filename="integration_test.csv",
            file_hash_sha256=result.file_hash_sha256,
            file_size_bytes=result.file_size_bytes,
            mime_type=result.mime_type,
            authenticity_score=result.authenticity_score,
            status=status_map.get(result.status, ValidationStatus.REVIEW),
            identified_bank_template=result.identified_bank_template,
            file_integrity_result=result.file_integrity_result,
            template_match_result=result.template_match_result,
            extraction_result=result.extraction_result,
            math_check_result=result.math_check_result,
            anomaly_check_result=result.anomaly_check_result,
            blocked=(result.status in ("Review", "HighRisk")),
        )
        db_session.add(sv)
        db_session.flush()

        for f in result.flags:
            svf = StatementValidationFlag(
                validation_id=sv.id,
                pipeline_stage=f.pipeline_stage,
                code=f.code,
                severity=sev_map.get(f.severity, FlagSeverity.MEDIUM),
                message=f.message,
                details=f.details,
            )
            db_session.add(svf)

        for et in result.extracted_transactions:
            svt = StatementValidationTransaction(
                validation_id=sv.id,
                date=et.date,
                description=et.description,
                amount=et.amount,
                direction=et.direction,
                balance=et.balance,
            )
            db_session.add(svt)

        db_session.commit()

        # Verify
        stored = db_session.query(StatementValidation).filter_by(id=sv.id).first()
        assert stored is not None
        assert stored.authenticity_score == result.authenticity_score
        assert len(stored.flags) == len(result.flags)
        assert len(stored.transactions) == len(result.extracted_transactions)
        
        # Verify to_dict works on persisted object
        d = stored.to_dict()
        assert d["filename"] == "integration_test.csv"
        assert d["transactions_count"] == len(result.extracted_transactions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
