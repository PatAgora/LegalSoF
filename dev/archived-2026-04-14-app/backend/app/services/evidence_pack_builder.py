"""
Evidence pack builder
=====================

Generates a single PDF for compliance archives covering one document
verification: header (matter, doc, hash, verdict, score), all flags
with severity and details, and the audit trail (overrides, etc).

Uses PyMuPDF (already in requirements) so there's no new dependency.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF


# Layout constants
PAGE_W, PAGE_H = 595, 842            # A4 portrait, points
MARGIN = 50
LINE_H = 14
SECTION_GAP = 10
FONT_REGULAR = "helv"
FONT_BOLD = "hebo"
TITLE_SIZE = 18
H2_SIZE = 13
BODY_SIZE = 10
SMALL_SIZE = 8


SEVERITY_COLOR = {
    "critical": (0.78, 0.12, 0.12),
    "high":     (0.85, 0.45, 0.05),
    "medium":   (0.45, 0.45, 0.45),
    "low":      (0.55, 0.55, 0.55),
    "info":     (0.40, 0.55, 0.70),
}


def _new_page(doc: fitz.Document) -> tuple[fitz.Page, float]:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    # Footer
    page.insert_text(
        (MARGIN, PAGE_H - 25),
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · Agora Consulting AI",
        fontsize=SMALL_SIZE,
        fontname=FONT_REGULAR,
        color=(0.5, 0.5, 0.5),
    )
    return page, MARGIN


def _wrap_text(text: str, width_chars: int) -> List[str]:
    """Crude word-wrap so long lines don't run off the page. Width is
    measured in characters rather than points — fine for monospace-ish
    Helvetica at body size."""
    if not text:
        return [""]
    out: List[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        line = ""
        for w in words:
            candidate = (line + " " + w).strip() if line else w
            if len(candidate) > width_chars:
                if line:
                    out.append(line)
                line = w
            else:
                line = candidate
        out.append(line)
    return out or [""]


def _draw_kv_block(page: fitz.Page, y: float, pairs: List[tuple[str, str]]) -> float:
    for k, v in pairs:
        page.insert_text((MARGIN, y), k, fontsize=BODY_SIZE, fontname=FONT_BOLD)
        # Word-wrap the value
        for i, line in enumerate(_wrap_text(v, 70)):
            page.insert_text(
                (MARGIN + 140, y + i * LINE_H),
                line,
                fontsize=BODY_SIZE,
                fontname=FONT_REGULAR,
            )
        y += LINE_H * max(1, len(_wrap_text(v, 70)))
        y += 4
    return y


def _draw_flag(
    page: fitz.Page,
    y: float,
    flag: Dict[str, Any],
) -> tuple[fitz.Page, float]:
    """Render a single flag block. If we run out of space mid-flag, fall
    through to a new page automatically."""
    needed = 60 + LINE_H * max(2, len((flag.get("message") or "")) // 70)
    if y + needed > PAGE_H - 60:
        page, y = _new_page(page.parent)

    severity = (flag.get("severity") or "info").lower()
    colour = SEVERITY_COLOR.get(severity, SEVERITY_COLOR["info"])

    # Severity tag
    tag = severity.upper()
    page.insert_text((MARGIN, y), tag, fontsize=SMALL_SIZE, fontname=FONT_BOLD, color=colour)
    # Code
    page.insert_text(
        (MARGIN + 70, y),
        flag.get("code") or "",
        fontsize=SMALL_SIZE,
        fontname=FONT_REGULAR,
        color=(0.4, 0.4, 0.4),
    )
    # Stage
    page.insert_text(
        (PAGE_W - MARGIN - 120, y),
        f"stage: {flag.get('pipeline_stage') or ''}",
        fontsize=SMALL_SIZE,
        fontname=FONT_REGULAR,
        color=(0.5, 0.5, 0.5),
    )
    y += LINE_H

    # Message
    for line in _wrap_text(flag.get("message") or "", 90):
        if y > PAGE_H - 80:
            page, y = _new_page(page.parent)
        page.insert_text((MARGIN, y), line, fontsize=BODY_SIZE, fontname=FONT_REGULAR)
        y += LINE_H

    # Details
    details = flag.get("details") or {}
    if isinstance(details, dict) and details:
        for k, v in details.items():
            if y > PAGE_H - 80:
                page, y = _new_page(page.parent)
            val_str = _stringify_value(v)
            line_str = f"    {k}: {val_str}"
            for line in _wrap_text(line_str, 90):
                page.insert_text(
                    (MARGIN, y),
                    line,
                    fontsize=SMALL_SIZE,
                    fontname=FONT_REGULAR,
                    color=(0.35, 0.35, 0.35),
                )
                y += LINE_H - 2

    y += SECTION_GAP
    return page, y


def _stringify_value(v: Any, max_len: int = 200) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (list, tuple)):
        if all(not isinstance(x, (dict, list)) for x in v):
            s = ", ".join(str(x) for x in v)
        else:
            s = str(v)
    elif isinstance(v, dict):
        s = str(v)
    else:
        s = str(v)
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s


def build_evidence_pack(
    matter: Dict[str, Any],
    verification: Dict[str, Any],
    flags: List[Dict[str, Any]],
    audit_entries: Optional[List[Dict[str, Any]]] = None,
) -> bytes:
    """Build a single PDF in-memory and return its raw bytes.

    All inputs are plain dicts so the function stays decoupled from
    SQLAlchemy. The caller assembles them.
    """
    audit_entries = audit_entries or []
    doc = fitz.open()

    # --- Cover page ---
    page, y = _new_page(doc)
    page.insert_text((MARGIN, y), "Document Verification Report", fontsize=TITLE_SIZE, fontname=FONT_BOLD)
    y += TITLE_SIZE + 10
    page.insert_text(
        (MARGIN, y),
        f"Matter {matter.get('reference_number') or matter.get('id')} · "
        f"{matter.get('client_name') or ''}",
        fontsize=H2_SIZE,
        fontname=FONT_REGULAR,
        color=(0.3, 0.3, 0.3),
    )
    y += H2_SIZE + 14

    pairs = [
        ("Filename", str(verification.get("filename") or "")),
        ("File category", str(verification.get("file_category") or "")),
        ("File hash (SHA-256)", str(verification.get("file_hash") or "")),
        ("Identified bank", str(verification.get("identified_bank_template") or "—")),
        ("Verdict", str(verification.get("verdict") or "—")),
        ("Authenticity score", f"{verification.get('authenticity_score') or 0:.1f} / 100"),
        ("Structural score", _opt_score(verification.get("structural_pipeline_score"))),
        ("Statement score", _opt_score(verification.get("statement_pipeline_score"))),
        ("Verification phase", str(verification.get("verification_phase") or "—")),
        ("Created at", str(verification.get("created_at") or "")),
        ("Admin override", "Yes" if verification.get("admin_override") else "No"),
    ]
    y = _draw_kv_block(page, y, pairs)
    if verification.get("admin_override"):
        y += SECTION_GAP
        y = _draw_kv_block(page, y, [
            ("Overridden by", str(verification.get("admin_override_by") or "")),
            ("Override rationale", str(verification.get("admin_override_rationale") or "")),
            ("Overridden at", str(verification.get("admin_override_at") or "")),
        ])

    # --- Flags ---
    y += SECTION_GAP * 2
    if y > PAGE_H - 80:
        page, y = _new_page(doc)
    page.insert_text((MARGIN, y), f"Verification Flags ({len(flags)})", fontsize=H2_SIZE, fontname=FONT_BOLD)
    y += H2_SIZE + 8

    if not flags:
        page.insert_text((MARGIN, y), "No flags raised.", fontsize=BODY_SIZE, fontname=FONT_REGULAR)
        y += LINE_H
    else:
        # Sort by severity (critical first)
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        for flag in sorted(flags, key=lambda f: order.get((f.get("severity") or "").lower(), 5)):
            page, y = _draw_flag(page, y, flag)

    # --- Audit trail ---
    if y > PAGE_H - 120:
        page, y = _new_page(doc)
    y += SECTION_GAP
    page.insert_text((MARGIN, y), f"Audit Trail ({len(audit_entries)})", fontsize=H2_SIZE, fontname=FONT_BOLD)
    y += H2_SIZE + 8

    if not audit_entries:
        page.insert_text((MARGIN, y), "No audit entries recorded.", fontsize=BODY_SIZE, fontname=FONT_REGULAR)
    else:
        for entry in audit_entries:
            if y > PAGE_H - 80:
                page, y = _new_page(doc)
            page.insert_text(
                (MARGIN, y),
                str(entry.get("timestamp") or ""),
                fontsize=SMALL_SIZE, fontname=FONT_BOLD,
                color=(0.3, 0.3, 0.3),
            )
            page.insert_text(
                (MARGIN + 140, y),
                f"{entry.get('action') or ''} by {entry.get('user') or 'system'}",
                fontsize=SMALL_SIZE, fontname=FONT_REGULAR,
            )
            y += LINE_H
            for line in _wrap_text(str(entry.get("description") or ""), 95):
                page.insert_text((MARGIN + 12, y), line, fontsize=SMALL_SIZE, fontname=FONT_REGULAR,
                                 color=(0.35, 0.35, 0.35))
                y += LINE_H - 2
            y += 4

    # Serialise
    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True)
    doc.close()
    return buf.getvalue()


def _opt_score(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f}"
    except (TypeError, ValueError):
        return str(v)
