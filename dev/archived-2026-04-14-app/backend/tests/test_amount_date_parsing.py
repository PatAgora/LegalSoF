"""
Unit tests for the shared amount/date parsing helpers
(app/services/amount_parser.py).

Run: pytest backend/tests/test_amount_date_parsing.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.amount_parser import parse_amount, parse_date, detect_currency


class TestParseAmount:
    def test_uk_thousands_with_decimals(self):
        # Regression for A1: must NEVER become 1.23456
        assert parse_amount("1,234.56") == 1234.56

    def test_pound_symbol(self):
        assert parse_amount("£1,234.56") == 1234.56

    def test_comma_thousands_no_decimals(self):
        assert parse_amount("1,234") == 1234.0

    def test_multiple_thousands_groups(self):
        assert parse_amount("1,234,567.89") == 1234567.89

    def test_european_unambiguous(self):
        assert parse_amount("1.234,56") == 1234.56

    def test_european_decimal_comma_only(self):
        assert parse_amount("1234,56") == 1234.56

    def test_parentheses_negative(self):
        assert parse_amount("(500.00)") == -500.00

    def test_cr_suffix_positive(self):
        # Regression for A2: CR rows must not be dropped
        assert parse_amount("1,234.56 CR") == 1234.56

    def test_dr_suffix_negative(self):
        assert parse_amount("500 DR") == -500.0

    def test_attached_dr_suffix(self):
        assert parse_amount("500.00DR") == -500.0

    def test_leading_minus(self):
        assert parse_amount("-123.45") == -123.45

    def test_trailing_minus(self):
        assert parse_amount("123.45-") == -123.45

    def test_garbage_reference_rejected(self):
        # Regression for A5: "REF 123456" must not parse as an amount
        assert parse_amount("REF 123456") is None

    def test_header_word_rejected(self):
        assert parse_amount("Amount") is None
        assert parse_amount("Date") is None

    def test_empty_and_none(self):
        assert parse_amount("") is None
        assert parse_amount(None) is None
        assert parse_amount("-") is None

    def test_dollar_and_euro(self):
        assert parse_amount("$99.99") == 99.99
        assert parse_amount("€2.500,00") == 2500.00

    def test_currency_code(self):
        assert parse_amount("GBP 1,000.00") == 1000.00

    def test_date_like_rejected(self):
        assert parse_amount("15/01/2024") is None


class TestDetectCurrency:
    def test_symbols(self):
        assert detect_currency("£1,234.56") == 'GBP'
        assert detect_currency("$500") == 'USD'
        assert detect_currency("€2.500,00") == 'EUR'

    def test_default(self):
        assert detect_currency("1,234.56") == 'GBP'
        assert detect_currency("") == 'GBP'


class TestParseDate:
    def test_uk_slash(self):
        assert parse_date("15/01/2024") == "2024-01-15"

    def test_uk_dash(self):
        assert parse_date("15-01-2024") == "2024-01-15"

    def test_iso(self):
        assert parse_date("2024-01-15") == "2024-01-15"

    def test_dd_mon_yyyy(self):
        assert parse_date("15 Jan 2024") == "2024-01-15"

    def test_dd_month_yyyy(self):
        assert parse_date("15 January 2024") == "2024-01-15"

    def test_two_digit_year_pivot_2000s(self):
        # Regression for A8: <70 -> 2000s
        assert parse_date("15/01/24") == "2024-01-15"

    def test_two_digit_year_pivot_1900s(self):
        assert parse_date("15/01/85") == "1985-01-15"

    def test_missing_year_with_default_year(self):
        assert parse_date("04 Jan", default_year=2023) == "2023-01-04"

    def test_missing_year_dec_jan_rollover(self):
        # Regression for A7: statement runs Dec 2023 -> Jan 2024.
        # "04 Jan" belongs to Jan 2024; "28 Dec" belongs to Dec 2023.
        hint = ("2023-12-15", "2024-01-14")
        assert parse_date("04 Jan", period_hint=hint) == "2024-01-04"
        assert parse_date("28 Dec", period_hint=hint) == "2023-12-28"

    def test_header_word_returns_none(self):
        # Regression for A6: failure must be None, never the input string
        assert parse_date("Date") is None
        assert parse_date("Balance") is None
        assert parse_date("") is None
        assert parse_date(None) is None

    def test_iso_timestamp(self):
        assert parse_date("2024-01-15T10:30:00") == "2024-01-15"
        assert parse_date("2024-01-15 10:30:00") == "2024-01-15"

    def test_compact(self):
        assert parse_date("20240115") == "2024-01-15"

    def test_invalid_date_rejected(self):
        assert parse_date("32/01/2024") is None
        assert parse_date("15/13/2024") is None

    def test_impossible_day_first_swaps(self):
        # 01/15/2024 can only be MDY
        assert parse_date("01/15/2024") == "2024-01-15"
