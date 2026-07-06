"""
Document Verification Pipeline
==============================

Pipeline stages executed in order:
  1. PDF Metadata Analysis      - check Creator/Producer for suspicious tools, date consistency,
                                  encryption/permission flags, producer version vs creation date
  2. Structural Integrity       - count %%EOF markers, embedded files, form XObjects,
                                  orphaned objects, linearization, xref integrity,
                                  file size anomaly, compression analysis
  3. Font & Text Analysis       - font consistency, text layered over scanned images,
                                  page-level consistency, watermark/header consistency
  4. Image Analysis             - DPI consistency across embedded images,
                                  color profile analysis
  5. Content Consistency        - dates in content vs metadata dates
  6. Digital Signature Check    - signature presence, expected signatures for known banks
  7. Annotation & Form Analysis - annotation detection, form field detection, fake redaction
  8. Hidden Content Detection   - hidden layers (OCGs), whited-out content detection
  9. Authenticity Scoring       - weighted aggregate -> VERIFIED / SUSPICIOUS / LIKELY_TAMPERED

Public interface:
    verify_document(file_bytes, filename, file_category, config) -> VerificationResult
"""
from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple


def _normalise_for_compare(s: str) -> str:
    """Strip whitespace runs and most punctuation so OCR and text-layer
    comparisons aren't tripped up by trivial formatting differences."""
    if not s:
        return ""
    # Lowercase, collapse whitespace, drop punctuation that OCR mis-handles
    lowered = s.lower()
    cleaned = re.sub(r"[^a-z0-9£$.,/\-\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VerificationFlag:
    """Single issue/observation from the pipeline."""
    pipeline_stage: str
    code: str
    severity: str   # info | low | medium | high | critical
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class VerificationResult:
    """Full result of the document verification pipeline."""
    authenticity_score: float = 0.0
    verdict: str = "Suspicious"           # Verified / Suspicious / LikelyTampered
    flags: List[VerificationFlag] = field(default_factory=list)

    # Internal stage scores (0-100 each)
    metadata_score: float = 0.0
    structural_score: float = 0.0
    font_text_score: float = 0.0
    image_score: float = 0.0
    content_consistency_score: float = 0.0
    signature_score: float = 0.0
    annotation_form_score: float = 0.0
    hidden_content_score: float = 0.0

    # Metadata about the file
    file_hash_sha256: str = ""
    file_size_bytes: int = 0
    filename: str = ""
    file_category: str = ""

    # Stage raw results (stored in JSON columns)
    metadata_result: Optional[Dict] = None
    structural_result: Optional[Dict] = None
    font_text_result: Optional[Dict] = None
    image_result: Optional[Dict] = None
    content_consistency_result: Optional[Dict] = None
    signature_result: Optional[Dict] = None
    annotation_form_result: Optional[Dict] = None
    hidden_content_result: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["flags"] = [asdict(f) for f in self.flags]
        return d


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    # Score weights (must sum to 1.0)
    "weight_metadata":            0.15,
    "weight_structural":          0.10,
    "weight_font_text":           0.15,
    "weight_image":               0.10,
    "weight_content_consistency": 0.15,
    "weight_signature":           0.10,
    "weight_annotation_form":     0.15,
    "weight_hidden_content":      0.10,

    # Thresholds
    "verified_threshold":  75,
    "suspicious_threshold": 45,

    # Suspicious PDF creators/producers
    "suspicious_creators": [
        "photoshop", "gimp", "illustrator", "inkscape",
        "canva", "paint", "acrobat pro", "foxit phantompdf",
        "nitro pro", "pdfelement", "pdfpen", "sejda",
        "smallpdf", "ilovepdf", "pdf-xchange", "pdf expert",
    ],
}

# Resource bounds — very long documents are analysed up to this many pages
# (an info flag records the truncation), and files above the size cap are
# not analysed at all (verdict Pending).
MAX_ANALYSIS_PAGES = 200
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


def compute_verdict(
    authenticity_score: float,
    flag_severities: List[str],
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """Standard verdict rule, shared with orchestrators that add flags
    after the pipeline has run (e.g. cross-document corroboration):
    any critical flag or a score below the suspicious threshold forces
    LikelyTampered; >=2 high flags or a score below the verified
    threshold means Suspicious; otherwise Verified."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    has_critical = any(s == "critical" for s in flag_severities)
    high_count = sum(1 for s in flag_severities if s == "high")
    if has_critical or authenticity_score < cfg["suspicious_threshold"]:
        return "LikelyTampered"
    if high_count >= 2 or authenticity_score < cfg["verified_threshold"]:
        return "Suspicious"
    return "Verified"


# ---------------------------------------------------------------------------
# Known bank signature expectations
# ---------------------------------------------------------------------------

# NOTE: expects_signature is currently False for the big four — most UK
# online-banking statement downloads are unsigned, so penalising the
# absence of a signature produced false positives on genuine statements.
# The table structure is kept so the expectation can be re-enabled per
# bank once signed-download coverage is confirmed.
BANK_SIGNATURE_EXPECTATIONS: Dict[str, Dict[str, Any]] = {
    "HSBC": {
        "keywords": ["hsbc", "hsbc uk", "first direct"],
        "expects_signature": False,
        "common_producers": ["hsbc", "xerox", "canon"],
    },
    "Barclays": {
        "keywords": ["barclays", "barclaycard"],
        "expects_signature": False,
        "common_producers": ["barclays", "xerox"],
    },
    "NatWest": {
        "keywords": ["natwest", "national westminster"],
        "expects_signature": False,
        "common_producers": ["natwest", "xerox"],
    },
    "Lloyds": {
        "keywords": ["lloyds", "lloyds bank", "halifax", "bank of scotland"],
        "expects_signature": False,
        "common_producers": ["lloyds", "xerox"],
    },
    "Santander": {
        "keywords": ["santander"],
        "expects_signature": False,
        "common_producers": ["santander"],
    },
    "Nationwide": {
        "keywords": ["nationwide"],
        "expects_signature": False,
        "common_producers": ["nationwide"],
    },
}


# ---------------------------------------------------------------------------
# Pipeline implementation
# ---------------------------------------------------------------------------

class DocumentVerificationPipeline:
    """Runs the full 8-stage document verification pipeline."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.cfg = {**DEFAULT_CONFIG, **(config or {})}

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def verify_document(
        self,
        file_bytes: bytes,
        filename: str = "",
        file_category: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Run the full verification pipeline on *file_bytes*.

        Parameters
        ----------
        file_bytes     : raw bytes of the uploaded document file
        filename       : original filename
        file_category  : category of the file (bank_statement, supporting_doc, etc.)
        config         : optional per-call config overrides

        Returns
        -------
        VerificationResult with score, verdict, flags.
        """
        # Per-call config merge. Never assign onto self.cfg — this class is
        # used as a module singleton and mutating it would leak one call's
        # overrides into every subsequent verification.
        cfg = {**self.cfg, **(config or {})}

        result = VerificationResult()
        result.file_hash_sha256 = hashlib.sha256(file_bytes).hexdigest()
        result.file_size_bytes = len(file_bytes)
        result.filename = filename
        result.file_category = file_category

        # Resource guard — refuse to analyse oversized files rather than
        # tie up a worker; verdict stays Pending for manual handling.
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            result.authenticity_score = 0.0
            result.verdict = "Pending"
            result.flags.append(VerificationFlag(
                "metadata", "FILE_TOO_LARGE", "high",
                f"File is {len(file_bytes) / (1024 * 1024):.1f} MB, above the "
                f"{MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB verification limit. "
                "Structural verification was not run.",
                {"file_size_bytes": len(file_bytes),
                 "limit_bytes": MAX_FILE_SIZE_BYTES},
            ))
            result.metadata_result = {"score": 0, "note": "File too large — verification skipped"}
            return result

        # Non-PDF files: structural analysis not applicable
        # CSVs will be verified by the statement validation pipeline instead
        if not file_bytes[:4] == b"%PDF":
            result.authenticity_score = 0.0
            result.verdict = "Pending"
            result.flags.append(VerificationFlag(
                "metadata", "NON_PDF_FILE", "info",
                f"File is not a PDF ({filename}). Structural verification not applicable. "
                "Statement validation pipeline will provide verification."
            ))
            result.metadata_result = {"score": 0, "note": "Non-PDF — see statement validation"}
            return result

        # Open PDF once, share across stages
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            result.authenticity_score = 0.0
            result.verdict = "LikelyTampered"
            result.flags.append(VerificationFlag(
                "metadata", "PDF_OPEN_FAILED", "critical",
                f"Cannot open PDF: {str(e)}"
            ))
            return result

        # Password-protected PDFs cannot be inspected — page access would
        # raise. Record the fact and return without attempting analysis.
        if getattr(doc, "needs_pass", False):
            result.authenticity_score = 0.0
            result.verdict = "Suspicious"
            result.flags.append(VerificationFlag(
                "metadata", "PASSWORD_PROTECTED", "high",
                "PDF is password-protected; its contents cannot be inspected. "
                "Request an unprotected copy from the client.",
                {"needs_pass": True},
            ))
            result.metadata_result = {"score": 0, "note": "Password-protected — verification skipped"}
            doc.close()
            return result

        try:
            try:
                # Resource guard — cap per-page analysis on very long documents.
                if doc.page_count > MAX_ANALYSIS_PAGES:
                    result.flags.append(VerificationFlag(
                        "structural", "PAGE_LIMIT_EXCEEDED", "info",
                        f"PDF has {doc.page_count} pages; structural analysis was "
                        f"capped at the first {MAX_ANALYSIS_PAGES}.",
                        {"page_count": doc.page_count, "analysed_pages": MAX_ANALYSIS_PAGES},
                    ))

                # Stage 1 - PDF Metadata Analysis
                self._stage_metadata_analysis(doc, result, cfg)

                # Stage 2 - Structural Integrity
                self._stage_structural_integrity(doc, file_bytes, result)

                # Stage 3 - Font & Text Analysis
                self._stage_font_text_analysis(doc, result)

                # Stage 4 - Image Analysis
                self._stage_image_analysis(doc, result)

                # Extract text for content-based stages
                text_parts: List[str] = []
                for page_num in self._page_range(doc):
                    try:
                        text_parts.append(doc[page_num].get_text() or "")
                    except Exception:
                        continue
                text_content = "\n".join(text_parts) + "\n"

                # Stage 5 - Content Consistency
                self._stage_content_consistency(doc, text_content, result)

                # Stage 6 - Digital Signature Check
                self._stage_signature_check(doc, text_content, file_bytes, result)

                # Stage 7 - Annotation & Form Analysis
                self._stage_annotation_form_analysis(doc, result)

                # Stage 8 - Hidden Content Detection
                self._stage_hidden_content_detection(doc, result)

                # Stage 8b - OCR vs text-layer consistency check.
                # Catches text-over-image tampering where the producer/creator
                # metadata looks clean but the visible glyphs disagree with the
                # PDF text layer (a classic forgery technique).
                self._stage_ocr_consistency(doc, result)

                # Stage 8c - Image-level forensics (ELA, JPEG quant tables, pHash).
                # Stays scoring-weight-neutral; flags feed verdict via severity.
                try:
                    from app.services.image_forensics import run_image_forensics
                    result.flags.extend(run_image_forensics(file_bytes))
                except Exception as exc:
                    result.flags.append(VerificationFlag(
                        "image_forensics", "IMAGE_FORENSICS_ERROR", "info",
                        f"Image forensics raised an unexpected error: {exc}",
                    ))

                # Stage 8d - PDF digital signature validation.
                try:
                    from app.services.pdf_signature_validator import validate_pdf_signature
                    result.flags.extend(validate_pdf_signature(file_bytes))
                except Exception as exc:
                    result.flags.append(VerificationFlag(
                        "signature_validation", "SIGNATURE_CHECK_ERROR", "info",
                        f"Signature validation raised an unexpected error: {exc}",
                    ))

                # Reconcile stage 6's cheap substring detection against stage
                # 8d's real signature-field validator. A bare "/ByteRange" or
                # "/Sig" in the byte stream is trivially spoofable, so the
                # signature-score boost only applies when 8d confirms an
                # actual signature field/object exists.
                self._reconcile_signature_marker(result)

                # Stage 8e - Bank template visual fingerprint match.
                # Bank statements only — completion statements / probate
                # grants legitimately mention banks without using their
                # statement template. The claimed bank is inferred from the
                # PAGE-1 HEADER BAND (the same region that gets hashed): a
                # whole-document keyword scan misattributes statements that
                # merely mention another bank in a transaction narrative.
                try:
                    from app.services.template_fingerprint import (
                        check_template_match, infer_bank_from_header,
                    )
                    if file_category == "bank_statement" and doc.page_count:
                        page1 = doc[0]
                        clip = fitz.Rect(0, 0, page1.rect.width,
                                         page1.rect.height * 0.25)
                        header_text = page1.get_text(clip=clip) or ""
                        bank = infer_bank_from_header(header_text)
                        if bank:
                            result.flags.extend(check_template_match(file_bytes, bank))
                except Exception as exc:
                    result.flags.append(VerificationFlag(
                        "template_fingerprint", "TEMPLATE_CHECK_ERROR", "info",
                        f"Template fingerprint check raised an unexpected error: {exc}",
                    ))

                # Stage 9 - Authenticity Scoring
                self._stage_scoring(result, cfg)
            except Exception as exc:
                # verify_document must never throw — an unexpected stage
                # failure degrades to a blocked result the reviewer can see,
                # never a 500 or a silently missing verification.
                result.authenticity_score = 0.0
                result.verdict = "LikelyTampered"
                result.flags.append(VerificationFlag(
                    "scoring", "PIPELINE_ERROR", "critical",
                    f"Verification pipeline failed with {type(exc).__name__}: {exc}. "
                    "Document could not be verified — treat as unverified.",
                    {"exception_type": type(exc).__name__},
                ))
        finally:
            doc.close()

        return result

    @staticmethod
    def _page_range(doc) -> range:
        """Iterate at most MAX_ANALYSIS_PAGES pages of *doc*."""
        return range(min(doc.page_count, MAX_ANALYSIS_PAGES))

    def _reconcile_signature_marker(self, result: VerificationResult):
        """Apply the stage-6 signature bonus only when stage 8d's validator
        also found a real signature field/object (see verify_document)."""
        sig_res = result.signature_result if isinstance(result.signature_result, dict) else {}
        if not sig_res.get("has_signature"):
            return

        validator_codes = {
            f.code for f in result.flags
            if f.pipeline_stage == "signature_validation"
        }
        validator_confirms = bool(validator_codes & {
            "SIGNATURE_VALID", "SIGNATURE_PRESENT_UNVERIFIED", "SIGNATURE_INVALID",
        })

        if validator_confirms:
            result.flags.append(VerificationFlag(
                "signature", "DIGITAL_SIGNATURE_PRESENT", "info",
                "PDF contains a digital signature."
            ))
            result.signature_score = 100.0
            sig_res["score"] = 100.0
        else:
            result.flags.append(VerificationFlag(
                "signature", "SIGNATURE_MARKER_CONTRADICTION", "info",
                "PDF byte stream contains signature markers (/Sig or /ByteRange) "
                "but no actual signature field/object was found by the signature "
                "validator. The marker may be residual or spoofed; no signature "
                "score bonus applied.",
                {"validator_codes": sorted(validator_codes)},
            ))

    # ------------------------------------------------------------------
    # STAGE 1 - PDF Metadata Analysis
    # ------------------------------------------------------------------

    def _stage_metadata_analysis(self, doc, result: VerificationResult, cfg: Optional[Dict[str, Any]] = None):
        cfg = cfg or self.cfg
        flags: List[VerificationFlag] = []
        score = 100.0

        metadata = doc.metadata or {}
        creator = (metadata.get("creator") or "").lower().strip()
        producer = (metadata.get("producer") or "").lower().strip()
        creation_date = metadata.get("creationDate") or ""
        mod_date = metadata.get("modDate") or ""

        meta_info = {
            "creator": creator,
            "producer": producer,
            "creation_date": creation_date,
            "mod_date": mod_date,
        }

        # Check for suspicious creators/producers
        for suspicious in cfg["suspicious_creators"]:
            if suspicious in creator or suspicious in producer:
                flags.append(VerificationFlag(
                    "metadata", "SUSPICIOUS_CREATOR", "high",
                    f"PDF created with suspicious tool: creator='{creator}', producer='{producer}'. "
                    f"Matched: '{suspicious}'",
                    {"creator": creator, "producer": producer, "matched_tool": suspicious}
                ))
                score -= 30
                break

        # Check if no metadata at all (stripped)
        if not creator and not producer:
            flags.append(VerificationFlag(
                "metadata", "NO_METADATA", "medium",
                "PDF has no creator/producer metadata. Metadata may have been stripped."
            ))
            score -= 15

        # Check date consistency
        if creation_date and mod_date:
            cd = self._parse_pdf_date(creation_date)
            md = self._parse_pdf_date(mod_date)
            if cd and md:
                if md < cd:
                    flags.append(VerificationFlag(
                        "metadata", "DATE_INCONSISTENCY", "high",
                        "PDF modification date is before creation date - likely tampered.",
                        {"creation_date": creation_date, "mod_date": mod_date}
                    ))
                    score -= 25
                elif (md - cd).days > 365:
                    flags.append(VerificationFlag(
                        "metadata", "LARGE_DATE_GAP", "medium",
                        f"PDF modified {(md - cd).days} days after creation.",
                        {"creation_date": creation_date, "mod_date": mod_date}
                    ))
                    score -= 10
        elif creation_date and not mod_date:
            flags.append(VerificationFlag(
                "metadata", "NO_MOD_DATE", "info",
                "PDF has creation date but no modification date."
            ))

        # Check encryption/permission flags
        try:
            if doc.is_encrypted:
                flags.append(VerificationFlag(
                    "metadata", "ENCRYPTED_PDF", "medium",
                    "PDF is encrypted. Checking permission flags.",
                    {"is_encrypted": True}
                ))
                # Check if text copy is disabled (hides text inconsistencies)
                try:
                    # fitz permission bits: bit 5 (16) = copy/extract
                    # If permissions attribute is available, check it
                    perms = getattr(doc, "permissions", None)
                    if perms is not None:
                        # In PyMuPDF, permissions is an int bitmask
                        # Bit 4 (value 16) controls copy/extract permission
                        copy_disabled = not (perms & 16)
                        if copy_disabled:
                            flags.append(VerificationFlag(
                                "metadata", "COPY_DISABLED", "high",
                                "PDF has text copy/extraction disabled. This can be used to hide "
                                "text-layer inconsistencies in tampered documents.",
                                {"permissions_bitmask": perms}
                            ))
                            score -= 20
                except Exception:
                    pass
        except Exception:
            pass

        # Check producer version vs creation date
        try:
            producer_version_ranges = {
                "acrobat 5":   (2001, 2003),
                "acrobat 6":   (2003, 2005),
                "acrobat 7":   (2005, 2007),
                "acrobat 8":   (2007, 2009),
                "acrobat 9":   (2009, 2011),
                "acrobat 10":  (2010, 2013),
                "acrobat x":   (2010, 2013),
                "acrobat 11":  (2012, 2017),
                "acrobat xi":  (2012, 2017),
                "acrobat 15":  (2015, 2017),
                "acrobat dc":  (2015, 2027),
                "acrobat pro dc": (2015, 2027),
                "acrobat 17":  (2017, 2020),
                "acrobat 2017": (2017, 2020),
                "acrobat 20":  (2020, 2025),
                "acrobat 2020": (2020, 2025),
                "prince 9":    (2013, 2016),
                "prince 10":   (2014, 2017),
                "prince 11":   (2016, 2019),
                "prince 12":   (2018, 2021),
                "prince 13":   (2020, 2023),
                "prince 14":   (2022, 2026),
                "itext 5":     (2010, 2020),
                "itext 7":     (2016, 2027),
                "itext 8":     (2023, 2027),
                "wkhtmltopdf":  (2010, 2027),
                "cairo 1.14":  (2014, 2018),
                "cairo 1.15":  (2016, 2020),
                "cairo 1.16":  (2018, 2027),
            }
            if creation_date and producer:
                cd = self._parse_pdf_date(creation_date)
                if cd:
                    creation_year = cd.year
                    for version_key, (start_year, end_year) in producer_version_ranges.items():
                        if version_key in producer:
                            if creation_year < start_year - 1 or creation_year > end_year + 1:
                                flags.append(VerificationFlag(
                                    "metadata", "PRODUCER_DATE_MISMATCH", "high",
                                    f"PDF producer '{producer}' (expected ~{start_year}-{end_year}) "
                                    f"does not match creation year {creation_year}. "
                                    "Document may have been recreated with mismatched tools.",
                                    {"producer": producer, "creation_year": creation_year,
                                     "expected_range": f"{start_year}-{end_year}"}
                                ))
                                score -= 15
                            break
        except Exception:
            pass

        if not flags:
            flags.append(VerificationFlag(
                "metadata", "METADATA_OK", "info",
                "PDF metadata appears consistent."
            ))

        result.metadata_score = max(score, 0.0)
        result.metadata_result = {"score": result.metadata_score, **meta_info}
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 2 - Structural Integrity
    # ------------------------------------------------------------------

    def _stage_structural_integrity(self, doc, file_bytes: bytes, result: VerificationResult):
        flags: List[VerificationFlag] = []
        score = 100.0

        # Count %%EOF markers (incremental saves)
        eof_count = file_bytes.count(b"%%EOF")
        # A digitally-signed PDF legitimately carries exactly one incremental
        # save (the act of signing appends a revision), so 2 %%EOF markers
        # plus a signature marker is expected — do not penalise that shape.
        has_signature_marker = (
            b"/ByteRange" in file_bytes
            or b"/Type /Sig" in file_bytes
            or b"/Type/Sig" in file_bytes
        )
        if eof_count == 2 and has_signature_marker:
            flags.append(VerificationFlag(
                "structural", "MULTIPLE_EOF", "info",
                "PDF has 2 %%EOF markers alongside a digital-signature marker — "
                "consistent with the incremental save produced by signing. Not penalised.",
                {"eof_count": eof_count, "signed_incremental_save": True}
            ))
        elif eof_count > 1:
            flags.append(VerificationFlag(
                "structural", "MULTIPLE_EOF", "medium",
                f"PDF has {eof_count} %%EOF markers indicating {eof_count - 1} incremental save(s). "
                f"This can indicate post-creation editing.",
                {"eof_count": eof_count}
            ))
            score -= min(eof_count * 5, 25)
        else:
            flags.append(VerificationFlag(
                "structural", "SINGLE_EOF", "info",
                "PDF has a single %%EOF marker (no incremental saves detected)."
            ))

        # Count embedded files
        embedded_count = 0
        try:
            embedded_count = doc.embfile_count()
            if embedded_count > 0:
                flags.append(VerificationFlag(
                    "structural", "EMBEDDED_FILES", "medium",
                    f"PDF contains {embedded_count} embedded file(s). Unusual for bank statements.",
                    {"embedded_count": embedded_count}
                ))
                score -= 15
        except Exception:
            pass

        # Count form XObjects (can indicate overlaid content)
        xobject_count = 0
        try:
            for page_num in self._page_range(doc):
                page = doc[page_num]
                xobjects = page.get_images(full=True)
                xobject_count += len(xobjects)
        except Exception:
            pass

        # Check for JavaScript
        has_js = False
        try:
            xref_len = doc.xref_length()
            for i in range(1, min(xref_len, 300)):
                try:
                    obj_str = doc.xref_object(i)
                    if "/JavaScript" in obj_str or "/JS " in obj_str:
                        has_js = True
                        break
                except Exception:
                    continue
        except Exception:
            pass

        if has_js:
            flags.append(VerificationFlag(
                "structural", "HAS_JAVASCRIPT", "high",
                "PDF contains embedded JavaScript. Highly unusual for financial documents.",
            ))
            score -= 25

        # Check page count
        if doc.page_count == 0:
            flags.append(VerificationFlag(
                "structural", "ZERO_PAGES", "critical",
                "PDF has zero pages."
            ))
            score -= 50

        # Orphaned object analysis
        orphaned_ratio = 0.0
        try:
            xref_len = doc.xref_length()
            free_count = 0
            valid_count = 0
            for i in range(1, xref_len):
                try:
                    obj_str = doc.xref_object(i)
                    if not obj_str or obj_str.strip() in ("", "null"):
                        free_count += 1
                    else:
                        valid_count += 1
                except Exception:
                    free_count += 1
            total = free_count + valid_count
            if total > 0:
                orphaned_ratio = free_count / total
                if orphaned_ratio > 0.30:
                    flags.append(VerificationFlag(
                        "structural", "ORPHANED_OBJECTS", "medium",
                        f"PDF has {free_count} free/empty objects out of {total} "
                        f"({orphaned_ratio:.0%}). High ratio indicates heavy editing.",
                        {"free_count": free_count, "valid_count": valid_count,
                         "ratio": round(orphaned_ratio, 3)}
                    ))
                    score -= 10
        except Exception:
            pass

        # NOTE: the old LINEARIZED_MULTI_EOF check was removed — linearized
        # ("fast web view") PDFs legitimately contain 2 %%EOF markers by
        # construction, so flagging that combination penalised genuine
        # bank statement downloads.

        # Cross-reference integrity
        xref_info = {}
        try:
            xref_len = doc.xref_length()
            # Check for /Prev chains (revision count) by scanning trailer
            raw_bytes = file_bytes[-min(len(file_bytes), 4096):]
            raw_str = raw_bytes.decode("latin-1", errors="ignore")
            prev_count = raw_str.count("/Prev")
            # Check trailer /Size vs actual xref length
            size_match = re.search(r"/Size\s+(\d+)", raw_str)
            trailer_size = int(size_match.group(1)) if size_match else None
            xref_info = {
                "xref_length": xref_len,
                "trailer_size": trailer_size,
                "prev_chain_count": prev_count,
            }
            mismatch = False
            if trailer_size is not None and abs(trailer_size - xref_len) > 2:
                mismatch = True
            if prev_count > 2:
                mismatch = True
            if mismatch:
                flags.append(VerificationFlag(
                    "structural", "XREF_INTEGRITY", "medium",
                    f"Cross-reference anomaly detected. Trailer /Size={trailer_size}, "
                    f"actual xref_length={xref_len}, /Prev chains={prev_count}. "
                    "Multiple revisions or xref table manipulation.",
                    xref_info
                ))
                score -= 10
        except Exception:
            pass

        # File size anomaly (per page)
        try:
            if doc.page_count > 0:
                file_size = len(file_bytes)
                size_per_page = file_size / doc.page_count
                # Determine if document is primarily text or image based
                total_images = 0
                for pn in self._page_range(doc):
                    try:
                        total_images += len(doc[pn].get_images(full=True))
                    except Exception:
                        pass
                images_per_page = total_images / doc.page_count if doc.page_count > 0 else 0
                is_image_pdf = images_per_page >= 1.0

                anomaly = False
                if is_image_pdf:
                    if size_per_page < 20 * 1024:  # <20KB/page for image PDF
                        anomaly = True
                        reason = f"Image-heavy PDF has only {size_per_page/1024:.1f} KB/page (expected >20KB)"
                    elif size_per_page > 10 * 1024 * 1024:  # >10MB/page
                        anomaly = True
                        reason = f"Image-heavy PDF has {size_per_page/1024/1024:.1f} MB/page (expected <10MB)"
                else:
                    if size_per_page < 1024:  # <1KB/page for text PDF
                        anomaly = True
                        reason = f"Text PDF has only {size_per_page:.0f} bytes/page (expected >1KB)"
                    elif size_per_page > 2 * 1024 * 1024:  # >2MB/page
                        anomaly = True
                        reason = f"Text PDF has {size_per_page/1024/1024:.1f} MB/page (expected <2MB)"

                if anomaly:
                    flags.append(VerificationFlag(
                        "structural", "FILE_SIZE_ANOMALY", "low",
                        reason,
                        {"file_size": file_size, "page_count": doc.page_count,
                         "size_per_page": round(size_per_page, 1),
                         "is_image_pdf": is_image_pdf}
                    ))
                    score -= 5
        except Exception:
            pass

        # Compression analysis
        try:
            filter_types: Counter = Counter()
            xref_len = doc.xref_length()
            scan_limit = min(xref_len, 500)
            for i in range(1, scan_limit):
                try:
                    obj_str = doc.xref_object(i)
                    filter_matches = re.findall(r"/Filter\s*(?:/(\w+)|\[([^\]]+)\])", obj_str)
                    for match in filter_matches:
                        # match is (single_filter, array_filters)
                        if match[0]:
                            filter_types[match[0]] += 1
                        if match[1]:
                            for f in re.findall(r"/(\w+)", match[1]):
                                filter_types[f] += 1
                except Exception:
                    continue

            archaic_filters = {"LZWDecode", "ASCIIHexDecode", "ASCII85Decode"}
            found_archaic = [f for f in filter_types if f in archaic_filters]
            # Mixed compression = more than 2 different stream filter types
            compression_info = {"filter_types": dict(filter_types)}

            flagged_compression = False
            if found_archaic:
                flags.append(VerificationFlag(
                    "structural", "ARCHAIC_COMPRESSION", "low",
                    f"PDF uses archaic compression filter(s): {', '.join(found_archaic)}. "
                    "These are uncommon in modern documents.",
                    compression_info
                ))
                score -= 5
                flagged_compression = True

            if len(filter_types) > 3 and not flagged_compression:
                flags.append(VerificationFlag(
                    "structural", "MIXED_COMPRESSION", "low",
                    f"PDF uses {len(filter_types)} different compression types: "
                    f"{', '.join(filter_types.keys())}. "
                    "Mixed compression across pages suggests multi-source assembly.",
                    compression_info
                ))
                score -= 5
        except Exception:
            pass

        result.structural_score = max(score, 0.0)
        result.structural_result = {
            "score": result.structural_score,
            "eof_count": eof_count,
            "embedded_count": embedded_count,
            "xobject_count": xobject_count,
            "has_javascript": has_js,
            "page_count": doc.page_count,
            "orphaned_ratio": round(orphaned_ratio, 3),
            "xref_info": xref_info,
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 3 - Font & Text Analysis
    # ------------------------------------------------------------------

    def _stage_font_text_analysis(self, doc, result: VerificationResult):
        flags: List[VerificationFlag] = []
        score = 100.0

        font_names = set()
        text_over_image_pages = 0
        text_over_image_page_list: List[int] = []
        total_pages = min(doc.page_count, MAX_ANALYSIS_PAGES)

        for page_num in range(total_pages):
            page = doc[page_num]

            # Collect fonts used on this page
            try:
                fonts = page.get_fonts()
                for f in fonts:
                    # f is a tuple: (xref, ext, type, basefont, name, encoding, ref-info)
                    if len(f) >= 4:
                        font_names.add(self._normalise_font_name(f[3]))
            except Exception:
                pass

            # Check if page has both images and text (text layered over scan)
            try:
                images = page.get_images(full=True)
                text = page.get_text().strip()
                if images and text and len(text) > 50:
                    # Page has substantial text AND images - possible overlay
                    # Check if any image covers most of the page
                    for img in images:
                        try:
                            img_rect = page.get_image_rects(img[0])
                            if img_rect:
                                for rect in img_rect:
                                    page_area = page.rect.width * page.rect.height
                                    img_area = rect.width * rect.height
                                    if page_area > 0 and (img_area / page_area) > 0.5:
                                        text_over_image_pages += 1
                                        text_over_image_page_list.append(page_num)
                                        break
                        except Exception:
                            continue
            except Exception:
                pass

        # Analyze font consistency
        if len(font_names) > 8:
            flags.append(VerificationFlag(
                "font_text", "EXCESSIVE_FONTS", "medium",
                f"PDF uses {len(font_names)} different fonts. Genuine bank statements typically use 2-4.",
                {"font_count": len(font_names), "fonts": list(font_names)[:10]}
            ))
            score -= 15
        elif len(font_names) == 0 and total_pages > 0:
            flags.append(VerificationFlag(
                "font_text", "NO_FONTS", "low",
                "No embedded fonts detected. PDF may be a scanned image."
            ))
            score -= 5
        else:
            flags.append(VerificationFlag(
                "font_text", "FONTS_OK", "info",
                f"PDF uses {len(font_names)} font(s), within normal range."
            ))

        # Text over image detection
        if text_over_image_pages > 0:
            pct = text_over_image_pages / total_pages if total_pages > 0 else 0
            if pct > 0.5:
                flags.append(VerificationFlag(
                    "font_text", "TEXT_OVER_IMAGE", "high",
                    f"Text is layered over full-page images on {text_over_image_pages} of {total_pages} pages. "
                    "This is a common tampering pattern.",
                    {"affected_pages": text_over_image_pages, "total_pages": total_pages,
                     "page_numbers": text_over_image_page_list}
                ))
                score -= 25
            else:
                flags.append(VerificationFlag(
                    "font_text", "PARTIAL_TEXT_OVERLAY", "low",
                    f"Some pages ({text_over_image_pages} of {total_pages}) have text layered over images.",
                    {"affected_pages": text_over_image_pages, "total_pages": total_pages,
                     "page_numbers": text_over_image_page_list}
                ))
                score -= 5

        # Page-level consistency check
        page_profiles: List[Dict[str, Any]] = []
        inconsistent_pages: List[int] = []
        cropped_pages: List[int] = []
        try:
            for page_num in range(total_pages):
                page = doc[page_num]
                try:
                    mediabox = tuple(round(x, 1) for x in page.mediabox)
                    cropbox = tuple(round(x, 1) for x in page.cropbox)
                    rotation = page.rotation
                    page_fonts = set()
                    try:
                        for f in page.get_fonts():
                            if len(f) >= 4:
                                page_fonts.add(self._normalise_font_name(f[3]))
                    except Exception:
                        pass
                    profile = {
                        "page": page_num,
                        "mediabox": mediabox,
                        "cropbox": cropbox,
                        "rotation": rotation,
                        "dimensions": (round(page.rect.width, 1), round(page.rect.height, 1)),
                        "font_set": frozenset(page_fonts),
                    }
                    page_profiles.append(profile)

                    # Check mediabox != cropbox (cropping)
                    if mediabox != cropbox:
                        cropped_pages.append(page_num)
                except Exception:
                    continue

            if len(page_profiles) >= 2:
                # Find the majority dimension/rotation
                dim_counter: Counter = Counter()
                rot_counter: Counter = Counter()
                for p in page_profiles:
                    dim_counter[p["dimensions"]] += 1
                    rot_counter[p["rotation"]] += 1

                majority_dim = dim_counter.most_common(1)[0][0] if dim_counter else None
                majority_rot = rot_counter.most_common(1)[0][0] if rot_counter else None

                for p in page_profiles:
                    if p["dimensions"] != majority_dim or p["rotation"] != majority_rot:
                        inconsistent_pages.append(p["page"])

                if inconsistent_pages:
                    flags.append(VerificationFlag(
                        "font_text", "PAGE_INCONSISTENCY", "high",
                        f"Pages {inconsistent_pages} have different dimensions or rotation "
                        f"from the majority. This may indicate page replacement.",
                        {"inconsistent_pages": inconsistent_pages,
                         "page_numbers": inconsistent_pages,
                         "majority_dimensions": majority_dim,
                         "majority_rotation": majority_rot}
                    ))
                    score -= 20

                if cropped_pages:
                    flags.append(VerificationFlag(
                        "font_text", "CROPPED_PAGES", "medium",
                        f"Pages {cropped_pages} have mediabox != cropbox, indicating cropping.",
                        {"cropped_pages": cropped_pages, "page_numbers": cropped_pages}
                    ))
                    score -= 5
        except Exception:
            pass

        # Watermark/header consistency check.
        # Page 0 is exempt: page 1 of a genuine statement always carries a
        # different, larger header (logo, address block) than the
        # continuation pages, so it must not be compared against them.
        # Only flag when CONTINUATION pages disagree with each other.
        try:
            if total_pages >= 3:
                header_texts: Dict[int, str] = {}
                for page_num in range(1, total_pages):
                    page = doc[page_num]
                    try:
                        # Extract text from top 15% of each page
                        page_height = page.rect.height
                        header_clip = page.rect + (0, 0, 0, -(page_height * 0.85))
                        header_text = page.get_text("text", clip=header_clip).strip()

                        # Normalize: remove page numbers and dates
                        normalized = re.sub(r"\b\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b", "", header_text)
                        normalized = re.sub(r"\bpage\s*\d+\b", "", normalized, flags=re.IGNORECASE)
                        normalized = re.sub(r"^\s*\d+\s*$", "", normalized, flags=re.MULTILINE)
                        normalized = re.sub(r"\s+", " ", normalized).strip()
                        header_texts[page_num] = normalized
                    except Exception:
                        header_texts[page_num] = ""

                # Compare continuation-page headers: find majority header
                non_empty_headers = [h for h in header_texts.values() if h]
                if len(non_empty_headers) >= 2:
                    header_counter: Counter = Counter(non_empty_headers)
                    majority_header, majority_count = header_counter.most_common(1)[0]
                    differing_pages = []
                    for idx, h in sorted(header_texts.items()):
                        if h and h != majority_header:
                            differing_pages.append(idx)

                    # Only flag if minority pages exist and it is not just empty vs non-empty
                    if differing_pages and len(differing_pages) < len(non_empty_headers):
                        flags.append(VerificationFlag(
                            "font_text", "HEADER_INCONSISTENCY", "high",
                            f"Continuation pages {differing_pages} have different header/"
                            f"watermark text compared to the majority ({majority_count} pages). "
                            "This may indicate pages sourced from different documents. "
                            "(Page 1 is exempt — its header legitimately differs.)",
                            {"differing_pages": differing_pages,
                             "page_numbers": differing_pages,
                             "total_pages": total_pages,
                             "majority_header_preview": majority_header[:100]}
                        ))
                        score -= 20
        except Exception:
            pass

        result.font_text_score = max(score, 0.0)
        result.font_text_result = {
            "score": result.font_text_score,
            "font_count": len(font_names),
            "fonts": list(font_names)[:10],
            "text_over_image_pages": text_over_image_pages,
            "total_pages": total_pages,
            "inconsistent_pages": inconsistent_pages,
            "cropped_pages": cropped_pages,
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 4 - Image Analysis
    # ------------------------------------------------------------------

    def _stage_image_analysis(self, doc, result: VerificationResult):
        flags: List[VerificationFlag] = []
        score = 100.0

        dpis: List[float] = []
        image_count = 0

        for page_num in self._page_range(doc):
            page = doc[page_num]
            try:
                images = page.get_images(full=True)
                for img_info in images:
                    image_count += 1
                    xref = img_info[0]
                    try:
                        # Get image dimensions
                        img_width = img_info[2]
                        img_height = img_info[3]

                        # Get rendered size on page
                        rects = page.get_image_rects(xref)
                        if rects:
                            for rect in rects:
                                rendered_w = rect.width
                                rendered_h = rect.height
                                if rendered_w > 0 and rendered_h > 0:
                                    dpi_x = (img_width / rendered_w) * 72
                                    dpi_y = (img_height / rendered_h) * 72
                                    dpis.append((dpi_x + dpi_y) / 2)
                    except Exception:
                        continue
            except Exception:
                continue

        if dpis:
            min_dpi = min(dpis)
            max_dpi = max(dpis)
            avg_dpi = sum(dpis) / len(dpis)

            # Check DPI consistency
            if max_dpi > 0 and min_dpi > 0:
                dpi_ratio = max_dpi / min_dpi
                if dpi_ratio > 3.0:
                    flags.append(VerificationFlag(
                        "image", "DPI_INCONSISTENCY", "high",
                        f"Embedded images have highly inconsistent DPI (range: {min_dpi:.0f}-{max_dpi:.0f}). "
                        "This may indicate images from different sources were combined.",
                        {"min_dpi": round(min_dpi, 1), "max_dpi": round(max_dpi, 1),
                         "avg_dpi": round(avg_dpi, 1), "image_count": image_count}
                    ))
                    score -= 25
                elif dpi_ratio > 1.5:
                    flags.append(VerificationFlag(
                        "image", "DPI_VARIATION", "low",
                        f"Some variation in image DPI (range: {min_dpi:.0f}-{max_dpi:.0f}).",
                        {"min_dpi": round(min_dpi, 1), "max_dpi": round(max_dpi, 1)}
                    ))
                    score -= 5
                else:
                    flags.append(VerificationFlag(
                        "image", "DPI_CONSISTENT", "info",
                        f"Image DPI is consistent (avg: {avg_dpi:.0f})."
                    ))

            # Very low DPI on important images
            if min_dpi < 50:
                flags.append(VerificationFlag(
                    "image", "LOW_DPI_IMAGE", "medium",
                    f"Very low DPI image detected ({min_dpi:.0f} DPI). May indicate poor quality scan or screenshot.",
                ))
                score -= 10
        elif image_count == 0:
            flags.append(VerificationFlag(
                "image", "NO_IMAGES", "info",
                "No embedded images found in PDF."
            ))
        else:
            flags.append(VerificationFlag(
                "image", "DPI_UNKNOWN", "info",
                f"Found {image_count} image(s) but could not determine DPI."
            ))

        # Color profile analysis
        color_spaces_per_page: Dict[int, set] = {}
        all_color_spaces: Counter = Counter()
        try:
            xref_len = doc.xref_length()
            # Build a mapping of image xrefs to their color spaces
            image_colorspaces: Dict[int, str] = {}
            for i in range(1, min(xref_len, 1000)):
                try:
                    obj_str = doc.xref_object(i)
                    if "/Subtype /Image" in obj_str or "/Subtype/Image" in obj_str:
                        cs_match = re.search(
                            r"/ColorSpace\s*(/\w+|/Device\w+|/ICCBased|/CalRGB|/CalGray|/Lab|/Indexed)",
                            obj_str
                        )
                        if cs_match:
                            cs = cs_match.group(1).strip("/")
                            image_colorspaces[i] = cs
                            all_color_spaces[cs] += 1
                except Exception:
                    continue

            # Map color spaces per page
            for page_num in self._page_range(doc):
                try:
                    page = doc[page_num]
                    page_images = page.get_images(full=True)
                    page_cs = set()
                    for img in page_images:
                        xref = img[0]
                        if xref in image_colorspaces:
                            page_cs.add(image_colorspaces[xref])
                    if page_cs:
                        color_spaces_per_page[page_num] = page_cs
                except Exception:
                    continue

            # Check for mixed CMYK + RGB across pages
            has_cmyk = any("CMYK" in cs for cs in all_color_spaces)
            has_rgb = any("RGB" in cs for cs in all_color_spaces)
            if has_cmyk and has_rgb:
                flags.append(VerificationFlag(
                    "image", "MIXED_COLOR_PROFILES", "medium",
                    "PDF contains both CMYK and RGB color spaces across images. "
                    "This suggests images from multiple sources were combined.",
                    {"color_spaces": dict(all_color_spaces)}
                ))
                score -= 10
        except Exception:
            pass

        result.image_score = max(score, 0.0)
        result.image_result = {
            "score": result.image_score,
            "image_count": image_count,
            "dpis": [round(d, 1) for d in dpis[:20]],
            "color_spaces": dict(all_color_spaces),
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 5 - Content Consistency
    # ------------------------------------------------------------------

    def _stage_content_consistency(self, doc, text_content: str, result: VerificationResult):
        flags: List[VerificationFlag] = []
        score = 100.0

        metadata = doc.metadata or {}
        creation_date_str = metadata.get("creationDate") or ""

        # Extract dates from content. Word boundaries keep long reference
        # numbers (e.g. "1201/01/20261") from parsing as dates.
        date_patterns = [
            r"\b\d{2}/\d{2}/\d{4}\b",
            r"\b\d{2}\s+\w{3}\s+\d{4}\b",
            r"\b\d{2}-\d{2}-\d{4}\b",
            r"\b\d{4}-\d{2}-\d{2}\b",
        ]

        content_dates: List[datetime] = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text_content)
            for m in matches:
                parsed = self._parse_content_date(m)
                if parsed:
                    content_dates.append(parsed)

        if content_dates and creation_date_str:
            cd = self._parse_pdf_date(creation_date_str)
            if cd:
                # Check if content dates make sense relative to creation date
                earliest_content = min(content_dates)
                latest_content = max(content_dates)

                # Content dates significantly after creation date is suspicious
                if earliest_content > cd:
                    days_after = (earliest_content - cd).days
                    if days_after > 180:
                        flags.append(VerificationFlag(
                            "content_consistency", "CONTENT_AFTER_CREATION", "high",
                            f"Content dates are {days_after} days after PDF creation date. "
                            "Document may have been backdated.",
                            {"creation_date": creation_date_str,
                             "earliest_content_date": earliest_content.strftime("%Y-%m-%d")}
                        ))
                        score -= 25

                # Content dates significantly before creation date is normal
                # (statement generated after the period it covers)

                # Check for future dates in content. Genuine statements
                # legitimately carry near-future dates (payment due date,
                # next statement date), so allow up to 45 days ahead.
                future_cutoff = datetime.now() + timedelta(days=45)
                future_dates = [d for d in content_dates if d > future_cutoff]
                if future_dates:
                    flags.append(VerificationFlag(
                        "content_consistency", "FUTURE_DATES", "high",
                        f"Document contains {len(future_dates)} date(s) more than "
                        "45 days in the future.",
                        {"future_date_count": len(future_dates),
                         "allowance_days": 45}
                    ))
                    score -= 20

        # Check for mixed date formats (can indicate manual editing)
        format_counts = Counter()
        for pattern in date_patterns:
            matches = re.findall(pattern, text_content)
            if matches:
                format_counts[pattern] = len(matches)

        if len(format_counts) > 2:
            flags.append(VerificationFlag(
                "content_consistency", "MIXED_DATE_FORMATS", "medium",
                f"Document uses {len(format_counts)} different date formats. "
                "Genuine documents typically use a single format.",
                {"format_counts": dict(format_counts)}
            ))
            score -= 10

        if not flags:
            flags.append(VerificationFlag(
                "content_consistency", "CONTENT_OK", "info",
                "Content dates appear consistent with metadata."
            ))

        result.content_consistency_score = max(score, 0.0)
        result.content_consistency_result = {
            "score": result.content_consistency_score,
            "content_dates_found": len(content_dates),
            "date_formats_used": len(format_counts),
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 6 - Digital Signature Check
    # ------------------------------------------------------------------

    def _stage_signature_check(self, doc, text_content: str, file_bytes: bytes, result: VerificationResult):
        flags: List[VerificationFlag] = []
        score = 80.0  # Start at 80 - signatures are a bonus

        # Check for digital signatures in the PDF
        has_signature = False
        try:
            # Look for signature objects in PDF structure
            xref_len = doc.xref_length()
            for i in range(1, min(xref_len, 500)):
                try:
                    obj_str = doc.xref_object(i)
                    if "/Sig" in obj_str or "/ByteRange" in obj_str:
                        has_signature = True
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Also check raw bytes for signature markers
        if not has_signature:
            if b"/Type /Sig" in file_bytes or b"/SubFilter /adbe.pkcs7" in file_bytes:
                has_signature = True

        # Identify the bank from content
        identified_bank = None
        text_lower = text_content.lower()
        for bank_name, bank_info in BANK_SIGNATURE_EXPECTATIONS.items():
            for kw in bank_info["keywords"]:
                if kw in text_lower:
                    identified_bank = bank_name
                    break
            if identified_bank:
                break

        if has_signature:
            # Marker only — a bare "/Sig" or "/ByteRange" substring is
            # spoofable, so the DIGITAL_SIGNATURE_PRESENT flag and the
            # score boost to 100 are deferred until stage 8d's validator
            # confirms a real signature field/object exists (see
            # _reconcile_signature_marker in verify_document).
            pass
        else:
            if identified_bank and BANK_SIGNATURE_EXPECTATIONS[identified_bank]["expects_signature"]:
                flags.append(VerificationFlag(
                    "signature", "EXPECTED_SIGNATURE_MISSING", "medium",
                    f"Document appears to be from {identified_bank}, which typically includes "
                    "digital signatures on official statements. No signature found.",
                    {"identified_bank": identified_bank}
                ))
                score -= 20
            else:
                flags.append(VerificationFlag(
                    "signature", "NO_SIGNATURE", "info",
                    "No digital signature found. Many legitimate documents lack signatures."
                ))

        result.signature_score = max(score, 0.0)
        result.signature_result = {
            "score": result.signature_score,
            "has_signature": has_signature,
            "identified_bank": identified_bank,
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 7 - Annotation & Form Analysis
    # ------------------------------------------------------------------

    def _stage_annotation_form_analysis(self, doc, result: VerificationResult):
        flags: List[VerificationFlag] = []
        score = 100.0

        total_annotations = 0
        freetext_count = 0
        redact_count = 0
        link_count = 0
        annotation_types: Counter = Counter()
        is_form = False
        widget_count = 0
        signature_widget_count = 0
        text_input_count = 0
        freetext_annotation_pages: List[int] = []
        redact_annotation_pages: List[int] = []
        text_input_field_pages: List[int] = []
        fake_redaction_pages: List[int] = []

        # PyMuPDF widget-type constants (fall back to the documented values
        # if an older fitz build lacks the names): TEXT=7, SIGNATURE=6.
        try:
            import fitz as _fitz_const
            WIDGET_TYPE_TEXT = getattr(_fitz_const, "PDF_WIDGET_TYPE_TEXT", 7)
            WIDGET_TYPE_SIGNATURE = getattr(_fitz_const, "PDF_WIDGET_TYPE_SIGNATURE", 6)
        except Exception:
            WIDGET_TYPE_TEXT = 7
            WIDGET_TYPE_SIGNATURE = 6

        for page_num in self._page_range(doc):
            page = doc[page_num]

            # Annotation detection
            try:
                annots = page.annots()
                if annots:
                    for annot in annots:
                        try:
                            total_annotations += 1
                            annot_type = annot.type[1] if annot.type else "Unknown"
                            annotation_types[annot_type] += 1
                            if annot_type == "FreeText":
                                freetext_count += 1
                                if page_num not in freetext_annotation_pages:
                                    freetext_annotation_pages.append(page_num)
                            elif annot_type == "Redact":
                                redact_count += 1
                                if page_num not in redact_annotation_pages:
                                    redact_annotation_pages.append(page_num)
                            elif annot_type == "Link":
                                # Hyperlinks are near-universal in genuine
                                # bank PDFs — whitelisted below.
                                link_count += 1
                        except Exception:
                            total_annotations += 1
                            continue
            except Exception:
                pass

            # Form field (widget) detection
            try:
                widgets = page.widgets()
                if widgets:
                    for widget in widgets:
                        try:
                            widget_count += 1
                            # PyMuPDF field types: 0=unknown, 1=Button,
                            # 2=CheckBox, 3=ComboBox, 4=ListBox,
                            # 5=RadioButton, 6=Signature, 7=Text
                            ft = getattr(widget, "field_type", None)
                            if ft == WIDGET_TYPE_SIGNATURE:
                                signature_widget_count += 1  # Signature fields are normal
                            elif ft == WIDGET_TYPE_TEXT:
                                text_input_count += 1
                                if page_num not in text_input_field_pages:
                                    text_input_field_pages.append(page_num)
                        except Exception:
                            continue
            except Exception:
                pass

            # Fake redaction detection: black rectangles with text underneath
            try:
                drawings = page.get_drawings()
                for drawing in drawings:
                    try:
                        fill = drawing.get("fill")
                        rect_items = drawing.get("items", [])
                        if not fill:
                            continue
                        # Check if fill is near-black (all channels close to 0)
                        is_black = False
                        if isinstance(fill, (tuple, list)):
                            if len(fill) == 3:
                                is_black = all(c <= 0.05 for c in fill)
                            elif len(fill) == 1:
                                is_black = fill[0] <= 0.05
                            elif len(fill) == 4:
                                # CMYK: black = high K or all CMY high
                                is_black = fill[3] >= 0.95 or all(c >= 0.95 for c in fill[:3])

                        if is_black and rect_items:
                            # Get the bounding rectangle of this drawing
                            d_rect = drawing.get("rect")
                            if d_rect:
                                import fitz as _fitz
                                clip = _fitz.Rect(d_rect)
                                # Check for text underneath the black rectangle
                                text_under = page.get_text("text", clip=clip).strip()
                                # Z-order check: a black fill BEHIND text (e.g. a
                                # dark table-cell background) is legitimate. Only
                                # flag when a render of the region shows the text
                                # is actually hidden by the fill.
                                if (text_under and len(text_under) > 2
                                        and self._covered_text_hidden(page, clip, expect_dark=True)):
                                    fake_redaction_pages.append(page_num)
                                    break  # One per page is enough
                    except Exception:
                        continue
            except Exception:
                pass

        # Score annotations
        if freetext_count > 0:
            flags.append(VerificationFlag(
                "annotation_form", "FREETEXT_ANNOTATIONS", "high",
                f"PDF contains {freetext_count} FreeText annotation(s). "
                "These allow arbitrary text overlays and are a common tampering method.",
                {"freetext_count": freetext_count, "page_numbers": freetext_annotation_pages}
            ))
            score -= 20

        if redact_count > 0:
            flags.append(VerificationFlag(
                "annotation_form", "REDACT_ANNOTATIONS", "critical",
                f"PDF contains {redact_count} Redact annotation(s). "
                "Redaction annotations can be used to hide original content.",
                {"redact_count": redact_count, "page_numbers": redact_annotation_pages}
            ))
            score -= 40

        # Link annotations (hyperlinks) are near-universal in genuine bank
        # PDFs, so they are whitelisted: a document whose only annotations
        # are Links gets an info note, not a penalty.
        non_link_other = total_annotations - freetext_count - redact_count - link_count
        if non_link_other > 0 and freetext_count == 0 and redact_count == 0:
            flags.append(VerificationFlag(
                "annotation_form", "HAS_ANNOTATIONS", "medium",
                f"PDF contains {non_link_other} annotation(s) of types: "
                f"{dict(annotation_types)}. Annotations (other than hyperlinks) "
                "are unusual on bank statements.",
                {"total_annotations": total_annotations,
                 "link_count": link_count,
                 "annotation_types": dict(annotation_types)}
            ))
            score -= 5
        elif link_count > 0 and non_link_other == 0 and freetext_count == 0 and redact_count == 0:
            flags.append(VerificationFlag(
                "annotation_form", "ANNOTATIONS_OK", "info",
                f"PDF contains {link_count} hyperlink annotation(s) only — "
                "normal for bank statements.",
                {"link_count": link_count}
            ))

        # Score form fields
        if text_input_count > 0:
            flags.append(VerificationFlag(
                "annotation_form", "TEXT_INPUT_FIELDS", "critical",
                f"PDF contains {text_input_count} text input form field(s). "
                "Bank statements should NEVER have editable text input fields. "
                "This is a strong indicator of a fillable template used for forgery.",
                {"text_input_count": text_input_count, "total_widgets": widget_count,
                 "page_numbers": text_input_field_pages}
            ))
            score -= 40
        elif widget_count - signature_widget_count > 0:
            # Signature fields are normal; only non-signature widgets count.
            flags.append(VerificationFlag(
                "annotation_form", "HAS_FORM_FIELDS", "high",
                f"PDF contains {widget_count - signature_widget_count} form field(s) "
                "(excluding signature fields). "
                "Bank statements should not contain form fields.",
                {"widget_count": widget_count,
                 "signature_widget_count": signature_widget_count}
            ))
            score -= 25

        # Check if it is a form PDF
        try:
            is_form = doc.is_form_pdf
            if is_form and widget_count == 0:
                # Form PDF structure but no widgets found — still suspicious
                flags.append(VerificationFlag(
                    "annotation_form", "FORM_PDF_STRUCTURE", "high",
                    "PDF has form-PDF internal structure (AcroForm) even though no "
                    "active widgets were found. This is unusual for bank statements.",
                ))
                score -= 10
        except Exception:
            pass

        # Fake redaction
        if fake_redaction_pages:
            unique_pages = sorted(set(fake_redaction_pages))
            flags.append(VerificationFlag(
                "annotation_form", "FAKE_REDACTION", "critical",
                f"Black rectangles with readable text underneath detected on pages "
                f"{unique_pages}. Original content is still extractable beneath black "
                "cover — this is a 'fake redaction' tampering technique.",
                {"affected_pages": unique_pages, "page_numbers": unique_pages}
            ))
            score -= 40

        if not flags:
            flags.append(VerificationFlag(
                "annotation_form", "ANNOTATIONS_OK", "info",
                "No suspicious annotations or form fields detected."
            ))

        result.annotation_form_score = max(score, 0.0)
        result.annotation_form_result = {
            "score": result.annotation_form_score,
            "total_annotations": total_annotations,
            "annotation_types": dict(annotation_types),
            "freetext_count": freetext_count,
            "redact_count": redact_count,
            "link_count": link_count,
            "is_form_pdf": is_form,
            "widget_count": widget_count,
            "signature_widget_count": signature_widget_count,
            "text_input_count": text_input_count,
            "fake_redaction_pages": sorted(set(fake_redaction_pages)),
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 8 - Hidden Content Detection
    # ------------------------------------------------------------------

    def _stage_hidden_content_detection(self, doc, result: VerificationResult):
        flags: List[VerificationFlag] = []
        score = 100.0

        # Hidden layers (OCGs - Optional Content Groups)
        ocg_count = 0
        hidden_ocg_count = 0
        try:
            ocgs = doc.get_ocgs()
            if ocgs:
                ocg_count = len(ocgs)
                for xref, ocg_info in ocgs.items():
                    try:
                        # ocg_info is a dict with 'name', 'intent', 'on', 'usage'
                        if isinstance(ocg_info, dict):
                            if not ocg_info.get("on", True):
                                hidden_ocg_count += 1
                    except Exception:
                        continue

                if hidden_ocg_count > 0:
                    flags.append(VerificationFlag(
                        "hidden_content", "HIDDEN_LAYERS", "critical",
                        f"PDF contains {hidden_ocg_count} hidden layer(s) (OCGs with on=False) "
                        f"out of {ocg_count} total. Hidden layers can conceal original or "
                        "alternate content.",
                        {"ocg_count": ocg_count, "hidden_ocg_count": hidden_ocg_count}
                    ))
                    score -= 40
                elif ocg_count > 0:
                    flags.append(VerificationFlag(
                        "hidden_content", "HAS_LAYERS", "high",
                        f"PDF contains {ocg_count} optional content group(s) (layers). "
                        "Layers are unusual in bank statements and may indicate editing.",
                        {"ocg_count": ocg_count}
                    ))
                    score -= 20
        except Exception:
            pass

        # Whited-out content detection
        whiteout_pages: List[int] = []
        try:
            for page_num in self._page_range(doc):
                page = doc[page_num]
                try:
                    drawings = page.get_drawings()
                    for drawing in drawings:
                        try:
                            fill = drawing.get("fill")
                            if not fill:
                                continue

                            # Check if fill is near-white (all channels > 0.95)
                            is_white = False
                            if isinstance(fill, (tuple, list)):
                                if len(fill) == 3:
                                    is_white = all(c > 0.95 for c in fill)
                                elif len(fill) == 1:
                                    is_white = fill[0] > 0.95
                                elif len(fill) == 4:
                                    # CMYK: white = all channels near 0
                                    is_white = all(c < 0.05 for c in fill)

                            # Check opacity if available
                            opacity = drawing.get("fill_opacity", 1.0)
                            if opacity is None:
                                opacity = 1.0

                            if is_white and opacity > 0.9:
                                d_rect = drawing.get("rect")
                                if d_rect:
                                    import fitz as _fitz
                                    clip = _fitz.Rect(d_rect)
                                    # Must be a reasonably sized rectangle (not tiny decorative elements)
                                    if clip.width > 10 and clip.height > 5:
                                        # Check for text underneath the white rectangle
                                        text_blocks = page.get_text("dict", clip=clip)
                                        text_under = ""
                                        if text_blocks and "blocks" in text_blocks:
                                            for block in text_blocks["blocks"]:
                                                if block.get("type") == 0:  # text block
                                                    for line in block.get("lines", []):
                                                        for span in line.get("spans", []):
                                                            text_under += span.get("text", "")
                                        text_under = text_under.strip()
                                        # Z-order check: white fills BEHIND text
                                        # (table-cell backgrounds, zebra stripes)
                                        # are ubiquitous in genuine statements.
                                        # Only flag when a render shows the text
                                        # is actually hidden by the fill.
                                        if (text_under and len(text_under) > 2
                                                and self._covered_text_hidden(page, clip, expect_dark=False)):
                                            whiteout_pages.append(page_num)
                                            break  # One per page is enough
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception:
            pass

        if whiteout_pages:
            unique_pages = sorted(set(whiteout_pages))
            flags.append(VerificationFlag(
                "hidden_content", "WHITED_OUT_CONTENT", "critical",
                f"White rectangles with readable text underneath detected on pages "
                f"{unique_pages}. Original content is still extractable beneath white "
                "cover-up — this is a common document tampering technique.",
                {"affected_pages": unique_pages, "page_numbers": unique_pages}
            ))
            score -= 40

        if not flags:
            flags.append(VerificationFlag(
                "hidden_content", "HIDDEN_CONTENT_OK", "info",
                "No hidden layers or whited-out content detected."
            ))

        result.hidden_content_score = max(score, 0.0)
        result.hidden_content_result = {
            "score": result.hidden_content_score,
            "ocg_count": ocg_count,
            "hidden_ocg_count": hidden_ocg_count,
            "whiteout_pages": sorted(set(whiteout_pages)),
        }
        result.flags.extend(flags)

    # ------------------------------------------------------------------
    # STAGE 8b - OCR vs text-layer consistency
    # ------------------------------------------------------------------
    def _stage_ocr_consistency(self, doc, result: VerificationResult):
        """Compare the PDF text layer against an OCR pass over the rendered page.

        A common forgery is to lay edited text on top of an image of the
        original document. The visible glyphs differ from the embedded text
        layer. We catch that by rasterising each page at 150 dpi, running
        Tesseract on the image, and comparing the two strings.

        Performance-sensitive — capped at the first 10 pages with a text
        layer, 150 dpi, and a 1.5s per-page Tesseract budget. The stage is
        wrapped in a single try/except so any OCR/runtime failure degrades
        gracefully without breaking the rest of the pipeline.
        """
        MAX_PAGES = 10
        DPI = 150
        # Mismatch thresholds (per page)
        MIN_LEN_FOR_CHECK = 80          # below this the text layer is too short to compare meaningfully
        LEN_DELTA_THRESHOLD = 0.25       # relative length difference
        RATIO_THRESHOLD = 0.60           # difflib similarity ratio

        try:
            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image
            import io
        except ImportError as exc:
            # OCR libraries not installed — record an info flag and bail.
            result.flags.append(VerificationFlag(
                "ocr_consistency", "OCR_UNAVAILABLE", "info",
                f"OCR check skipped (missing dependency: {exc.name}).",
                {"error": str(exc)},
            ))
            return

        suspicious_pages: List[Dict[str, Any]] = []
        pages_checked = 0
        ocr_errors = 0

        for page_num, page in enumerate(doc):
            if pages_checked >= MAX_PAGES:
                break

            text_layer = (page.get_text() or "").strip()
            if len(text_layer) < MIN_LEN_FOR_CHECK:
                # Image-only or near-empty page — different category of issue,
                # not what this stage is looking for.
                continue

            try:
                pix = page.get_pixmap(dpi=DPI, alpha=False)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                # `timeout` is supported by Tesseract via the wrapper; if the
                # OCR call hangs on a page we move on.
                ocr_text = pytesseract.image_to_string(img, timeout=15) or ""
            except RuntimeError:
                # pytesseract raises RuntimeError on timeout
                ocr_errors += 1
                continue
            except Exception:
                ocr_errors += 1
                continue

            pages_checked += 1

            norm_text = _normalise_for_compare(text_layer)
            norm_ocr = _normalise_for_compare(ocr_text)
            if not norm_ocr or len(norm_ocr) < MIN_LEN_FOR_CHECK:
                # OCR couldn't read enough — skip rather than false-positive
                continue

            len_delta = abs(len(norm_text) - len(norm_ocr)) / max(len(norm_text), 1)
            ratio = SequenceMatcher(None, norm_text, norm_ocr).ratio()

            if len_delta > LEN_DELTA_THRESHOLD and ratio < RATIO_THRESHOLD:
                suspicious_pages.append({
                    "page": page_num + 1,                     # 1-indexed for display
                    "text_layer_chars": len(norm_text),
                    "ocr_chars": len(norm_ocr),
                    "length_delta_pct": round(len_delta * 100, 1),
                    "similarity_ratio": round(ratio, 3),
                })

        details: Dict[str, Any] = {
            "pages_checked": pages_checked,
            "ocr_errors": ocr_errors,
            "suspicious_pages": suspicious_pages,
            "thresholds": {
                "length_delta_pct": LEN_DELTA_THRESHOLD * 100,
                "min_similarity_ratio": RATIO_THRESHOLD,
            },
        }

        if suspicious_pages:
            page_list = ", ".join(str(p["page"]) for p in suspicious_pages)
            result.flags.append(VerificationFlag(
                "ocr_consistency", "TEXT_LAYER_OCR_MISMATCH", "high",
                f"PDF text layer disagrees with rendered text on page(s) {page_list}. "
                "Common indicator of text-over-image tampering.",
                {
                    **details,
                    # page_numbers in flag.details lets the UI highlight pages
                    "page_numbers": [p["page"] - 1 for p in suspicious_pages],
                },
            ))
        elif pages_checked > 0:
            result.flags.append(VerificationFlag(
                "ocr_consistency", "OCR_CONSISTENCY_OK", "info",
                f"OCR matches text layer on {pages_checked} sampled page(s).",
                details,
            ))

    # ------------------------------------------------------------------
    # STAGE 9 - Scoring & Classification
    # ------------------------------------------------------------------

    def _stage_scoring(self, result: VerificationResult, cfg: Optional[Dict[str, Any]] = None):
        w = cfg or self.cfg
        weighted_score = (
            result.metadata_score              * w["weight_metadata"] +
            result.structural_score            * w["weight_structural"] +
            result.font_text_score             * w["weight_font_text"] +
            result.image_score                 * w["weight_image"] +
            result.content_consistency_score   * w["weight_content_consistency"] +
            result.signature_score             * w["weight_signature"] +
            result.annotation_form_score       * w["weight_annotation_form"] +
            result.hidden_content_score        * w["weight_hidden_content"]
        )

        result.authenticity_score = round(weighted_score, 1)

        # Shared verdict rule — critical flags force LikelyTampered
        # regardless of score; >=2 high flags force Suspicious.
        result.verdict = compute_verdict(
            result.authenticity_score,
            [f.severity for f in result.flags],
            w,
        )

        result.flags.append(VerificationFlag(
            "scoring", "FINAL_SCORE", "info",
            f"Authenticity score: {result.authenticity_score}/100 -> {result.verdict}",
            {
                "metadata": result.metadata_score,
                "structural": result.structural_score,
                "font_text": result.font_text_score,
                "image": result.image_score,
                "content_consistency": result.content_consistency_score,
                "signature": result.signature_score,
                "annotation_form": result.annotation_form_score,
                "hidden_content": result.hidden_content_score,
            }
        ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_font_name(name: str) -> str:
        """Strip PDF subset-font prefixes (e.g. 'ABCDEF+Frutiger' ->
        'Frutiger') so the same face embedded as multiple subsets is
        counted once."""
        if not name:
            return name
        return re.sub(r"^[A-Z]{6}\+", "", name)

    @staticmethod
    def _covered_text_hidden(page, clip, expect_dark: bool) -> bool:
        """Visibility (z-order) test for fake-redaction / white-out checks.

        The text layer says there is text inside *clip* and the drawing list
        says a black/white fill covers the same rect — but the fill may be
        painted BEHIND the text (table-cell background), which is legitimate.
        Rasterise the clip region at ~72 dpi: if the render is a near-uniform
        block (pixel std-dev below a small threshold) with a mean matching
        the fill colour, the text really is hidden and we should flag; if
        glyphs are visible (contrast present) we must not flag.

        Returns True only when the text is genuinely hidden. Any render
        failure returns False (conservative — don't flag what we can't see).
        """
        try:
            import fitz as _fitz
            rect = _fitz.Rect(clip)
            if rect.is_empty or rect.width <= 0 or rect.height <= 0:
                return False
            pix = page.get_pixmap(clip=rect, dpi=72, alpha=False)
            if pix.width == 0 or pix.height == 0:
                return False
            gray = _fitz.Pixmap(_fitz.csGRAY, pix) if pix.n > 1 else pix
            samples = bytes(gray.samples)
            n = len(samples)
            if n == 0:
                return False
            # Sample at most ~20k pixels to bound cost on large rects
            step = max(1, n // 20000)
            sampled = samples[::step]
            count = len(sampled)
            mean = sum(sampled) / count
            variance = sum((s - mean) ** 2 for s in sampled) / count
            std = variance ** 0.5
            uniform = std < 8.0
            matches_fill = (mean <= 80.0) if expect_dark else (mean >= 175.0)
            return uniform and matches_fill
        except Exception:
            return False

    @staticmethod
    def _parse_pdf_date(date_str: str) -> Optional[datetime]:
        """Parse PDF date format D:YYYYMMDDHHmmSS or similar."""
        if not date_str:
            return None
        # Strip the D: prefix
        cleaned = date_str.replace("D:", "").strip()
        # Remove timezone info
        cleaned = re.sub(r"[+\-Z].*$", "", cleaned)
        # Try various lengths
        for fmt, length in [
            ("%Y%m%d%H%M%S", 14),
            ("%Y%m%d%H%M", 12),
            ("%Y%m%d", 8),
            ("%Y%m", 6),
            ("%Y", 4),
        ]:
            try:
                return datetime.strptime(cleaned[:length], fmt)
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def _parse_content_date(date_str: str) -> Optional[datetime]:
        """Parse a date found in document content."""
        for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except (ValueError, TypeError):
                continue
        return None


# Singleton instance for convenience
document_verification_pipeline = DocumentVerificationPipeline()
