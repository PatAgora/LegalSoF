# Bank statement reference fingerprints

Each JSON file in this directory is the visual fingerprint of one known
UK bank's statement template. The template_fingerprint service loads
them at runtime to detect hand-built fakes.

## File format

```
{
  "bank": "HSBC",
  "header_phash": "ff0080c0c060e0f0",
  "added": "2026-05-16",
  "source_filename": "HSBC_Current_Account_Statement_Jun-Sep2023.pdf",
  "notes": "Pulled from SOF Demo 2 — page 1 header band, 100 dpi."
}
```

Filename convention: lowercase bank name with underscores, e.g.
`hsbc.json`, `natwest.json`, `barclays.json`, `santander.json`,
`lloyds.json`.

## Generating a new fingerprint

To register a known-good statement as the reference for a bank:

```python
from app.services.template_fingerprint import _compute_header_phash
with open("path/to/known_good_statement.pdf", "rb") as f:
    print(_compute_header_phash(f.read()))
```

Drop the resulting hex string into a new JSON file with the format
above, commit and redeploy. Mismatches against this fingerprint will
then raise `TEMPLATE_VISUAL_MISMATCH` (HIGH) on suspect uploads.

## Why pHash and not exact-hash?

Perceptual hashing tolerates minor differences (different month,
slightly different colour rendering, OCR cleanup) but rejects layout
changes. A genuine new HSBC statement matches; a hand-rebuilt fake
that simply *resembles* HSBC's branding will not.
