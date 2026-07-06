"""
Cross-document corroboration
============================

Runs after a single document's verification finishes, and asks the
question: does this document agree with the OTHER documents on this
matter?

Phase 1 checks (no schema migration required):

  * `ACCOUNT_NAME_MISMATCH`   — the matter's `client_name` does not appear
                                anywhere in this document's text. Almost
                                every genuine bank statement / completion
                                statement / probate grant carries the
                                client's name on it.
  * `PERIOD_GAP_VS_OTHER_STATEMENTS` — this statement's period leaves an
                                unexplained gap (>35 days) relative to the
                                neighbouring statements already uploaded
                                for this matter.

The corroborator is deliberately pipeline-agnostic: callers extract the
relevant inputs (text, period bounds) and call `corroborate(...)`. We
return a list of `VerificationFlag` dataclass instances to keep the
shape identical to the rest of the verification pipeline output.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import Matter
from app.models.document_verification import DocumentVerification, DocumentVerificationFlag
from app.services.document_verification_pipeline import VerificationFlag


# How big a gap between adjacent statements is "unexplained"? UK bank
# statements are typically monthly so anything over ~5 weeks merits a flag.
PERIOD_GAP_DAYS = 35

# Consecutive statements on the same account must chain: statement N's
# closing balance == statement N+1's opening balance, to the penny.
BALANCE_CHAIN_TOLERANCE = Decimal("0.01")

# Tokens that should be ignored when checking whether the client name
# appears in a document — they're meaningless on their own.
_NAME_STOPWORDS = {
    "mr", "mrs", "miss", "ms", "dr", "prof",
    "and", "the", "of", "ltd", "limited", "llp", "plc", "inc",
}


@dataclass
class CorroborationContext:
    """Per-matter context cached across multiple corroborate() calls."""
    matter_id: int
    client_name: str = ""
    other_period_ranges: List["PeriodRange"] = field(default_factory=list)
    # Account identifiers (sort codes / account numbers) recorded by
    # previous bank-statement uploads on this matter, keyed by the
    # verification they came from.
    other_account_sets: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PeriodRange:
    start: datetime
    end: datetime


def _significant_name_tokens(client_name: str) -> List[str]:
    """Split a client name into the parts worth searching for in a document."""
    if not client_name:
        return []
    tokens = re.findall(r"[A-Za-z]{3,}", client_name.lower())
    return [t for t in tokens if t not in _NAME_STOPWORDS]


def _parse_period(s: Optional[str]) -> Optional[datetime]:
    """The pipeline stores periods as free-text strings — try the most
    common UK statement formats."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _load_context(db: Session, matter_id: int, exclude_verification_id: Optional[int]) -> CorroborationContext:
    ctx = CorroborationContext(matter_id=matter_id)

    # Only the client name is needed from the matter.
    client_name_row = (
        db.query(Matter.client_name)
        .filter(Matter.id == matter_id)
        .first()
    )
    if client_name_row:
        ctx.client_name = client_name_row[0] or ""

    # Select only the columns needed — crucially NOT file_bytes, which
    # would drag every raw upload for the matter into memory on every
    # corroboration call.
    q = db.query(
        DocumentVerification.id,
        DocumentVerification.period_start,
        DocumentVerification.period_end,
    ).filter(DocumentVerification.matter_id == matter_id)
    if exclude_verification_id is not None:
        q = q.filter(DocumentVerification.id != exclude_verification_id)
    other_ids: List[int] = []
    for dv_id, period_start, period_end in q.all():
        other_ids.append(dv_id)
        start = _parse_period(period_start)
        end = _parse_period(period_end)
        if start and end and end >= start:
            ctx.other_period_ranges.append(PeriodRange(start=start, end=end))

    # Account identifiers previously recorded by this corroborator
    # (info flag ACCOUNT_IDS_RECORDED persisted alongside each
    # bank-statement verification). Cheap flags-table lookup — no
    # document bytes or text re-extraction needed.
    if other_ids:
        flag_rows = (
            db.query(DocumentVerificationFlag.verification_id, DocumentVerificationFlag.details)
            .filter(
                DocumentVerificationFlag.verification_id.in_(other_ids),
                DocumentVerificationFlag.code == "ACCOUNT_IDS_RECORDED",
            )
            .all()
        )
        for verification_id, details in flag_rows:
            if isinstance(details, dict):
                ctx.other_account_sets.append({
                    "verification_id": verification_id,
                    "sort_codes": set(details.get("sort_codes") or []),
                    "account_numbers": set(details.get("account_numbers") or []),
                })

    return ctx


def _extract_accounts(doc_text: str) -> Dict[str, List[str]]:
    """Best-effort extraction of UK bank account identifiers from a
    document's text: sort codes (XX-XX-XX) and 8-digit account numbers.
    Capped to keep flag payloads small."""
    if not doc_text:
        return {"sort_codes": [], "account_numbers": []}
    sort_codes = sorted(set(re.findall(r"\b\d{2}-\d{2}-\d{2}\b", doc_text)))[:10]
    account_numbers = sorted(set(re.findall(r"\b\d{8}\b", doc_text)))[:10]
    # An 8-digit run can also be a date (e.g. 20260101) — drop values that
    # parse as plausible yyyymmdd dates to reduce noise.
    filtered_numbers = []
    for num in account_numbers:
        year = int(num[:4])
        month = int(num[4:6])
        day = int(num[6:8])
        if 1990 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31:
            continue
        filtered_numbers.append(num)
    return {"sort_codes": sort_codes, "account_numbers": filtered_numbers}


def _check_account_numbers(
    new_accounts: Dict[str, List[str]],
    ctx: CorroborationContext,
) -> Optional[VerificationFlag]:
    """Compare this statement's account identifiers against those recorded
    for the matter's other bank statements.

    A matter can legitimately involve multiple accounts (current +
    savings, joint accounts), so a hard high-severity mismatch flag would
    generate false positives. Instead this emits an info-level
    ACCOUNT_NUMBERS_DIFFER listing the distinct accounts seen when this
    document shares NO account number with any previously uploaded
    statement — a prompt for the reviewer, not an accusation."""
    new_numbers = set(new_accounts.get("account_numbers") or [])
    if not new_numbers or not ctx.other_account_sets:
        return None

    seen_numbers: set = set()
    for acc in ctx.other_account_sets:
        seen_numbers |= acc.get("account_numbers") or set()
    if not seen_numbers:
        return None

    if new_numbers & seen_numbers:
        return None  # Overlap with an already-seen account — corroborates fine

    distinct = sorted(seen_numbers | new_numbers)
    return VerificationFlag(
        "cross_document", "ACCOUNT_NUMBERS_DIFFER", "info",
        "This statement's account number(s) do not match any account seen "
        "on the matter's other statements. Multiple accounts on a matter "
        "can be legitimate — confirm the client holds all of them.",
        {
            "this_document_accounts": sorted(new_numbers),
            "this_document_sort_codes": new_accounts.get("sort_codes") or [],
            "previously_seen_accounts": sorted(seen_numbers),
            "distinct_accounts_on_matter": distinct,
        },
    )


def _check_client_name(doc_text: str, ctx: CorroborationContext) -> Optional[VerificationFlag]:
    """Flag if NONE of the significant tokens from the matter's client
    name appear in the document text. This is intentionally lenient — we
    only flag when there's zero overlap, so OCR-fuzzy / minor-spelling
    differences don't cause false positives."""
    tokens = _significant_name_tokens(ctx.client_name)
    if not tokens or not doc_text:
        return None

    lowered = doc_text.lower()
    found = [t for t in tokens if t in lowered]
    if found:
        return None

    return VerificationFlag(
        "cross_document", "ACCOUNT_NAME_MISMATCH", "high",
        f"Document does not appear to mention the client ('{ctx.client_name}'). "
        "Worth checking the document was uploaded to the right matter.",
        {
            "matter_client_name": ctx.client_name,
            "tokens_searched": tokens,
            "tokens_found": found,
        },
    )


def _check_period_gap(
    new_start: Optional[datetime],
    new_end: Optional[datetime],
    ctx: CorroborationContext,
) -> Optional[VerificationFlag]:
    """Flag if this statement's period leaves a >35 day gap to the nearest
    neighbouring period in the matter (either before or after).

    Only fires when there's at least one other dated statement to compare
    against — a single statement on a matter is never "leaving a gap"."""
    if not new_start or not new_end or new_end < new_start:
        return None
    if not ctx.other_period_ranges:
        return None

    nearest_before_end: Optional[datetime] = None
    nearest_after_start: Optional[datetime] = None
    for r in ctx.other_period_ranges:
        if r.end < new_start:
            if nearest_before_end is None or r.end > nearest_before_end:
                nearest_before_end = r.end
        elif r.start > new_end:
            if nearest_after_start is None or r.start < nearest_after_start:
                nearest_after_start = r.start

    gaps: List[Dict[str, Any]] = []
    threshold = timedelta(days=PERIOD_GAP_DAYS)
    if nearest_before_end is not None and (new_start - nearest_before_end) > threshold:
        gaps.append({
            "direction": "before",
            "neighbour_period_end": nearest_before_end.strftime("%Y-%m-%d"),
            "this_period_start": new_start.strftime("%Y-%m-%d"),
            "gap_days": (new_start - nearest_before_end).days,
        })
    if nearest_after_start is not None and (nearest_after_start - new_end) > threshold:
        gaps.append({
            "direction": "after",
            "this_period_end": new_end.strftime("%Y-%m-%d"),
            "neighbour_period_start": nearest_after_start.strftime("%Y-%m-%d"),
            "gap_days": (nearest_after_start - new_end).days,
        })

    if not gaps:
        return None

    biggest = max(gaps, key=lambda g: g["gap_days"])
    # Medium, not high — a coverage gap merits a question to the client,
    # not a tampering-level alarm (spec §4: low/medium).
    return VerificationFlag(
        "cross_document", "PERIOD_GAP_VS_OTHER_STATEMENTS", "medium",
        f"Statement period leaves a {biggest['gap_days']}-day gap "
        f"({'before' if biggest['direction'] == 'before' else 'after'}) "
        "the neighbouring statements on this matter.",
        {"gaps": gaps, "threshold_days": PERIOD_GAP_DAYS},
    )


# ---------------------------------------------------------------------------
# Statement balance extraction helpers (shared with the upload flow)
# ---------------------------------------------------------------------------

# "Opening balance ... £1,234.56" / "BALANCE BROUGHT FORWARD\n£2,450.00".
# PDF text extraction often puts the amount on the line AFTER the label, so
# the separator may include a newline.
_AMOUNT = r"(-?\s*£?\s*-?[\d,]+\.\d{2})"
_OPENING_BALANCE_PATTERNS = [
    re.compile(r"opening\s+balance[^0-9\-]{0,60}?" + _AMOUNT, re.IGNORECASE | re.DOTALL),
    re.compile(r"balance\s+brought\s+forward[^0-9\-]{0,60}?" + _AMOUNT, re.IGNORECASE | re.DOTALL),
]
_CLOSING_BALANCE_PATTERNS = [
    re.compile(r"closing\s+balance[^0-9\-]{0,60}?" + _AMOUNT, re.IGNORECASE | re.DOTALL),
    re.compile(r"balance\s+carried\s+forward[^0-9\-]{0,60}?" + _AMOUNT, re.IGNORECASE | re.DOTALL),
]

# Account numbers anchored to an "Account No/Number:" label — masked
# ("****5678") or plain ("12345678"). Preferred over the unanchored
# 8-digit scan in _extract_accounts, which can catch reference numbers.
_LABELLED_ACCOUNT_RE = re.compile(
    r"account\s*(?:no|number|num)\.?\s*[:\-]?\s*((?:[*Xx•]\s?){2,}\s?\d{3,8}|\d{8})",
    re.IGNORECASE,
)


def _parse_money(raw: str) -> Optional[float]:
    """Parse a captured amount string like '£1,234.56' / '-£123.45'."""
    cleaned = raw.replace("£", "").replace(",", "").replace(" ", "")
    negative = cleaned.startswith("-") or cleaned.count("-") > 0
    cleaned = cleaned.replace("-", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if negative:
        value = -value
    return float(value)


def extract_balances_from_text(text: str) -> tuple[Optional[float], Optional[float]]:
    """Best-effort (opening_balance, closing_balance) from statement text.
    Looks for 'Opening balance' / 'Balance brought forward' and
    'Closing balance' / 'Balance carried forward' followed by an amount."""
    if not text:
        return None, None
    opening: Optional[float] = None
    closing: Optional[float] = None
    for pat in _OPENING_BALANCE_PATTERNS:
        m = pat.search(text)
        if m:
            opening = _parse_money(m.group(1))
            if opening is not None:
                break
    for pat in _CLOSING_BALANCE_PATTERNS:
        # Take the LAST occurrence — multi-page statements repeat the
        # carried-forward line per page; the final one is the true close.
        matches = list(pat.finditer(text))
        if matches:
            closing = _parse_money(matches[-1].group(1))
            if closing is not None:
                break
    return opening, closing


def derive_balances_from_transactions(transactions) -> tuple[Optional[float], Optional[float]]:
    """(opening, closing) from parsed transactions (objects with .balance,
    .amount, .direction — e.g. the statement pipeline's ExtractedTransaction).

    Closing = the last transaction's balance. Opening = the FIRST
    transaction's balance minus its signed amount — i.e. the balance
    brought forward, which is what the previous statement's closing
    balance must equal."""
    with_balance = [t for t in transactions if getattr(t, "balance", None) is not None]
    if not with_balance:
        return None, None
    first = with_balance[0]
    try:
        first_bal = Decimal(str(first.balance))
        signed = Decimal(str(first.amount or 0))
        if (first.direction or "").lower() != "credit":
            signed = -signed
        opening = float((first_bal - signed).quantize(Decimal("0.01")))
    except (InvalidOperation, TypeError):
        opening = None
    try:
        closing = float(Decimal(str(with_balance[-1].balance)).quantize(Decimal("0.01")))
    except (InvalidOperation, TypeError):
        closing = None
    return opening, closing


def derive_account_identifier(text: str) -> Optional[str]:
    """Best-effort stable account identifier from statement text.

    Prefers 'sort_code account_number' when exactly one of each is found
    (multiple hits mean we can't tell which is the statement's own account,
    so we return None and let the caller fall back to bank grouping).
    Masked account numbers (****5678) are normalised to their visible
    digits prefixed with '*'."""
    if not text:
        return None
    accounts = _extract_accounts(text)
    sort_codes = accounts.get("sort_codes") or []

    # Numbers anchored to an "Account No:" label win over the unanchored
    # 8-digit scan (which can catch reference/statement numbers). Masked
    # numbers are normalised to '*' + their visible digits.
    labelled = sorted({
        (m.group(1) if m.group(1).isdigit()
         else "*" + re.sub(r"[^0-9]", "", m.group(1))[-8:])
        for m in _LABELLED_ACCOUNT_RE.finditer(text)
    })
    numbers = labelled if labelled else list(accounts.get("account_numbers") or [])

    account = numbers[0] if len(numbers) == 1 else None
    sort_code = sort_codes[0] if len(sort_codes) == 1 else None
    if account and sort_code:
        return f"{sort_code} {account}"
    if account:
        return account
    if sort_code:
        return sort_code
    return None


# ---------------------------------------------------------------------------
# Balance chaining (anti-flatten-and-reprint)
# ---------------------------------------------------------------------------

@dataclass
class StatementBalanceInfo:
    """Minimal per-statement record for the balance-chain check. Built
    from DocumentVerification rows in corroborate(); tests can construct
    these directly with in-memory data."""
    verification_id: int
    filename: str = ""
    account_identifier: Optional[str] = None
    bank: Optional[str] = None            # identified template / bank hint fallback
    period_start: Optional[str] = None    # free-text, parsed with _parse_period
    created_at: Optional[datetime] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None


def _chain_group_key(s: StatementBalanceInfo) -> str:
    if s.account_identifier:
        return f"account:{s.account_identifier}"
    if s.bank:
        return f"bank:{s.bank.strip().lower()}"
    return "unknown"


def _chain_sort_key(s: StatementBalanceInfo) -> datetime:
    return _parse_period(s.period_start) or s.created_at or datetime.min


def check_balance_chain(
    statements: List[StatementBalanceInfo],
    new_verification_id: int,
) -> List[VerificationFlag]:
    """Chain-check the matter's bank statements: within each account group
    (falling back to identified bank when no account id was extracted),
    order by period_start (falling back to created_at) and require that
    each statement's closing balance equals the next statement's opening
    balance to within £0.01.

    Only the pairs ADJACENT TO THE NEW STATEMENT are flagged — older pairs
    were checked when their own uploads were corroborated, and re-flagging
    them on every subsequent upload would duplicate flags."""
    new_stmt = next((s for s in statements if s.verification_id == new_verification_id), None)
    if new_stmt is None:
        return []

    group = [s for s in statements if _chain_group_key(s) == _chain_group_key(new_stmt)]
    group.sort(key=_chain_sort_key)
    idx = next(i for i, s in enumerate(group) if s.verification_id == new_verification_id)

    pairs: List[tuple[StatementBalanceInfo, StatementBalanceInfo]] = []
    if idx > 0:
        pairs.append((group[idx - 1], group[idx]))
    if idx < len(group) - 1:
        pairs.append((group[idx], group[idx + 1]))

    flags: List[VerificationFlag] = []
    for prev, nxt in pairs:
        if prev.closing_balance is None or nxt.opening_balance is None:
            continue  # missing data — no flag either way
        try:
            closing = Decimal(str(prev.closing_balance)).quantize(Decimal("0.01"))
            opening = Decimal(str(nxt.opening_balance)).quantize(Decimal("0.01"))
        except InvalidOperation:
            continue
        details = {
            "previous_statement": prev.filename,
            "previous_closing_balance": float(closing),
            "next_statement": nxt.filename,
            "next_opening_balance": float(opening),
            "account_group": _chain_group_key(new_stmt),
        }
        if abs(closing - opening) > BALANCE_CHAIN_TOLERANCE:
            details["difference"] = float(abs(closing - opening))
            flags.append(VerificationFlag(
                "cross_document", "BALANCE_CHAIN_MISMATCH", "high",
                f"Statement balances do not chain: '{prev.filename}' closes at "
                f"£{closing:,.2f} but the next statement '{nxt.filename}' opens at "
                f"£{opening:,.2f}. A genuine statement sequence carries the closing "
                "balance forward — a break can indicate a reprinted or altered statement.",
                details,
            ))
        else:
            flags.append(VerificationFlag(
                "cross_document", "BALANCE_CHAIN_OK", "info",
                f"Balance chain verified: '{prev.filename}' closing balance "
                f"(£{closing:,.2f}) carries forward into '{nxt.filename}'.",
                details,
            ))
    return flags


def _load_balance_chain_statements(db: Session, matter_id: int) -> List[StatementBalanceInfo]:
    """Load the matter's bank-statement verifications (including the new
    one) as StatementBalanceInfo records. Column-only query — never drags
    file_bytes into memory."""
    rows = (
        db.query(
            DocumentVerification.id,
            DocumentVerification.filename,
            DocumentVerification.account_identifier,
            DocumentVerification.identified_bank_template,
            DocumentVerification.bank_hint,
            DocumentVerification.period_start,
            DocumentVerification.created_at,
            DocumentVerification.opening_balance,
            DocumentVerification.closing_balance,
        )
        .filter(
            DocumentVerification.matter_id == matter_id,
            DocumentVerification.file_category == "bank_statement",
        )
        .all()
    )
    return [
        StatementBalanceInfo(
            verification_id=r[0],
            filename=r[1] or "",
            account_identifier=r[2],
            bank=r[3] or r[4],
            period_start=r[5],
            created_at=r[6],
            opening_balance=r[7],
            closing_balance=r[8],
        )
        for r in rows
    ]


def corroborate(
    db: Session,
    matter_id: int,
    new_verification_id: int,
    new_doc_text: str = "",
    new_period_start: Optional[str] = None,
    new_period_end: Optional[str] = None,
    file_category: str = "",
) -> List[VerificationFlag]:
    """Run all corroboration checks for a newly-created verification.

    Returns a list of `VerificationFlag` to be persisted as
    `DocumentVerificationFlag` rows against `new_verification_id`. Empty
    list means everything corroborates fine (no flag).
    """
    ctx = _load_context(db, matter_id, exclude_verification_id=new_verification_id)

    flags: List[VerificationFlag] = []

    f = _check_client_name(new_doc_text, ctx)
    if f:
        flags.append(f)

    start_dt = _parse_period(new_period_start)
    end_dt = _parse_period(new_period_end)
    f = _check_period_gap(start_dt, end_dt, ctx)
    if f:
        flags.append(f)

    # Account-number corroboration — bank statements only. Always record
    # the identifiers found (info flag, hidden from the reviewer's issue
    # list) so future uploads on the matter can compare cheaply without
    # re-reading document bytes.
    if file_category == "bank_statement":
        new_accounts = _extract_accounts(new_doc_text)
        if new_accounts["sort_codes"] or new_accounts["account_numbers"]:
            f = _check_account_numbers(new_accounts, ctx)
            if f:
                flags.append(f)
            flags.append(VerificationFlag(
                "cross_document", "ACCOUNT_IDS_RECORDED", "info",
                "Recorded account identifiers found in this statement for "
                "cross-document comparison.",
                new_accounts,
            ))

        # Balance chaining — statement N's closing balance must equal
        # statement N+1's opening balance for the same account. Relies on
        # the opening/closing/account columns the upload flow persisted
        # on the DocumentVerification rows (including the new one).
        statements = _load_balance_chain_statements(db, matter_id)
        flags.extend(check_balance_chain(statements, new_verification_id))

    return flags
