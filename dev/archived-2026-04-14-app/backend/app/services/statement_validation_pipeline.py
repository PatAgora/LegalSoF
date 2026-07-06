"""
Statement Authenticity Validation Pipeline
==========================================

Pipeline stages executed in order:
  1. File Integrity      – hash, size, mime-type, corruption checks
  2. Template Match      – identify bank from layout / headers / watermarks
  3. Transaction Extract – parse rows using the existing universal parser
  4. Math Checks         – running balance verification, sum cross-checks
  5. Anomaly Checks      – duplicate rows, round-number bias, date gaps, suspicious patterns
  6. Authenticity Score   – weighted aggregate → Trusted / Review / HighRisk

Public interface:
    validate_statement(file_bytes, bank_hint, period_start, period_end, config) -> ValidationResult
"""
from __future__ import annotations

import hashlib
import io
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Flag:
    """Single issue/observation from the pipeline."""
    pipeline_stage: str
    code: str
    severity: str   # info | low | medium | high | critical
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ExtractedTransaction:
    """Minimal transaction extracted during validation."""
    date: str
    description: str
    amount: float
    direction: str   # credit / debit
    balance: Optional[float] = None
    transaction_type: Optional[str] = None
    raw_row: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Full result of the validation pipeline."""
    authenticity_score: float = 0.0
    status: str = "Review"                          # Trusted / Review / HighRisk
    identified_bank_template: Optional[str] = None
    flags: List[Flag] = field(default_factory=list)
    extracted_transactions: List[ExtractedTransaction] = field(default_factory=list)

    # Internal stage scores (0-100 each)
    file_integrity_score: float = 0.0
    template_match_score: float = 0.0
    extraction_score: float = 0.0
    math_check_score: float = 0.0
    anomaly_check_score: float = 0.0

    # Metadata
    file_hash_sha256: str = ""
    file_size_bytes: int = 0
    mime_type: str = ""

    # Stage raw results (stored in JSON columns)
    file_integrity_result: Optional[Dict] = None
    template_match_result: Optional[Dict] = None
    extraction_result: Optional[Dict] = None
    math_check_result: Optional[Dict] = None
    anomaly_check_result: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["flags"] = [asdict(f) for f in self.flags]
        d["extracted_transactions"] = [asdict(t) for t in self.extracted_transactions]
        return d


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    # Score weights (must sum to 1.0)
    "weight_file_integrity": 0.15,
    "weight_template_match": 0.20,
    "weight_extraction":     0.20,
    "weight_math_check":     0.25,
    "weight_anomaly_check":  0.20,

    # Thresholds
    "trusted_threshold": 75,
    "review_threshold":  45,

    # Limits
    "max_file_size_mb": 25,
    "max_balance_drift_pct": 0.01,     # 1% tolerance on running-balance mismatches
    "max_round_number_pct": 0.60,       # flag if >60% of amounts are round
    "max_duplicate_pct":    0.10,       # flag if >10% of rows identical
}


# ---------------------------------------------------------------------------
# Known bank templates (header keywords / patterns)
# ---------------------------------------------------------------------------

BANK_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "HSBC": {
        "keywords": ["hsbc", "hsbc uk", "first direct"],
        "header_patterns": [r"sort\s*code", r"account\s*number", r"hsbc"],
        "date_format": r"\d{2}\s\w{3}\s\d{4}",
    },
    "Barclays": {
        "keywords": ["barclays", "barclaycard"],
        "header_patterns": [r"barclays", r"sort\s*code", r"account\s*no"],
        "date_format": r"\d{2}/\d{2}/\d{4}",
    },
    "NatWest": {
        "keywords": ["natwest", "national westminster"],
        "header_patterns": [r"natwest", r"sort\s*code"],
        "date_format": r"\d{2}\s\w{3}\s\d{4}",
    },
    "Lloyds": {
        "keywords": ["lloyds", "lloyds bank", "halifax", "bank of scotland"],
        "header_patterns": [r"lloyds", r"halifax", r"sort\s*code"],
        "date_format": r"\d{2}/\d{2}/\d{4}",
    },
    "Santander": {
        "keywords": ["santander"],
        "header_patterns": [r"santander", r"account\s*number"],
        "date_format": r"\d{2}/\d{2}/\d{4}",
    },
    "Nationwide": {
        "keywords": ["nationwide"],
        "header_patterns": [r"nationwide", r"building\s*society"],
        "date_format": r"\d{2}\s\w{3}\s\d{4}",
    },
    "TSB": {
        "keywords": ["tsb"],
        "header_patterns": [r"tsb"],
        "date_format": r"\d{2}/\d{2}/\d{4}",
    },
    "Monzo": {
        "keywords": ["monzo"],
        "header_patterns": [r"monzo"],
        "date_format": r"\d{2}/\d{2}/\d{4}",
    },
    "Starling": {
        "keywords": ["starling"],
        "header_patterns": [r"starling"],
        "date_format": r"\d{2}/\d{2}/\d{4}",
    },
    "Generic CSV": {
        "keywords": [],
        "header_patterns": [r"date", r"amount", r"balance", r"description"],
        "date_format": r"\d{2}/\d{2}/\d{4}",
    },
}


# ---------------------------------------------------------------------------
# Pipeline implementation
# ---------------------------------------------------------------------------

class StatementValidationPipeline:
    """Runs the full 6-stage validation pipeline."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = {**DEFAULT_CONFIG, **(config or {})}

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def validate_statement(
        self,
        file_bytes: bytes,
        bank_hint: Optional[str] = None,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Run the full validation pipeline on *file_bytes*.

        Parameters
        ----------
        file_bytes   : raw bytes of the uploaded statement file
        bank_hint    : optional user-supplied bank name
        period_start : optional expected start date (dd/mm/yyyy or yyyy-mm-dd)
        period_end   : optional expected end date
        config       : optional per-call config overrides

        Returns
        -------
        ValidationResult with score, status, flags and optionally extracted txns.
        """
        # Per-call config merge. Never assign onto self.cfg — this class is
        # used as a module singleton and mutating it would leak one call's
        # overrides into every subsequent validation.
        cfg = {**self.cfg, **(config or {})}

        result = ValidationResult()

        # Stage 1 – File Integrity
        self._stage_file_integrity(file_bytes, result, cfg)

        # Determine file content for downstream stages
        text_content = self._extract_text(file_bytes, result.mime_type)

        # Stage 2 – Template Match
        self._stage_template_match(text_content, bank_hint, result)

        # Stage 3 – Transaction Extraction
        self._stage_transaction_extraction(file_bytes, text_content, result)

        # Stage 4 – Math Checks
        self._stage_math_checks(result, period_start, period_end, cfg)

        # Stage 5 – Anomaly Checks
        self._stage_anomaly_checks(result, period_start, period_end, cfg)

        # Stage 6 – Authenticity Scoring
        self._stage_scoring(result, cfg)

        return result

    # ------------------------------------------------------------------
    # STAGE 1 – File Integrity
    # ------------------------------------------------------------------

    def _stage_file_integrity(self, file_bytes: bytes, result: ValidationResult, cfg: Optional[Dict[str, Any]] = None):
        cfg = cfg or self.cfg
        flags: List[Flag] = []
        score = 100.0

        # Hash
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        result.file_hash_sha256 = sha256
        result.file_size_bytes = len(file_bytes)

        # Mime detection (simple heuristic)
        mime = self._detect_mime(file_bytes)
        result.mime_type = mime

        # Size check
        max_bytes = cfg["max_file_size_mb"] * 1024 * 1024
        if len(file_bytes) > max_bytes:
            flags.append(Flag("file_integrity", "FILE_TOO_LARGE", "high",
                              f"File size {len(file_bytes)} exceeds {cfg['max_file_size_mb']}MB limit"))
            score -= 30
        if len(file_bytes) < 100:
            flags.append(Flag("file_integrity", "FILE_TOO_SMALL", "critical",
                              "File is suspiciously small (<100 bytes)"))
            score -= 50

        # PDF-specific checks
        if mime == "application/pdf":
            integrity_info = self._check_pdf_integrity(file_bytes)
            if not integrity_info["valid"]:
                flags.append(Flag("file_integrity", "PDF_CORRUPT", "critical",
                                  "PDF file is corrupt or unreadable"))
                score -= 50
            if integrity_info.get("encrypted"):
                flags.append(Flag("file_integrity", "PDF_ENCRYPTED", "medium",
                                  "PDF is encrypted / password-protected"))
                score -= 15
            if integrity_info.get("has_javascript"):
                flags.append(Flag("file_integrity", "PDF_HAS_JS", "high",
                                  "PDF contains embedded JavaScript — unusual for a bank statement"))
                score -= 25
            if integrity_info.get("has_form_fields"):
                flags.append(Flag("file_integrity", "PDF_FORM_FIELDS", "medium",
                                  "PDF contains editable form fields"))
                score -= 10
            if integrity_info.get("modified_after_creation"):
                flags.append(Flag("file_integrity", "PDF_MODIFIED", "low",
                                  "PDF metadata indicates modification after initial creation"))
                score -= 5

        # CSV checks
        elif mime in ("text/csv", "text/plain"):
            if b"\x00" in file_bytes:
                flags.append(Flag("file_integrity", "BINARY_CONTENT", "high",
                                  "CSV file contains binary/null bytes"))
                score -= 30

        result.file_integrity_score = max(score, 0.0)
        result.file_integrity_result = {"score": result.file_integrity_score, "flags_count": len(flags)}
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 2 – Template Match
    # ------------------------------------------------------------------

    def _stage_template_match(self, text_content: str, bank_hint: Optional[str], result: ValidationResult):
        flags: List[Flag] = []
        score = 50.0  # start neutral
        text_lower = text_content.lower()

        best_bank = None
        best_match_score = 0

        for bank_name, tmpl in BANK_TEMPLATES.items():
            match_score = 0
            # Keyword matching
            for kw in tmpl["keywords"]:
                if kw in text_lower:
                    match_score += 30
            # Header pattern matching
            for pat in tmpl["header_patterns"]:
                if re.search(pat, text_lower):
                    match_score += 20
            # Date format matching
            if tmpl.get("date_format"):
                date_matches = re.findall(tmpl["date_format"], text_content)
                if date_matches:
                    match_score += 10

            if match_score > best_match_score:
                best_match_score = match_score
                best_bank = bank_name

        if best_bank and best_match_score >= 30:
            result.identified_bank_template = best_bank
            score = min(50 + best_match_score, 100)
            flags.append(Flag("template_match", "BANK_IDENTIFIED", "info",
                              f"Identified bank template: {best_bank} (confidence {best_match_score})"))
        else:
            flags.append(Flag("template_match", "NO_TEMPLATE_MATCH", "medium",
                              "Could not match statement to a known bank template"))
            score = 30

        # Cross-check with user hint
        if bank_hint:
            hint_lower = bank_hint.lower().strip()
            if best_bank and hint_lower in best_bank.lower():
                score = min(score + 10, 100)
                flags.append(Flag("template_match", "HINT_CONFIRMED", "info",
                                  f"User-supplied bank hint '{bank_hint}' confirmed by template match"))
            elif best_bank:
                flags.append(Flag("template_match", "HINT_MISMATCH", "high",
                                  f"User said '{bank_hint}' but template matched '{best_bank}'"))
                score = max(score - 20, 0)

        result.template_match_score = score
        result.template_match_result = {
            "score": score,
            "identified_bank": best_bank,
            "match_confidence": best_match_score,
            "bank_hint": bank_hint,
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 3 – Transaction Extraction
    # ------------------------------------------------------------------

    def _stage_transaction_extraction(self, file_bytes: bytes, text_content: str, result: ValidationResult):
        flags: List[Flag] = []
        score = 0.0
        extracted: List[ExtractedTransaction] = []

        try:
            if result.mime_type in ("text/csv", "text/plain"):
                extracted = self._extract_csv_transactions(file_bytes)
            elif result.mime_type == "application/pdf":
                extracted = self._extract_pdf_transactions(file_bytes, text_content)
            else:
                flags.append(Flag("extraction", "UNSUPPORTED_FORMAT", "high",
                                  f"Cannot extract transactions from {result.mime_type}"))
                score = 0

            if extracted:
                score = 80 + min(len(extracted), 20)  # up to 100 for 20+ rows
                flags.append(Flag("extraction", "TRANSACTIONS_EXTRACTED", "info",
                                  f"Successfully extracted {len(extracted)} transactions"))
            else:
                score = 10
                flags.append(Flag("extraction", "NO_TRANSACTIONS", "high",
                                  "No transactions could be extracted from the file"))

        except Exception as e:
            flags.append(Flag("extraction", "EXTRACTION_ERROR", "critical",
                              f"Transaction extraction failed: {str(e)}"))
            score = 0

        result.extracted_transactions = extracted
        result.extraction_score = min(score, 100)
        result.extraction_result = {
            "score": result.extraction_score,
            "transactions_count": len(extracted),
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 4 – Math Checks
    # ------------------------------------------------------------------

    def _stage_math_checks(self, result: ValidationResult, period_start: Optional[str], period_end: Optional[str], cfg: Optional[Dict[str, Any]] = None):
        cfg = cfg or self.cfg
        flags: List[Flag] = []
        txns = result.extracted_transactions
        score = 100.0

        if not txns:
            score = 0.0
            flags.append(Flag("math_check", "NO_DATA", "high",
                              "No transactions to perform math checks on"))
            result.math_check_score = score
            result.math_check_result = {"score": score, "checks_passed": 0, "checks_total": 0}
            result.flags.extend(flags)
            return

        checks_passed = 0
        checks_total = 0

        # 4a. Running balance verification.
        # Walk the FULL transaction list in order: balance-less rows between
        # two balance-bearing rows contribute their signed amounts to the
        # expected movement, so a statement that only shows balances on some
        # rows (common in exports) still reconciles correctly.
        txns_with_balance = [t for t in txns if t.balance is not None]
        if len(txns_with_balance) >= 2:
            checks_total += 1
            balance_errors = 0
            transitions = 0
            prev_balance: Optional[float] = None
            pending_delta = 0.0
            for t in txns:
                delta = t.amount if t.direction == "credit" else -t.amount
                if t.balance is None:
                    if prev_balance is not None:
                        pending_delta += delta
                    continue
                if prev_balance is None:
                    prev_balance = t.balance
                    pending_delta = 0.0
                    continue
                expected_balance = prev_balance + pending_delta + delta
                transitions += 1
                tolerance = abs(expected_balance) * cfg["max_balance_drift_pct"] + 0.02  # +2p for rounding
                if abs(t.balance - expected_balance) > tolerance:
                    balance_errors += 1
                prev_balance = t.balance
                pending_delta = 0.0

            error_rate = balance_errors / transitions if transitions > 0 else 0
            if error_rate == 0:
                checks_passed += 1
                flags.append(Flag("math_check", "BALANCE_OK", "info",
                                  "Running balance verified across all rows"))
            elif error_rate < 0.05:
                checks_passed += 1
                score -= 5
                flags.append(Flag("math_check", "BALANCE_MINOR_ERRORS", "low",
                                  f"Running balance has minor discrepancies in {balance_errors} of {transitions} transitions"))
            else:
                score -= 30
                flags.append(Flag("math_check", "BALANCE_ERRORS", "high",
                                  f"Running balance failed: {balance_errors} errors in {transitions} transitions ({error_rate:.0%})"))

        # 4b. Sum cross-check (total credits vs total debits vs balance change).
        # Totals are computed over the SAME rows the balance movement spans:
        # from the first balance-bearing row to the last, including any
        # balance-less rows in between (their amounts move the balance too).
        if txns_with_balance and len(txns_with_balance) >= 2:
            checks_total += 1
            first_bal_idx = next(i for i, t in enumerate(txns) if t.balance is not None)
            last_bal_idx = len(txns) - 1 - next(
                i for i, t in enumerate(reversed(txns)) if t.balance is not None
            )
            span = txns[first_bal_idx:last_bal_idx + 1]
            total_credits = sum(t.amount for t in span if t.direction == "credit")
            total_debits = sum(t.amount for t in span if t.direction == "debit")
            actual_change = txns_with_balance[-1].balance - txns_with_balance[0].balance
            # Account for the first txn itself
            if txns_with_balance[0].direction == "credit":
                actual_change += txns_with_balance[0].amount
            else:
                actual_change -= txns_with_balance[0].amount
            expected_change = total_credits - total_debits
            sum_tolerance = max(abs(expected_change) * 0.02, 1.0)  # 2% or £1

            if abs(actual_change - expected_change) <= sum_tolerance:
                checks_passed += 1
                flags.append(Flag("math_check", "SUM_CROSS_CHECK_OK", "info",
                                  "Credit/debit totals reconcile with balance movement"))
            else:
                score -= 20
                flags.append(Flag("math_check", "SUM_CROSS_CHECK_FAIL", "high",
                                  f"Credit/debit totals (net £{expected_change:,.2f}) do not match balance movement (£{actual_change:,.2f})",
                                  {"total_credits": total_credits, "total_debits": total_debits,
                                   "expected_net": expected_change, "actual_net": actual_change}))

        # 4c. Date continuity check.
        # A date gap is an observation, not an arithmetic failure — moderate
        # gaps (36-90 days) keep their low-severity flag but still count as
        # a PASSED check so they cannot fail the binary CSV verdict. Only a
        # very large (>90 day) gap fails the check. When no dates parse at
        # all, the check is excluded from checks_total entirely.
        dates = self._parse_txn_dates(txns)
        if dates and len(dates) >= 2:
            checks_total += 1
            sorted_dates = sorted(dates)
            max_gap_days = max(
                (sorted_dates[i + 1] - sorted_dates[i]).days
                for i in range(len(sorted_dates) - 1)
            )
            if max_gap_days <= 35:
                checks_passed += 1
                flags.append(Flag("math_check", "DATE_CONTINUITY_OK", "info",
                                  f"Transaction dates are continuous (max gap: {max_gap_days} days)"))
            elif max_gap_days <= 90:
                checks_passed += 1
                score -= 5
                flags.append(Flag("math_check", "DATE_GAP_MODERATE", "low",
                                  f"Gap of {max_gap_days} days found between transactions"))
            else:
                score -= 15
                flags.append(Flag("math_check", "DATE_GAP_LARGE", "medium",
                                  f"Large gap of {max_gap_days} days found between transactions"))
        elif not dates:
            flags.append(Flag("math_check", "DATES_UNPARSEABLE", "info",
                              "Transaction dates could not be parsed — date continuity check skipped"))
        # A single parseable date: nothing to gap-check; excluded from checks_total.

        result.math_check_score = max(score, 0.0)
        result.math_check_result = {
            "score": result.math_check_score,
            "checks_passed": checks_passed,
            "checks_total": checks_total,
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 5 – Anomaly Checks
    # ------------------------------------------------------------------

    def _stage_anomaly_checks(self, result: ValidationResult, period_start: Optional[str], period_end: Optional[str], cfg: Optional[Dict[str, Any]] = None):
        cfg = cfg or self.cfg
        flags: List[Flag] = []
        txns = result.extracted_transactions
        score = 100.0

        if not txns:
            result.anomaly_check_score = 0
            result.anomaly_check_result = {"score": 0, "anomalies_found": 0}
            result.flags.extend(flags)
            return

        anomalies_found = 0

        # 5a. Duplicate detection
        row_signatures = []
        for t in txns:
            sig = f"{t.date}|{t.amount}|{t.direction}|{(t.description or '')[:30]}"
            row_signatures.append(sig)

        sig_counts = Counter(row_signatures)
        duplicates = sum(c - 1 for c in sig_counts.values() if c > 1)
        dup_pct = duplicates / len(txns) if txns else 0

        if dup_pct > cfg["max_duplicate_pct"]:
            flags.append(Flag("anomaly_check", "HIGH_DUPLICATE_RATE", "high",
                              f"{duplicates} duplicate rows ({dup_pct:.0%}) — potential fabrication indicator",
                              {"duplicate_count": duplicates, "total_rows": len(txns)}))
            score -= 25
            anomalies_found += 1
        elif duplicates > 0:
            flags.append(Flag("anomaly_check", "SOME_DUPLICATES", "low",
                              f"{duplicates} duplicate transaction(s) found"))

        # 5b. Round-number bias
        amounts = [t.amount for t in txns if t.amount]
        round_count = sum(1 for a in amounts if a == round(a, 0) and a >= 10)
        round_pct = round_count / len(amounts) if amounts else 0

        if round_pct > cfg["max_round_number_pct"]:
            flags.append(Flag("anomaly_check", "ROUND_NUMBER_BIAS", "medium",
                              f"{round_pct:.0%} of transactions are round numbers — unusual for genuine statements",
                              {"round_count": round_count, "total": len(amounts)}))
            score -= 15
            anomalies_found += 1

        # 5c. Suspicious description patterns
        descriptions = [t.description.lower() for t in txns if t.description]
        suspicious_patterns = [
            (r"test\s*(transaction|payment|txn)", "TEST_TRANSACTIONS", "Test transactions detected"),
            (r"(lorem|ipsum|sample|dummy|fake)", "DUMMY_TEXT", "Dummy/placeholder text detected"),
            (r"^(payment|transaction)\s*\d+$", "GENERIC_DESCRIPTIONS", "Sequentially numbered generic descriptions"),
        ]
        for pattern, code, msg in suspicious_patterns:
            matches = sum(1 for d in descriptions if re.search(pattern, d))
            if matches > 0:
                flags.append(Flag("anomaly_check", code, "high",
                                  f"{msg} ({matches} occurrences)"))
                score -= 20
                anomalies_found += 1

        # 5d. Amount distribution analysis (entropy check)
        if len(amounts) >= 10:
            # Check for suspiciously uniform distribution
            try:
                stdev = statistics.stdev(amounts)
                mean = statistics.mean(amounts)
                cv = stdev / mean if mean != 0 else 0
                if cv < 0.05:
                    flags.append(Flag("anomaly_check", "UNIFORM_AMOUNTS", "medium",
                                      f"Transaction amounts have suspiciously low variance (CV={cv:.3f})"))
                    score -= 10
                    anomalies_found += 1
            except Exception:
                pass

        # 5e. Period coverage check
        if period_start or period_end:
            dates = self._parse_txn_dates(txns)
            if dates:
                earliest = min(dates)
                latest = max(dates)
                ps = self._parse_date_str(period_start) if period_start else None
                pe = self._parse_date_str(period_end) if period_end else None

                if ps and earliest > ps + timedelta(days=15):
                    flags.append(Flag("anomaly_check", "PERIOD_START_MISMATCH", "medium",
                                      f"First transaction ({earliest.strftime('%d/%m/%Y')}) is {(earliest - ps).days} days after expected period start"))
                    score -= 10
                    anomalies_found += 1
                if pe and latest < pe - timedelta(days=15):
                    flags.append(Flag("anomaly_check", "PERIOD_END_MISMATCH", "medium",
                                      f"Last transaction ({latest.strftime('%d/%m/%Y')}) is {(pe - latest).days} days before expected period end"))
                    score -= 10
                    anomalies_found += 1

        if anomalies_found == 0:
            flags.append(Flag("anomaly_check", "NO_ANOMALIES", "info",
                              "No anomalies detected in transaction data"))

        result.anomaly_check_score = max(score, 0.0)
        result.anomaly_check_result = {
            "score": result.anomaly_check_score,
            "anomalies_found": anomalies_found,
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 6 – Scoring & Classification
    # ------------------------------------------------------------------

    def _stage_scoring(self, result: ValidationResult, cfg: Optional[Dict[str, Any]] = None):
        w = cfg or self.cfg
        weighted_score = (
            result.file_integrity_score * w["weight_file_integrity"] +
            result.template_match_score * w["weight_template_match"] +
            result.extraction_score     * w["weight_extraction"] +
            result.math_check_score     * w["weight_math_check"] +
            result.anomaly_check_score  * w["weight_anomaly_check"]
        )

        result.authenticity_score = round(weighted_score, 1)

        # Critical flags can force HighRisk regardless of score
        critical_flags = [f for f in result.flags if f.severity == "critical"]
        high_flags = [f for f in result.flags if f.severity == "high"]

        if critical_flags or result.authenticity_score < w["review_threshold"]:
            result.status = "HighRisk"
        elif len(high_flags) >= 2 or result.authenticity_score < w["trusted_threshold"]:
            # >=2 high flags (spec rule) — a single high flag alone does
            # not force Review status.
            result.status = "Review"
        else:
            result.status = "Trusted"

        # HighRisk → blocked by default
        result.flags.append(Flag(
            "scoring", "FINAL_SCORE", "info",
            f"Authenticity score: {result.authenticity_score}/100 → {result.status}",
            {
                "file_integrity": result.file_integrity_score,
                "template_match": result.template_match_score,
                "extraction": result.extraction_score,
                "math_check": result.math_check_score,
                "anomaly_check": result.anomaly_check_score,
            }
        ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_mime(file_bytes: bytes) -> str:
        if file_bytes[:4] == b"%PDF":
            return "application/pdf"
        # Heuristic for CSV: first 500 bytes are mostly printable ASCII with commas
        sample = file_bytes[:500]
        try:
            text = sample.decode("utf-8", errors="ignore")
            if "," in text and "\n" in text:
                return "text/csv"
        except Exception:
            pass
        return "application/octet-stream"

    @staticmethod
    def _check_pdf_integrity(file_bytes: bytes) -> Dict[str, Any]:
        info: Dict[str, Any] = {"valid": False, "encrypted": False, "has_javascript": False,
                                 "has_form_fields": False, "modified_after_creation": False}
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            info["valid"] = True
            info["encrypted"] = doc.is_encrypted
            info["page_count"] = doc.page_count

            # Check for JavaScript
            for page in doc:
                for annot in page.annots() or []:
                    if annot.type[0] in (19, 20):  # Widget / Screen
                        info["has_form_fields"] = True

            # Metadata check
            metadata = doc.metadata
            if metadata:
                creation = metadata.get("creationDate", "")
                mod = metadata.get("modDate", "")
                if creation and mod and creation != mod:
                    info["modified_after_creation"] = True
                # Check for JS in catalog
                try:
                    xref_len = doc.xref_length()
                    for i in range(1, min(xref_len, 200)):
                        try:
                            obj_str = doc.xref_object(i)
                            if "/JavaScript" in obj_str or "/JS" in obj_str:
                                info["has_javascript"] = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

            doc.close()
        except Exception as e:
            info["error"] = str(e)
        return info

    @staticmethod
    def _extract_text(file_bytes: bytes, mime_type: str) -> str:
        if mime_type == "application/pdf":
            try:
                import fitz
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                texts = []
                for page in doc:
                    texts.append(page.get_text())
                doc.close()
                return "\n".join(texts)
            except Exception:
                return ""
        else:
            try:
                return file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                return ""

    def _extract_csv_transactions(self, file_bytes: bytes) -> List[ExtractedTransaction]:
        import csv as csvlib
        text = file_bytes.decode("utf-8", errors="ignore")
        reader = csvlib.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return []

        # Find header row
        header_idx = 0
        for i, row in enumerate(rows[:5]):
            row_lower = [c.lower().strip() for c in row]
            if any(h in " ".join(row_lower) for h in ["date", "amount", "balance", "description", "credit", "debit"]):
                header_idx = i
                break

        headers = [h.lower().strip() for h in rows[header_idx]]
        data_rows = rows[header_idx + 1:]

        # Map columns
        date_col = self._find_col(headers, ["date", "transaction date", "posting date", "value date"])
        desc_col = self._find_col(headers, ["description", "details", "narrative", "transaction description", "memo", "reference"])
        amount_col = self._find_col(headers, ["amount", "transaction amount"])
        credit_col = self._find_col(headers, ["credit", "credits", "money in", "paid in", "credit amount"])
        debit_col = self._find_col(headers, ["debit", "debits", "money out", "paid out", "debit amount", "withdrawals"])
        balance_col = self._find_col(headers, ["balance", "closing balance", "running balance", "available balance"])
        type_col = self._find_col(headers, ["type", "transaction type"])

        transactions = []
        for row in data_rows:
            if not row or all(not c.strip() for c in row):
                continue
            try:
                date = row[date_col].strip() if date_col is not None and date_col < len(row) else ""
                desc = row[desc_col].strip() if desc_col is not None and desc_col < len(row) else ""
                bal = self._parse_amount(row[balance_col]) if balance_col is not None and balance_col < len(row) else None
                txn_type = row[type_col].strip() if type_col is not None and type_col < len(row) else None

                if amount_col is not None and amount_col < len(row):
                    amt_val = self._parse_amount(row[amount_col])
                    if amt_val is not None:
                        direction = "credit" if amt_val >= 0 else "debit"
                        amt_val = abs(amt_val)
                    else:
                        continue
                elif credit_col is not None or debit_col is not None:
                    credit_val = self._parse_amount(row[credit_col]) if credit_col is not None and credit_col < len(row) else None
                    debit_val = self._parse_amount(row[debit_col]) if debit_col is not None and debit_col < len(row) else None
                    if credit_val and credit_val > 0:
                        amt_val = credit_val
                        direction = "credit"
                    elif debit_val and debit_val > 0:
                        amt_val = debit_val
                        direction = "debit"
                    else:
                        continue
                else:
                    continue

                if not date and not amt_val:
                    continue

                transactions.append(ExtractedTransaction(
                    date=date, description=desc, amount=amt_val,
                    direction=direction, balance=bal, transaction_type=txn_type,
                    raw_row={headers[i]: row[i] for i in range(min(len(headers), len(row)))}
                ))
            except (IndexError, ValueError):
                continue

        return transactions

    def _extract_pdf_transactions(self, file_bytes: bytes, text_content: str) -> List[ExtractedTransaction]:
        """Attempt basic PDF transaction extraction from text content."""
        transactions = []

        # Try line-by-line extraction with date-anchored regex
        date_pattern = re.compile(
            r"(\d{2}[/\-\.]\d{2}[/\-\.]\d{2,4}|\d{2}\s+\w{3}\s+\d{4})"
        )
        amount_pattern = re.compile(r"[\-]?£?\s*([\d,]+\.\d{2})")

        lines = text_content.split("\n")
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue

            date_match = date_pattern.search(line)
            if not date_match:
                continue

            amounts = amount_pattern.findall(line)
            if not amounts:
                continue

            date_str = date_match.group(1)
            # Use the last amount as balance (if multiple), first non-balance as txn amount
            parsed_amounts = []
            for a in amounts:
                try:
                    parsed_amounts.append(float(a.replace(",", "")))
                except ValueError:
                    continue

            if not parsed_amounts:
                continue

            txn_amount = parsed_amounts[0]
            balance = parsed_amounts[-1] if len(parsed_amounts) > 1 else None

            # Guess direction from context
            desc = line[date_match.end():].strip()
            desc = re.sub(r"[\-]?£?\s*[\d,]+\.\d{2}", "", desc).strip()

            direction = "debit"
            if any(kw in desc.lower() for kw in ["credit", "paid in", "deposit", "interest", "salary", "refund"]):
                direction = "credit"
            if any(kw in line.lower() for kw in ["cr", "credit"]):
                direction = "credit"

            transactions.append(ExtractedTransaction(
                date=date_str, description=desc[:200], amount=abs(txn_amount),
                direction=direction, balance=balance
            ))

        return transactions

    @staticmethod
    def _find_col(headers: List[str], candidates: List[str]) -> Optional[int]:
        for c in candidates:
            for i, h in enumerate(headers):
                if c in h or h in c:
                    return i
        return None

    @staticmethod
    def _parse_amount(value: str) -> Optional[float]:
        if not value or not value.strip():
            return None
        cleaned = value.strip().replace("£", "").replace(",", "").replace(" ", "")
        # Handle parenthetical negatives: (100.00) -> -100.00
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _parse_txn_dates(self, txns: List[ExtractedTransaction]) -> List[datetime]:
        dates = []
        for t in txns:
            d = self._parse_date_str(t.date)
            if d:
                dates.append(d)
        return dates

    @staticmethod
    def _parse_date_str(date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        # ISO timestamps first — Monzo/Starling exports use
        # "YYYY-MM-DD HH:MM:SS" / "YYYY-MM-DDTHH:MM:SS".
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                    "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y",
                    "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except (ValueError, TypeError):
                continue
        return None


# Singleton instance for convenience
validation_pipeline = StatementValidationPipeline()
