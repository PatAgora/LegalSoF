"""
Unit tests for statement balance chaining (anti-flatten-and-reprint).

Covers:
  * check_balance_chain — the pure chaining logic, driven with in-memory
    StatementBalanceInfo objects (no database needed)
  * the balance/account extraction helpers used by the upload flow

Run with: pytest tests/test_balance_chaining.py -v
"""
import pytest
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cross_document_corroborator import (
    StatementBalanceInfo,
    check_balance_chain,
    extract_balances_from_text,
    derive_balances_from_transactions,
    derive_account_identifier,
)


def _stmt(vid, filename, opening=None, closing=None, account="20-45-67 12345678",
          bank=None, period_start=None, created_at=None):
    return StatementBalanceInfo(
        verification_id=vid,
        filename=filename,
        account_identifier=account,
        bank=bank,
        period_start=period_start,
        created_at=created_at,
        opening_balance=opening,
        closing_balance=closing,
    )


def _codes(flags):
    return [f.code for f in flags]


# ===========================================================================
# check_balance_chain — core logic
# ===========================================================================

class TestBalanceChain:
    def test_matching_chain_emits_ok(self):
        stmts = [
            _stmt(1, "jan.pdf", opening=100.00, closing=250.50, period_start="2025-01-01"),
            _stmt(2, "feb.pdf", opening=250.50, closing=310.00, period_start="2025-02-01"),
        ]
        flags = check_balance_chain(stmts, new_verification_id=2)
        assert _codes(flags) == ["BALANCE_CHAIN_OK"]
        assert flags[0].severity == "info"

    def test_mismatch_flags_high(self):
        stmts = [
            _stmt(1, "jan.pdf", opening=100.00, closing=250.50, period_start="2025-01-01"),
            _stmt(2, "feb.pdf", opening=999.99, closing=310.00, period_start="2025-02-01"),
        ]
        flags = check_balance_chain(stmts, new_verification_id=2)
        assert _codes(flags) == ["BALANCE_CHAIN_MISMATCH"]
        assert flags[0].severity == "high"
        # Both values and both filenames must be in the details
        d = flags[0].details
        assert d["previous_statement"] == "jan.pdf"
        assert d["next_statement"] == "feb.pdf"
        assert d["previous_closing_balance"] == 250.50
        assert d["next_opening_balance"] == 999.99

    def test_penny_tolerance(self):
        # Exactly 1p out — within tolerance, no mismatch
        stmts = [
            _stmt(1, "jan.pdf", closing=250.50, period_start="2025-01-01"),
            _stmt(2, "feb.pdf", opening=250.51, period_start="2025-02-01"),
        ]
        flags = check_balance_chain(stmts, new_verification_id=2)
        assert _codes(flags) == ["BALANCE_CHAIN_OK"]

        # 2p out — beyond tolerance
        stmts[1].opening_balance = 250.52
        flags = check_balance_chain(stmts, new_verification_id=2)
        assert _codes(flags) == ["BALANCE_CHAIN_MISMATCH"]

    def test_float_artifacts_do_not_false_flag(self):
        # 0.1 + 0.2 style float noise must not trip the penny comparison
        stmts = [
            _stmt(1, "jan.pdf", closing=0.30000000000000004, period_start="2025-01-01"),
            _stmt(2, "feb.pdf", opening=0.30, period_start="2025-02-01"),
        ]
        flags = check_balance_chain(stmts, new_verification_id=2)
        assert _codes(flags) == ["BALANCE_CHAIN_OK"]

    def test_missing_balances_no_flag(self):
        stmts = [
            _stmt(1, "jan.pdf", closing=None, period_start="2025-01-01"),
            _stmt(2, "feb.pdf", opening=250.50, period_start="2025-02-01"),
        ]
        assert check_balance_chain(stmts, new_verification_id=2) == []

        stmts = [
            _stmt(1, "jan.pdf", closing=250.50, period_start="2025-01-01"),
            _stmt(2, "feb.pdf", opening=None, period_start="2025-02-01"),
        ]
        assert check_balance_chain(stmts, new_verification_id=2) == []

    def test_single_statement_no_flag(self):
        stmts = [_stmt(1, "jan.pdf", opening=1.0, closing=2.0, period_start="2025-01-01")]
        assert check_balance_chain(stmts, new_verification_id=1) == []

    def test_different_accounts_not_chained(self):
        stmts = [
            _stmt(1, "current.pdf", closing=250.50, account="20-45-67 11111111",
                  period_start="2025-01-01"),
            _stmt(2, "savings.pdf", opening=999.99, account="20-45-67 22222222",
                  period_start="2025-02-01"),
        ]
        assert check_balance_chain(stmts, new_verification_id=2) == []

    def test_bank_fallback_grouping_when_account_absent(self):
        stmts = [
            _stmt(1, "jan.pdf", closing=250.50, account=None, bank="Barclays",
                  period_start="2025-01-01"),
            _stmt(2, "feb.pdf", opening=100.00, account=None, bank="Barclays",
                  period_start="2025-02-01"),
        ]
        flags = check_balance_chain(stmts, new_verification_id=2)
        assert _codes(flags) == ["BALANCE_CHAIN_MISMATCH"]

    def test_ordering_by_period_start(self):
        # Uploaded out of order: the new statement (March) must chain against
        # February's closing, not January's.
        stmts = [
            _stmt(1, "jan.pdf", opening=0.0, closing=100.00, period_start="2025-01-01"),
            _stmt(3, "mar.pdf", opening=200.00, closing=300.00, period_start="2025-03-01"),
            _stmt(2, "feb.pdf", opening=100.00, closing=200.00, period_start="2025-02-01"),
        ]
        flags = check_balance_chain(stmts, new_verification_id=3)
        assert _codes(flags) == ["BALANCE_CHAIN_OK"]
        assert flags[0].details["previous_statement"] == "feb.pdf"

    def test_insert_in_middle_checks_both_neighbours(self):
        # New February statement lands between January and March: chain OK
        # backwards (jan->feb) but broken forwards (feb->mar).
        stmts = [
            _stmt(1, "jan.pdf", opening=0.0, closing=100.00, period_start="2025-01-01"),
            _stmt(3, "mar.pdf", opening=500.00, closing=600.00, period_start="2025-03-01"),
            _stmt(2, "feb.pdf", opening=100.00, closing=200.00, period_start="2025-02-01"),
        ]
        flags = check_balance_chain(stmts, new_verification_id=2)
        assert sorted(_codes(flags)) == ["BALANCE_CHAIN_MISMATCH", "BALANCE_CHAIN_OK"]
        mismatch = next(f for f in flags if f.code == "BALANCE_CHAIN_MISMATCH")
        assert mismatch.details["previous_statement"] == "feb.pdf"
        assert mismatch.details["next_statement"] == "mar.pdf"

    def test_created_at_fallback_ordering(self):
        stmts = [
            _stmt(1, "first.csv", closing=100.00, period_start=None,
                  created_at=datetime(2025, 1, 1)),
            _stmt(2, "second.csv", opening=100.00, period_start=None,
                  created_at=datetime(2025, 2, 1)),
        ]
        flags = check_balance_chain(stmts, new_verification_id=2)
        assert _codes(flags) == ["BALANCE_CHAIN_OK"]

    def test_new_id_not_in_list_no_flags(self):
        stmts = [_stmt(1, "jan.pdf", opening=1.0, closing=2.0)]
        assert check_balance_chain(stmts, new_verification_id=99) == []


# ===========================================================================
# Extraction helpers used by the upload flow
# ===========================================================================

class TestExtractBalancesFromText:
    def test_opening_and_closing_labels(self):
        text = "Opening balance £1,234.56\n...\nClosing balance £2,000.00"
        assert extract_balances_from_text(text) == (1234.56, 2000.00)

    def test_brought_and_carried_forward_across_newlines(self):
        # Real PDF extraction shape — amount on the line after the label
        text = (
            "01/10/2025\nBALANCE BROUGHT FORWARD\n£2,450.00\n"
            "02/10/2025\nTESCO STORES\nDEB\n£85.42\n£2,364.58\n"
            "31/10/2025\nBALANCE CARRIED FORWARD\n£70,949.13\n"
        )
        assert extract_balances_from_text(text) == (2450.00, 70949.13)

    def test_last_carried_forward_wins(self):
        # Multi-page statements repeat the carried-forward line per page
        text = (
            "BALANCE CARRIED FORWARD £100.00\n"
            "page 2\n"
            "BALANCE CARRIED FORWARD £200.00\n"
        )
        assert extract_balances_from_text(text) == (None, 200.00)

    def test_negative_amount(self):
        text = "Opening balance -£123.45"
        opening, _ = extract_balances_from_text(text)
        assert opening == -123.45

    def test_no_labels(self):
        assert extract_balances_from_text("no balances here") == (None, None)
        assert extract_balances_from_text("") == (None, None)


class _Txn:
    """Duck-typed stand-in for ExtractedTransaction."""
    def __init__(self, amount, direction, balance=None):
        self.amount = amount
        self.direction = direction
        self.balance = balance


class TestDeriveBalancesFromTransactions:
    def test_opening_is_balance_brought_forward(self):
        # First txn: +3500 credit leaving balance 3500 => opening was 0.00
        txns = [
            _Txn(3500.00, "credit", 3500.00),
            _Txn(45.67, "debit", 3454.33),
        ]
        opening, closing = derive_balances_from_transactions(txns)
        assert opening == 0.00
        assert closing == 3454.33

    def test_debit_first_txn(self):
        txns = [_Txn(50.00, "debit", 950.00), _Txn(10.00, "debit", 940.00)]
        opening, closing = derive_balances_from_transactions(txns)
        assert opening == 1000.00
        assert closing == 940.00

    def test_skips_balance_less_rows(self):
        txns = [_Txn(10.00, "credit", None), _Txn(20.00, "credit", 120.00)]
        opening, closing = derive_balances_from_transactions(txns)
        assert opening == 100.00
        assert closing == 120.00

    def test_no_balances(self):
        assert derive_balances_from_transactions([_Txn(1.0, "credit")]) == (None, None)
        assert derive_balances_from_transactions([]) == (None, None)


class TestDeriveAccountIdentifier:
    def test_sort_code_and_account_number(self):
        text = "Sort Code: 20-45-67 Account Number: 12345678"
        assert derive_account_identifier(text) == "20-45-67 12345678"

    def test_masked_account_number(self):
        text = "Sort Code: 40-11-22\nAccount No: ****5678"
        assert derive_account_identifier(text) == "40-11-22 *5678"

    def test_ambiguous_accounts_returns_sort_code_only_or_none(self):
        # Two distinct 8-digit account numbers — cannot tell which is the
        # statement's own account.
        text = "Account 11111111 and account 22222222, sort code 20-45-67"
        assert derive_account_identifier(text) == "20-45-67"

    def test_no_identifiers(self):
        assert derive_account_identifier("nothing here") is None
        assert derive_account_identifier("") is None


# ===========================================================================
# End-to-end through corroborate() with in-memory SQLite
# ===========================================================================

@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    import app.models  # noqa: F401 — register every model on Base.metadata

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


class TestCorroborateBalanceChain:
    def _make_matter(self, db):
        from app.models import Matter, User, UserRole
        user = User(email="t@example.com", hashed_password="x",
                    full_name="Test", role=UserRole.ADMIN)
        db.add(user)
        db.commit()
        matter = Matter(client_name="John Smith", reference_number="MAT-1",
                        target_amount=100000, created_by_id=user.id)
        db.add(matter)
        db.commit()
        return matter

    def _make_dv(self, db, matter, filename, period_start, period_end,
                 opening, closing, account="40-11-22 *5678"):
        from app.models.document_verification import (
            DocumentVerification, VerificationVerdict,
        )
        dv = DocumentVerification(
            matter_id=matter.id, filename=filename, file_hash=filename,
            file_category="bank_statement", authenticity_score=90,
            verdict=VerificationVerdict.VERIFIED,
            period_start=period_start, period_end=period_end,
            opening_balance=opening, closing_balance=closing,
            account_identifier=account,
        )
        db.add(dv)
        db.commit()
        return dv

    def test_mismatch_flagged_through_db(self, db_session):
        from app.services.cross_document_corroborator import corroborate
        matter = self._make_matter(db_session)
        self._make_dv(db_session, matter, "jan.pdf", "2025-01-01", "2025-01-31",
                      100.00, 250.50)
        new = self._make_dv(db_session, matter, "feb.pdf", "2025-02-01",
                            "2025-02-28", 999.99, 400.00)
        flags = corroborate(
            db_session, matter.id, new.id,
            new_doc_text="John Smith sort code 40-11-22",
            new_period_start="2025-02-01", new_period_end="2025-02-28",
            file_category="bank_statement",
        )
        codes = [f.code for f in flags]
        assert "BALANCE_CHAIN_MISMATCH" in codes
        mismatch = next(f for f in flags if f.code == "BALANCE_CHAIN_MISMATCH")
        assert mismatch.severity == "high"
        assert mismatch.details["previous_statement"] == "jan.pdf"
        assert mismatch.details["next_statement"] == "feb.pdf"

    def test_chain_ok_through_db(self, db_session):
        from app.services.cross_document_corroborator import corroborate
        matter = self._make_matter(db_session)
        self._make_dv(db_session, matter, "jan.pdf", "2025-01-01", "2025-01-31",
                      100.00, 250.50)
        new = self._make_dv(db_session, matter, "feb.pdf", "2025-02-01",
                            "2025-02-28", 250.50, 400.00)
        flags = corroborate(
            db_session, matter.id, new.id,
            new_doc_text="John Smith sort code 40-11-22",
            new_period_start="2025-02-01", new_period_end="2025-02-28",
            file_category="bank_statement",
        )
        codes = [f.code for f in flags]
        assert "BALANCE_CHAIN_OK" in codes
        assert "BALANCE_CHAIN_MISMATCH" not in codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
