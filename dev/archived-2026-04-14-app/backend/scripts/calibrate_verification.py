#!/usr/bin/env python3
"""
Verification calibration harness.

Runs the verification pipelines over a corpus of KNOWN-GENUINE statements
and reports which flags fire, and how often. A non-info flag firing on a
large share of genuine documents is mis-calibrated — it will bury real
tampering signals in noise.

Usage (from backend/):
    python scripts/calibrate_verification.py --dir "/path/to/genuine" [--dir ...]
                                             [--bank HSBC] [--category bank_statement]

  * PDFs  -> DocumentVerificationPipeline (structural forensics)
  * CSVs  -> StatementValidationPipeline (arithmetic/anomaly checks)
  * other files are skipped

Output: per-file verdict + score, then an aggregate table of flag codes by
fire-rate. Any non-info flag firing on more than CALIBRATION_THRESHOLD of
the genuine files is marked "CALIBRATION CANDIDATE".

Exit status: non-zero if ANY file verdicts LikelyTampered (PDF) or
HighRisk (CSV) — a genuine corpus should never trip the blocking verdict.
"""
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Ensure the backend package is importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.document_verification_pipeline import DocumentVerificationPipeline  # noqa: E402
from app.services.statement_validation_pipeline import StatementValidationPipeline    # noqa: E402

# A non-info flag firing on more than this share of genuine files is a
# calibration candidate.
CALIBRATION_THRESHOLD = 0.20

BLOCKING_VERDICTS = {"LikelyTampered", "HighRisk"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run verification pipelines over a known-genuine corpus and "
                    "report flag fire-rates."
    )
    parser.add_argument("--dir", action="append", required=True, dest="dirs",
                        help="Directory of known-genuine statements (repeatable)")
    parser.add_argument("--bank", default=None,
                        help="Optional bank hint passed to the CSV pipeline")
    parser.add_argument("--category", default="bank_statement",
                        help="file_category passed to the PDF pipeline "
                             "(default: bank_statement)")
    args = parser.parse_args()

    files = []
    for d in args.dirs:
        path = Path(d)
        if not path.is_dir():
            print(f"[!] Not a directory: {path}", file=sys.stderr)
            return 2
        files.extend(sorted(p for p in path.iterdir()
                            if p.suffix.lower() in (".pdf", ".csv")))
    if not files:
        print("[!] No PDF/CSV files found in the given directories.", file=sys.stderr)
        return 2

    pdf_pipeline = DocumentVerificationPipeline()
    csv_pipeline = StatementValidationPipeline()

    per_file = []           # (filename, kind, verdict, score)
    flag_files = defaultdict(set)   # code -> set of filenames it fired on
    flag_severity = {}              # code -> worst severity seen
    severity_rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    blocking = []

    print(f"Calibrating over {len(files)} file(s)\n")
    print(f"{'file':<58} {'kind':<5} {'verdict':<15} {'score':>6}")
    print("-" * 88)
    for f in files:
        data = f.read_bytes()
        if f.suffix.lower() == ".pdf":
            res = pdf_pipeline.verify_document(data, f.name, args.category)
            verdict, score, flags, kind = res.verdict, res.authenticity_score, res.flags, "PDF"
        else:
            res = csv_pipeline.validate_statement(data, bank_hint=args.bank)
            verdict, score, flags, kind = res.status, res.authenticity_score, res.flags, "CSV"

        per_file.append((f.name, kind, verdict, score))
        if verdict in BLOCKING_VERDICTS:
            blocking.append(f.name)
        for fl in flags:
            flag_files[fl.code].add(f.name)
            prev = flag_severity.get(fl.code)
            if prev is None or severity_rank.get(fl.severity, 0) > severity_rank.get(prev, 0):
                flag_severity[fl.code] = fl.severity
        print(f"{f.name[:57]:<58} {kind:<5} {verdict:<15} {score:>6.1f}")

    n = len(files)
    print("\nFlag fire-rates over genuine corpus "
          f"(calibration threshold {CALIBRATION_THRESHOLD:.0%} for non-info flags)\n")
    print(f"{'flag code':<34} {'severity':<9} {'files':>5} {'rate':>7}  note")
    print("-" * 88)
    rows = sorted(flag_files.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    calibration_candidates = []
    for code, hit_files in rows:
        sev = flag_severity.get(code, "info")
        rate = len(hit_files) / n
        note = ""
        if sev != "info" and rate > CALIBRATION_THRESHOLD:
            note = "CALIBRATION CANDIDATE"
            calibration_candidates.append(code)
        print(f"{code:<34} {sev:<9} {len(hit_files):>5} {rate:>6.0%}  {note}")

    print()
    if calibration_candidates:
        print(f"[!] {len(calibration_candidates)} calibration candidate(s): "
              + ", ".join(calibration_candidates))
    else:
        print("[+] No non-info flag fires on more than "
              f"{CALIBRATION_THRESHOLD:.0%} of the genuine corpus.")

    if blocking:
        print(f"\n[!] FAIL: {len(blocking)} genuine file(s) received a blocking "
              f"verdict ({'/'.join(sorted(BLOCKING_VERDICTS))}): " + ", ".join(blocking))
        return 1
    print("[+] No genuine file verdicts LikelyTampered/HighRisk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
