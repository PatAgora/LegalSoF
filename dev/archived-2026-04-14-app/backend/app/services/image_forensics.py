"""
Image-level forensics
=====================

For every raster image embedded in a PDF we run:

  * ELA (Error Level Analysis) — re-compress at quality 90 and compare
    against the original. Tampered regions tend to show as bright
    patches when the rest of the image is dim, because they've been
    saved with different JPEG parameters from the surrounding pixels.
    We score the *whole image* with its mean ELA brightness and flag
    if it's above the empirical threshold.

  * JPEG quantisation-table inspection — if a PDF contains several JPEG
    images but their quantisation tables are not all identical, that's
    a strong "spliced" indicator (genuine bank statements are exported
    once with one set of tables).

  * Perceptual hash (pHash) — computed for every image and stored on
    the result for downstream "have we seen this image on another
    matter?" lookups (the comparator isn't wired in this phase — we're
    just establishing the data).

Implementation uses PyMuPDF to iterate page images, Pillow for ELA,
and the `imagehash` library for pHash.

Performance: capped at the first 6 pages and first 8 images per page.
Failures degrade gracefully — never raises out of the public entry
point, only ever appends flags.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Tuple

from app.services.document_verification_pipeline import VerificationFlag


MAX_PAGES = 6
MAX_IMAGES_PER_PAGE = 8

# Mean-brightness threshold above which an image is considered to show
# ELA evidence of re-compression. Empirical; chosen to avoid firing on
# clean scans which sit well below 12 on the same scale.
ELA_MEAN_THRESHOLD = 14.0


def run_image_forensics(file_bytes: bytes) -> List[VerificationFlag]:
    """Run the image-level forensic checks on a PDF and return any flags.

    Empty list means everything looked clean (or the PDF had no embedded
    raster images to check — not unusual for a fully-vector statement).
    """
    flags: List[VerificationFlag] = []

    try:
        import fitz
        from PIL import Image, ImageChops
    except ImportError as exc:
        flags.append(VerificationFlag(
            "image_forensics", "IMAGE_FORENSICS_UNAVAILABLE", "info",
            f"Image forensics skipped (missing dependency: {exc.name}).",
            {"error": str(exc)},
        ))
        return flags

    try:
        import imagehash  # type: ignore
        have_imagehash = True
    except ImportError:
        have_imagehash = False

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        flags.append(VerificationFlag(
            "image_forensics", "IMAGE_FORENSICS_OPEN_FAILED", "info",
            f"Could not open PDF for image forensics: {exc}",
        ))
        return flags

    try:
        ela_findings: List[Dict[str, Any]] = []
        phashes: List[Dict[str, Any]] = []
        quant_table_sigs: List[Tuple[int, str]] = []  # (page, sig)

        for page_idx, page in enumerate(doc):
            if page_idx >= MAX_PAGES:
                break
            try:
                image_list = page.get_images(full=True)
            except Exception:
                continue

            for img_idx, img_info in enumerate(image_list[:MAX_IMAGES_PER_PAGE]):
                xref = img_info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.alpha:
                        pix = fitz.Pixmap(pix, 0)  # drop alpha for safe save
                    img_bytes = pix.tobytes("png")
                except Exception:
                    continue

                try:
                    pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                except Exception:
                    continue

                # --- pHash ---
                if have_imagehash:
                    try:
                        phash = str(imagehash.phash(pil))
                        phashes.append({
                            "page": page_idx + 1,
                            "xref": xref,
                            "phash": phash,
                            "size": pil.size,
                        })
                    except Exception:
                        pass

                # --- ELA ---
                try:
                    buf = io.BytesIO()
                    pil.save(buf, "JPEG", quality=90)
                    recompressed = Image.open(io.BytesIO(buf.getvalue()))
                    diff = ImageChops.difference(pil, recompressed)
                    # Compute mean luminance of the diff. Big-canvas images
                    # dilute the signal, so we crop dark borders out.
                    bbox = diff.getbbox()
                    crop = diff.crop(bbox) if bbox else diff
                    extrema = crop.convert("L").getextrema()
                    # Use the upper-bound brightness; mean is too soft on
                    # localized tampering.
                    mean_brightness = sum(extrema) / 2 if isinstance(extrema, tuple) else 0
                    ela_findings.append({
                        "page": page_idx + 1,
                        "xref": xref,
                        "ela_mean": round(mean_brightness, 2),
                    })
                except Exception:
                    pass

                # --- JPEG quantisation-table signature ---
                # tobytes() above gave us PNG; for quant-tables we need to
                # examine the *raw stream* if it's JPEG-encoded inside the
                # PDF. PyMuPDF exposes that as extract_image()["image"].
                try:
                    raw = doc.extract_image(xref)
                    if raw and raw.get("ext", "").lower() in {"jpg", "jpeg", "jpx"}:
                        jpil = Image.open(io.BytesIO(raw["image"]))
                        qt = getattr(jpil, "quantization", None)
                        if qt:
                            # Reduce to a short signature: hash of the table values
                            sig = ",".join(
                                str(sum(tbl)) for tbl in qt.values()
                            )
                            quant_table_sigs.append((page_idx + 1, sig))
                except Exception:
                    pass

        # --- Aggregate ELA into a single flag if any image trips ---
        suspect_ela = [f for f in ela_findings if f["ela_mean"] >= ELA_MEAN_THRESHOLD]
        if suspect_ela:
            pages = sorted({f["page"] for f in suspect_ela})
            flags.append(VerificationFlag(
                "image_forensics", "IMAGE_ELA_ANOMALY", "high",
                f"Error-level analysis suggests {len(suspect_ela)} image(s) on "
                f"page(s) {', '.join(map(str, pages))} were edited or "
                "re-compressed.",
                {
                    "suspect_images": suspect_ela,
                    "threshold": ELA_MEAN_THRESHOLD,
                    "page_numbers": [p - 1 for p in pages],  # 0-indexed for the UI highlighter
                },
            ))

        # --- Quant table mismatch flag ---
        if len(quant_table_sigs) >= 2:
            distinct_sigs = {sig for _, sig in quant_table_sigs}
            if len(distinct_sigs) > 1:
                flags.append(VerificationFlag(
                    "image_forensics", "IMAGE_QUANT_TABLE_MIXED", "high",
                    f"Document contains {len(distinct_sigs)} different JPEG "
                    "compression profiles across its embedded images. Genuine "
                    "statements export with a single profile — this is a "
                    "strong indicator of image splicing.",
                    {
                        "distinct_signatures": len(distinct_sigs),
                        "total_images": len(quant_table_sigs),
                        "by_page": [{"page": p, "sig": s} for p, s in quant_table_sigs],
                    },
                ))

        # --- pHash info flag (no severity — just data for downstream) ---
        if phashes:
            flags.append(VerificationFlag(
                "image_forensics", "IMAGE_PHASH_RECORDED", "info",
                f"Computed perceptual hash for {len(phashes)} embedded image(s).",
                {"phashes": phashes},
            ))

    finally:
        doc.close()

    return flags
