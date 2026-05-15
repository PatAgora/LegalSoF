#!/usr/bin/env bash
# =============================================================
# security_scan.sh — Dependency vulnerability scanner
# Agora Consulting AI — Anti-Financial Crime Platform
# =============================================================
# Runs pip-audit against backend Python dependencies to detect
# known CVEs. Exits non-zero if vulnerabilities are found.
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
REQUIREMENTS="$APP_DIR/backend/requirements.txt"
EXIT_CODE=0

echo "============================================="
echo " Agora Consulting AI — Security Scan"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================="
echo ""

# --- 1. pip-audit: Python dependency vulnerabilities ---
echo "[1/2] Python dependency audit (pip-audit)"
echo "---------------------------------------------"

if ! command -v pip-audit &>/dev/null; then
    echo "[!] pip-audit not found. Installing..."
    pip install --quiet pip-audit
fi

if [ ! -f "$REQUIREMENTS" ]; then
    echo "[!] Requirements file not found: $REQUIREMENTS"
    EXIT_CODE=1
else
    echo "[*] Scanning: $REQUIREMENTS"
    echo ""
    if pip-audit -r "$REQUIREMENTS" --desc 2>&1; then
        echo "[+] No known vulnerabilities found in Python dependencies."
    else
        echo "[!] Vulnerabilities detected in Python dependencies."
        EXIT_CODE=1
    fi
fi

echo ""

# --- 2. npm audit: Frontend dependency vulnerabilities ---
echo "[2/2] Frontend dependency audit (npm audit)"
echo "---------------------------------------------"

FRONTEND_DIR="$APP_DIR/frontend"
if [ -f "$FRONTEND_DIR/package-lock.json" ]; then
    echo "[*] Scanning: $FRONTEND_DIR"
    echo ""
    if (cd "$FRONTEND_DIR" && npm audit --production 2>&1); then
        echo "[+] No known vulnerabilities found in frontend dependencies."
    else
        echo "[!] Vulnerabilities detected in frontend dependencies."
        EXIT_CODE=1
    fi
else
    echo "[*] No package-lock.json found — skipping frontend audit."
fi

echo ""
echo "============================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo " RESULT: PASS — No vulnerabilities detected"
else
    echo " RESULT: FAIL — Review findings above"
fi
echo "============================================="

exit $EXIT_CODE
