"""
Unit tests for the Statement Authenticity Validation Pipeline.

Tests cover all 6 stages plus the public interface.
Run with: pytest tests/test_statement_validation.py -v
"""
import pytest
import json
import csv
import io
import hashlib
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.statement_validation_pipeline import (
    StatementValidationPipeline,
    ValidationResult,
    Flag,
    ExtractedTransaction,
    DEFAULT_CONFIG,
)


# ---------------------------------------------------------------------------
# Fixtures – synthetic bank statement data
# ---------------------------------------------------------------------------

def _make_csv_bytes(rows, headers=None):
    """Build a CSV file in memory."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    if headers:
        writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def valid_csv_statement():
    """A clean, valid CSV bank statement (HSBC-like)."""
    headers = ["Date", "Description", "Amount", "Balance", "Type"]
    rows = [
        ["01/01/2025", "SALARY FROM EMPLOYER LTD", "3500.00", "3500.00", "credit"],
        ["05/01/2025", "TESCO STORES", "-45.67", "3454.33", "debit"],
        ["10/01/2025", "DIRECT DEBIT - COUNCIL TAX", "-150.00", "3304.33", "debit"],
        ["15/01/2025", "TRANSFER IN FROM SAVINGS", "500.00", "3804.33", "credit"],
        ["20/01/2025", "AMAZON MARKETPLACE", "-89.99", "3714.34", "debit"],
        ["25/01/2025", "STANDING ORDER - RENT", "-1200.00", "2514.34", "debit"],
        ["28/01/2025", "NATWEST INTEREST", "1.23", "2515.57", "credit"],
        ["31/01/2025", "SALARY FROM EMPLOYER LTD", "3500.00", "6015.57", "credit"],
    ]
    return _make_csv_bytes(rows, headers)


@pytest.fixture
def suspicious_csv_statement():
    """A CSV with suspicious patterns: duplicates, round numbers, test transactions."""
    headers = ["Date", "Description", "Amount", "Balance"]
    rows = [
        ["01/01/2025", "Test Transaction 1", "1000.00", "1000.00"],
        ["01/01/2025", "Test Transaction 1", "1000.00", "2000.00"],
        ["02/01/2025", "Test Transaction 2", "2000.00", "4000.00"],
        ["03/01/2025", "Test Transaction 3", "500.00", "4500.00"],
        ["04/01/2025", "Payment 1", "1000.00", "5500.00"],
        ["05/01/2025", "Payment 2", "1000.00", "6500.00"],
        ["06/01/2025", "Payment 3", "1000.00", "7500.00"],
        ["07/01/2025", "Payment 4", "1000.00", "8500.00"],
        ["08/01/2025", "Payment 5", "1000.00", "9500.00"],
        ["09/01/2025", "Payment 6", "1000.00", "10500.00"],
    ]
    return _make_csv_bytes(rows, headers)


@pytest.fixture
def empty_csv():
    """An empty CSV file."""
    return b"Date,Description,Amount,Balance\n"


@pytest.fixture
def tiny_file():
    """A suspiciously tiny file."""
    return b"hi"


@pytest.fixture
def hsbc_csv_statement():
    """A CSV with HSBC identifiers."""
    headers = ["Date", "Description", "Amount", "Balance", "Sort Code", "Account Number"]
    rows = [
        ["01/01/2025", "HSBC UK Current Account - Salary", "3000.00", "3000.00", "40-01-01", "12345678"],
        ["15/01/2025", "FIRST DIRECT SAVINGS TRANSFER", "500.00", "3500.00", "40-01-01", "12345678"],
    ]
    # Add HSBC header line
    csv_str = "HSBC UK Bank Statement\n"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    csv_str += buf.getvalue()
    return csv_str.encode("utf-8")


# ---------------------------------------------------------------------------
# Pipeline instance
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline():
    return StatementValidationPipeline()


# ===========================================================================
# STAGE 1 – File Integrity
# ===========================================================================

class TestFileIntegrity:
    def test_valid_csv_passes(self, pipeline, valid_csv_statement):
        result = ValidationResult()
        pipeline._stage_file_integrity(valid_csv_statement, result)
        assert result.file_integrity_score >= 90
        assert result.file_hash_sha256 == hashlib.sha256(valid_csv_statement).hexdigest()
        assert result.mime_type == "text/csv"

    def test_tiny_file_flagged(self, pipeline, tiny_file):
        result = ValidationResult()
        pipeline._stage_file_integrity(tiny_file, result)
        assert result.file_integrity_score <= 50
        codes = [f.code for f in result.flags]
        assert "FILE_TOO_SMALL" in codes

    def test_binary_in_csv_flagged(self, pipeline):
        bad_csv = b"Date,Amount\n01/01/2025,100\x00.00\n"
        result = ValidationResult()
        pipeline._stage_file_integrity(bad_csv, result)
        codes = [f.code for f in result.flags]
        assert "BINARY_CONTENT" in codes

    def test_file_hash_computed(self, pipeline, valid_csv_statement):
        result = ValidationResult()
        pipeline._stage_file_integrity(valid_csv_statement, result)
        expected = hashlib.sha256(valid_csv_statement).hexdigest()
        assert result.file_hash_sha256 == expected


# ===========================================================================
# STAGE 2 – Template Match
# ===========================================================================

class TestTemplateMatch:
    def test_hsbc_detected(self, pipeline, hsbc_csv_statement):
        text = hsbc_csv_statement.decode("utf-8")
        result = ValidationResult()
        pipeline._stage_template_match(text, None, result)
        assert result.identified_bank_template == "HSBC"
        assert result.template_match_score >= 60

    def test_hint_confirmed(self, pipeline, hsbc_csv_statement):
        text = hsbc_csv_statement.decode("utf-8")
        result = ValidationResult()
        pipeline._stage_template_match(text, "HSBC", result)
        codes = [f.code for f in result.flags]
        assert "HINT_CONFIRMED" in codes

    def test_hint_mismatch(self, pipeline, hsbc_csv_statement):
        text = hsbc_csv_statement.decode("utf-8")
        result = ValidationResult()
        pipeline._stage_template_match(text, "Barclays", result)
        codes = [f.code for f in result.flags]
        assert "HINT_MISMATCH" in codes

    def test_no_template_match(self, pipeline):
        text = "some random text without bank identifiers"
        result = ValidationResult()
        pipeline._stage_template_match(text, None, result)
        codes = [f.code for f in result.flags]
        assert "NO_TEMPLATE_MATCH" in codes


# ===========================================================================
# STAGE 3 – Transaction Extraction
# ===========================================================================

class TestTransactionExtraction:
    def test_csv_extraction(self, pipeline, valid_csv_statement):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(valid_csv_statement, "", result)
        assert len(result.extracted_transactions) == 8
        assert result.extraction_score >= 80

    def test_empty_csv(self, pipeline, empty_csv):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(empty_csv, "", result)
        assert len(result.extracted_transactions) == 0
        codes = [f.code for f in result.flags]
        assert "NO_TRANSACTIONS" in codes

    def test_extracted_fields(self, pipeline, valid_csv_statement):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(valid_csv_statement, "", result)
        first = result.extracted_transactions[0]
        assert first.date == "01/01/2025"
        assert first.amount == 3500.0
        assert first.direction == "credit"


# ===========================================================================
# STAGE 4 – Math Checks
# ===========================================================================

class TestMathChecks:
    def test_valid_balance_passes(self, pipeline, valid_csv_statement):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(valid_csv_statement, "", result)
        pipeline._stage_math_checks(result, None, None)
        assert result.math_check_score >= 80
        codes = [f.code for f in result.flags]
        assert "BALANCE_OK" in codes or "BALANCE_MINOR_ERRORS" in codes

    def test_no_data_zero_score(self, pipeline):
        result = ValidationResult()
        result.extracted_transactions = []
        pipeline._stage_math_checks(result, None, None)
        assert result.math_check_score == 0

    def test_date_continuity(self, pipeline, valid_csv_statement):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(valid_csv_statement, "", result)
        pipeline._stage_math_checks(result, None, None)
        codes = [f.code for f in result.flags]
        assert "DATE_CONTINUITY_OK" in codes


# ===========================================================================
# STAGE 5 – Anomaly Checks
# ===========================================================================

class TestAnomalyChecks:
    def test_clean_statement_no_anomalies(self, pipeline, valid_csv_statement):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(valid_csv_statement, "", result)
        pipeline._stage_anomaly_checks(result, None, None)
        assert result.anomaly_check_score >= 70
        # Valid statement may still trigger round-number check for salary amounts
        codes = [f.code for f in result.flags]
        # Should NOT have critical anomalies
        assert "HIGH_DUPLICATE_RATE" not in codes
        assert "TEST_TRANSACTIONS" not in codes
        assert "DUMMY_TEXT" not in codes

    def test_suspicious_detects_duplicates(self, pipeline, suspicious_csv_statement):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(suspicious_csv_statement, "", result)
        pipeline._stage_anomaly_checks(result, None, None)
        codes = [f.code for f in result.flags]
        assert "HIGH_DUPLICATE_RATE" in codes or "SOME_DUPLICATES" in codes

    def test_suspicious_detects_test_transactions(self, pipeline, suspicious_csv_statement):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(suspicious_csv_statement, "", result)
        pipeline._stage_anomaly_checks(result, None, None)
        codes = [f.code for f in result.flags]
        assert "TEST_TRANSACTIONS" in codes

    def test_round_number_bias(self, pipeline, suspicious_csv_statement):
        result = ValidationResult()
        result.mime_type = "text/csv"
        pipeline._stage_transaction_extraction(suspicious_csv_statement, "", result)
        pipeline._stage_anomaly_checks(result, None, None)
        codes = [f.code for f in result.flags]
        assert "ROUND_NUMBER_BIAS" in codes


# ===========================================================================
# STAGE 6 – Scoring / Classification
# ===========================================================================

class TestScoring:
    def test_trusted_classification(self, pipeline, valid_csv_statement):
        result = pipeline.validate_statement(valid_csv_statement)
        assert result.status == "Trusted"
        assert result.authenticity_score >= 75

    def test_suspicious_not_trusted(self, pipeline, suspicious_csv_statement):
        result = pipeline.validate_statement(suspicious_csv_statement)
        # Should be flagged for review due to high-severity flags
        assert result.status in ("Review", "HighRisk")
        # Anomaly score should be significantly penalised
        assert result.anomaly_check_score < 50
        # High-severity flags should be present
        flag_codes = [f.code for f in result.flags]
        assert "TEST_TRANSACTIONS" in flag_codes or "ROUND_NUMBER_BIAS" in flag_codes

    def test_tiny_file_high_risk(self, pipeline, tiny_file):
        result = pipeline.validate_statement(tiny_file)
        assert result.status == "HighRisk"
        assert result.authenticity_score < 45


# ===========================================================================
# End-to-end: validate_statement()
# ===========================================================================

class TestFullPipeline:
    def test_returns_validation_result(self, pipeline, valid_csv_statement):
        result = pipeline.validate_statement(valid_csv_statement)
        assert isinstance(result, ValidationResult)

    def test_flags_populated(self, pipeline, valid_csv_statement):
        result = pipeline.validate_statement(valid_csv_statement)
        assert len(result.flags) > 0

    def test_to_dict(self, pipeline, valid_csv_statement):
        result = pipeline.validate_statement(valid_csv_statement)
        d = result.to_dict()
        assert "authenticity_score" in d
        assert "status" in d
        assert "flags" in d
        assert isinstance(d["flags"], list)

    def test_bank_hint_passed(self, pipeline, hsbc_csv_statement):
        result = pipeline.validate_statement(hsbc_csv_statement, bank_hint="HSBC")
        assert result.identified_bank_template == "HSBC"
        flag_codes = [f.code for f in result.flags]
        assert "HINT_CONFIRMED" in flag_codes

    def test_period_dates_passed(self, pipeline, valid_csv_statement):
        result = pipeline.validate_statement(
            valid_csv_statement,
            period_start="01/01/2025",
            period_end="31/01/2025"
        )
        assert result.authenticity_score > 0

    def test_config_override(self, pipeline, valid_csv_statement):
        # Set very strict thresholds
        result = pipeline.validate_statement(
            valid_csv_statement,
            config={"trusted_threshold": 99}
        )
        # With threshold at 99, even a good file may not be "Trusted"
        assert result.authenticity_score > 0

    def test_empty_file_handles_gracefully(self, pipeline):
        result = pipeline.validate_statement(b"")
        assert result.status in ("Review", "HighRisk")
        assert result.authenticity_score <= 50


# ===========================================================================
# ValidationResult serialisation
# ===========================================================================

class TestValidationResultSerialization:
    def test_to_dict_complete(self, pipeline, valid_csv_statement):
        result = pipeline.validate_statement(valid_csv_statement)
        d = result.to_dict()
        
        required_keys = [
            "authenticity_score", "status", "identified_bank_template",
            "flags", "extracted_transactions", "file_hash_sha256",
            "file_size_bytes", "mime_type",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"

    def test_json_serializable(self, pipeline, valid_csv_statement):
        result = pipeline.validate_statement(valid_csv_statement)
        d = result.to_dict()
        # Should not raise
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["status"] in ("Trusted", "Review", "HighRisk")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
