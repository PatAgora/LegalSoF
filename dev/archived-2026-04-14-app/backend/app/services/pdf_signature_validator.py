"""
PDF digital-signature validation
================================

Many modern UK bank PDFs and conveyancing completion statements are
PAdES-signed (or carry an Adobe-AATL chain). This service detects any
embedded signature and, when pyHanko is available, validates the chain.

Flag taxonomy:

  SIGNATURE_VALID          (info)     — sig present and validated cleanly
  SIGNATURE_PRESENT_UNVERIFIED (info) — sig present but couldn't verify
                                        (pyHanko not installed, or the
                                        certificate chain doesn't reach a
                                        trusted root)
  SIGNATURE_INVALID        (critical) — sig present and explicitly broken
                                        (the document has been modified
                                        after signing, or the cert chain
                                        is forged)
  SIGNATURE_ABSENT         (info)     — no signature; carries no weight
                                        on its own, just records the fact

The "absent" flag is included so the evidence pack and reviewer UI can
say "no digital signature attached" rather than silently nothing.
"""
from __future__ import annotations

import io
from typing import List

from app.services.document_verification_pipeline import VerificationFlag


def validate_pdf_signature(file_bytes: bytes) -> List[VerificationFlag]:
    flags: List[VerificationFlag] = []

    # Fast presence check via PyMuPDF — works whether or not pyHanko is
    # installed and tells us if there's anything to validate.
    sig_present = False
    sig_field_count = 0
    try:
        import fitz
        # PyMuPDF widget-type constant: signature fields are type 6
        # (PDF_WIDGET_TYPE_SIGNATURE), NOT 4 (4 is ListBox).
        sig_widget_type = getattr(fitz, "PDF_WIDGET_TYPE_SIGNATURE", 6)
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            for page in doc:
                widgets = page.widgets() or []
                for w in widgets:
                    if getattr(w, "field_type", None) == sig_widget_type or getattr(w, "field_type_string", "") == "Signature":
                        sig_field_count += 1
                        # A signature field is only "signed" if it has a value
                        if getattr(w, "field_value", None):
                            sig_present = True
        finally:
            doc.close()
    except Exception:
        # PyMuPDF failure — fall through; pyHanko may still detect a sig.
        pass

    if not sig_present and sig_field_count == 0:
        flags.append(VerificationFlag(
            "signature_validation", "SIGNATURE_ABSENT", "info",
            "Document has no digital signature.",
        ))
        return flags

    # Try a proper chain validation with pyHanko if available.
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature as ph_validate
        from pyhanko_certvalidator import ValidationContext
    except ImportError:
        flags.append(VerificationFlag(
            "signature_validation", "SIGNATURE_PRESENT_UNVERIFIED", "info",
            f"Document contains {sig_field_count} signature field(s) but "
            "pyHanko is not installed so the chain cannot be verified.",
            {"signature_fields": sig_field_count},
        ))
        return flags

    try:
        reader = PdfFileReader(io.BytesIO(file_bytes))
        sigs = list(reader.embedded_signatures)
    except Exception as exc:
        flags.append(VerificationFlag(
            "signature_validation", "SIGNATURE_PRESENT_UNVERIFIED", "info",
            f"Signature present but pyHanko could not read it ({exc}).",
        ))
        return flags

    if not sigs:
        flags.append(VerificationFlag(
            "signature_validation", "SIGNATURE_ABSENT", "info",
            "Document has signature fields but none are populated.",
        ))
        return flags

    # Use a relaxed validation context (no revocation checking, no AATL
    # registry) — we want "is this internally consistent" rather than
    # "is the issuer in our trust store". A future pass can wire in the
    # actual trust roots once we have a curated bank-CA list.
    vc = ValidationContext(allow_fetching=False)
    valid_count = 0
    invalid_count = 0
    sig_details = []
    for emb_sig in sigs:
        try:
            status = ph_validate(emb_sig, vc)
            ok = bool(getattr(status, "intact", False) and getattr(status, "valid", False))
            valid_count += 1 if ok else 0
            invalid_count += 0 if ok else 1
            sig_details.append({
                "signer": getattr(status, "signer_reported_dn", None) or "—",
                "intact": bool(getattr(status, "intact", False)),
                "valid": bool(getattr(status, "valid", False)),
                "trust_problem": str(getattr(status, "trust_problem_indic", None) or ""),
            })
        except Exception as exc:
            invalid_count += 1
            sig_details.append({"error": str(exc)})

    if invalid_count and not valid_count:
        flags.append(VerificationFlag(
            "signature_validation", "SIGNATURE_INVALID", "critical",
            "Document signature(s) failed validation. The document may "
            "have been modified after signing, or the certificate chain "
            "is broken/forged.",
            {"signatures": sig_details},
        ))
    elif valid_count:
        flags.append(VerificationFlag(
            "signature_validation", "SIGNATURE_VALID", "info",
            f"Document carries {valid_count} validated digital signature(s).",
            {"signatures": sig_details},
        ))
    else:
        flags.append(VerificationFlag(
            "signature_validation", "SIGNATURE_PRESENT_UNVERIFIED", "info",
            "Signature present but pyHanko returned no status.",
            {"signatures": sig_details},
        ))

    return flags
