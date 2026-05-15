#!/usr/bin/env bash
# =============================================================
# entrypoint.sh — Backend container startup
# Agora Consulting AI — Anti-Financial Crime Platform
# =============================================================
# 1. Initialises the database (creates tables + seeds admin)
# 2. Starts the FastAPI application via uvicorn
# =============================================================
set -e

echo "=== Agora Backend — Starting ==="

# Wait for PostgreSQL to be truly ready (belt-and-suspenders with healthcheck)
echo "[*] Running database initialisation..."
python scripts/init_db.py

echo "[*] Launching uvicorn..."
exec "$@"
