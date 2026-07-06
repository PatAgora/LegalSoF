"""
Shared amount / date parsing helpers for the bank-statement parsing layer.

All statement parsers (file_processor, universal_financial_parser,
enhanced_universal_parser, natwest_statement_parser) delegate to these
functions so that amount and date semantics are consistent everywhere.

Conventions (UK): GBP default, DD/MM/YYYY input dates, ISO YYYY-MM-DD output.
"""
import re
from datetime import datetime, date, timedelta
from typing import Optional, Tuple

# Currency symbol -> ISO code (strict: only unambiguous symbols)
CURRENCY_SYMBOLS = {
    '£': 'GBP',
    '$': 'USD',
    '€': 'EUR',
    '¥': 'JPY',
    '₹': 'INR',
}

_CURRENCY_CODE_RE = re.compile(
    r'\b(GBP|USD|EUR|JPY|INR|AUD|CAD|CHF|CNY|NZD|SGD|HKD|SEK|NOK|DKK|ZAR)\b',
    re.IGNORECASE,
)

# Trailing DR/CR (or single D/C) marker — matched only as a whole suffix token.
_DRCR_SUFFIX_RE = re.compile(r'(?:(?<=\d)|(?<=\s))(DR|CR|D|C)\.?\s*$', re.IGNORECASE)

_MONTH_MAP = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
    'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
    'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}


def detect_currency(text: str, default: str = 'GBP') -> str:
    """Detect a currency from a raw amount string. Falls back to `default`."""
    if not text:
        return default
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    m = _CURRENCY_CODE_RE.search(text)
    if m:
        return m.group(1).upper()
    return default


def parse_amount(text) -> Optional[float]:
    """
    Parse a monetary amount from text. Returns a SIGNED float, or None if the
    text is not a recognisable amount.

    Handles:
    - Currency symbols (£/$/€/¥/₹) and ISO codes (GBP, USD, ...)
    - Comma thousands: "1,234.56" -> 1234.56, "1,234" -> 1234.0
    - European style ONLY when unambiguous (decimal comma present):
      "1.234,56" -> 1234.56, "1234,56" -> 1234.56
    - Parentheses negatives: "(123.45)" -> -123.45
    - Leading/trailing minus: "-500", "500-" -> -500.0
    - Trailing DR/D -> negative, CR/C -> positive (whole suffix tokens only)
    - Rejects non-numeric garbage (e.g. "REF 123456", "Date") -> None
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)

    s = str(text).strip()
    if not s:
        return None

    is_negative = False

    # Parentheses negative: (123.45)
    if s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1].strip()

    # Trailing DR/CR marker (whole suffix token, case-insensitive)
    m = _DRCR_SUFFIX_RE.search(s)
    if m:
        marker = m.group(1).upper()
        if marker in ('DR', 'D'):
            is_negative = True
        # CR / C -> positive (leave is_negative as-is unless already set)
        s = s[:m.start()].strip()

    # Currency codes and symbols
    s = _CURRENCY_CODE_RE.sub('', s).strip()
    for symbol in CURRENCY_SYMBOLS:
        s = s.replace(symbol, '')
    s = s.strip()

    # Leading / trailing sign
    if s.startswith('-'):
        is_negative = True
        s = s[1:].strip()
    elif s.endswith('-'):
        is_negative = True
        s = s[:-1].strip()
    elif s.startswith('+'):
        s = s[1:].strip()

    if not s:
        return None

    # Reject anything containing characters other than digits, separators, spaces
    if not re.fullmatch(r'[\d.,\s \']+', s):
        return None

    # Remove spaces / apostrophes used as thousands separators (e.g. Swiss 1'234.56)
    s = re.sub(r'\s', '', s).replace("'", '')
    if not s or not any(ch.isdigit() for ch in s):
        return None

    has_comma = ',' in s
    has_dot = '.' in s

    if has_comma and has_dot:
        # Whichever separator appears LAST is the decimal separator.
        # "1,234.56" -> dot decimal (UK); "1.234,56" -> comma decimal (EU).
        if s.rfind('.') > s.rfind(','):
            s = s.replace(',', '')
        else:
            s = s.replace('.', '').replace(',', '.')
    elif has_comma:
        parts = s.split(',')
        # Thousands grouping: every group after the first is exactly 3 digits
        # ("1,234", "1,234,567"). Anything else -> decimal comma ("1234,56").
        if len(parts) >= 2 and all(len(p) == 3 and p.isdigit() for p in parts[1:]) \
                and parts[0].isdigit() and 1 <= len(parts[0]) <= 3:
            s = s.replace(',', '')
        elif len(parts) == 2 and parts[1].isdigit() and 1 <= len(parts[1]) <= 2:
            s = parts[0].replace('.', '') + '.' + parts[1]
        else:
            return None
    # dot-only or plain digits: standard float

    if not re.fullmatch(r'\d+(\.\d+)?', s):
        return None

    try:
        value = float(s)
    except ValueError:
        return None

    return -value if is_negative else value


def _resolve_year_for_day_month(day: int, month: int,
                                default_year: Optional[int],
                                period_hint: Optional[Tuple[str, str]]) -> int:
    """Choose the best year for a day/month with no explicit year."""
    # 1) Period hint: pick the candidate year that places the date inside the
    #    period (handles Dec -> Jan rollover), else nearest to the period.
    if period_hint:
        try:
            start = _coerce_date(period_hint[0])
            end = _coerce_date(period_hint[1])
            if start and end:
                candidates = {start.year, end.year, start.year - 1, end.year + 1}
                best_year, best_dist = None, None
                for y in sorted(candidates):
                    try:
                        d = date(y, month, day)
                    except ValueError:
                        continue
                    if start <= d <= end:
                        return y
                    dist = min(abs((d - start).days), abs((d - end).days))
                    if best_dist is None or dist < best_dist:
                        best_year, best_dist = y, dist
                if best_year is not None:
                    return best_year
        except Exception:
            pass

    # 2) Explicit default year
    if default_year:
        return int(default_year)

    # 3) Current year, but never far in the future: statements describe the
    #    past, so a date more than 30 days ahead means last year.
    year = datetime.now().year
    try:
        d = date(year, month, day)
        if d > date.today() + timedelta(days=30):
            year -= 1
    except ValueError:
        pass
    return year


def _coerce_date(value) -> Optional[date]:
    """Coerce ISO string / date / datetime into a date object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _pivot_two_digit_year(year: int) -> int:
    """Two-digit year pivot: < 70 -> 2000s, >= 70 -> 1900s."""
    if year < 100:
        return year + 2000 if year < 70 else year + 1900
    return year


def parse_date(text, default_year: Optional[int] = None,
               period_hint: Optional[Tuple[str, str]] = None) -> Optional[str]:
    """
    Parse a date string to ISO format (YYYY-MM-DD). Returns None on failure —
    NEVER the input string.

    Supports: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, YYYY-MM-DD, DD Mon YYYY,
    DD Month YYYY, Mon DD YYYY, DD/MM/YY (pivot <70 -> 2000s), "04 Jan"
    (no year: uses default_year / period_hint / rollover guard), ISO
    timestamps, and compact YYYYMMDD.

    period_hint: optional (start, end) ISO date strings for the statement
    period — used to resolve missing years across Dec -> Jan rollovers.
    """
    if text is None:
        return None
    if isinstance(text, datetime):
        return text.strftime('%Y-%m-%d')
    if isinstance(text, date):
        return text.strftime('%Y-%m-%d')

    s = str(text).strip()
    if not s:
        return None

    # ISO timestamp: "2024-01-15T10:30:00", "2024-01-15 10:30:00"
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T\s]\d{2}:\d{2}', s)
    if m:
        return _validate_ymd(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # Strip any trailing time component (e.g. "15/01/2024 08:30:12")
    s = re.sub(r'[T\s]+\d{1,2}:\d{2}(:\d{2})?(\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?$', '', s).strip()
    if not s:
        return None

    # ISO date: YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    m = re.match(r'^(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})$', s)
    if m:
        return _validate_ymd(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # Numeric D/M/Y: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YY etc.
    m = re.match(r'^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})$', s)
    if m:
        p1, p2, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = _pivot_two_digit_year(year)
        # UK convention: day first. Only swap when day-first is impossible.
        if p1 > 12 and p2 <= 12:
            day, month = p1, p2
        elif p2 > 12 and p1 <= 12:
            day, month = p2, p1
        else:
            day, month = p1, p2
        return _validate_ymd(year, month, day)

    # DD Mon [YYYY] / DD Month [YYYY] (e.g. "15 Jan 2024", "04 Jan")
    m = re.match(r'^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s*(\d{2,4})?$', s)
    if m:
        day = int(m.group(1))
        month = _MONTH_MAP.get(m.group(2).lower()[:3])
        if month is None or m.group(2).lower()[:3] not in _MONTH_MAP:
            month = _MONTH_MAP.get(m.group(2).lower())
        if month:
            if m.group(3):
                year = _pivot_two_digit_year(int(m.group(3)))
            else:
                year = _resolve_year_for_day_month(day, month, default_year, period_hint)
            return _validate_ymd(year, month, day)
        return None

    # Mon DD[, YYYY] (US text, e.g. "Jan 15, 2024", "Jan 15")
    m = re.match(r'^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{2,4})?$', s)
    if m:
        month = _MONTH_MAP.get(m.group(1).lower()[:3])
        if month:
            day = int(m.group(2))
            if m.group(3):
                year = _pivot_two_digit_year(int(m.group(3)))
            else:
                year = _resolve_year_for_day_month(day, month, default_year, period_hint)
            return _validate_ymd(year, month, day)
        return None

    # Compact YYYYMMDD
    m = re.match(r'^(\d{8})$', s)
    if m:
        v = m.group(1)
        if int(v[:4]) > 1900:
            return _validate_ymd(int(v[:4]), int(v[4:6]), int(v[6:8]))
        return _validate_ymd(int(v[4:8]), int(v[2:4]), int(v[:2]))

    return None


def _validate_ymd(year: int, month: int, day: int) -> Optional[str]:
    """Validate a Y/M/D triple and format as ISO, else None."""
    try:
        return date(year, month, day).strftime('%Y-%m-%d')
    except ValueError:
        return None
