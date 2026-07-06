#!/usr/bin/env bash
# =============================================================
# entrypoint.sh — Backend container startup (with diagnostics)
# =============================================================
# Every failure step prints a clear, named cause to stderr before exit.
# =============================================================
set -e

# Print exactly which step failed if -e trips us up.
trap 'rc=$?; echo "" >&2; echo "[FATAL] entrypoint.sh aborted at line ${LINENO} (exit ${rc}). See messages above for the cause." >&2; exit "${rc}"' ERR

echo "================================================================"
echo "Agora Backend — Container Startup ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
echo "================================================================"

# ----- 1. Environment diagnostics -------------------------------------
echo ""
echo "[1/4] Environment:"
echo "      PORT             = ${PORT:-<unset; CMD default 8000 will be used>}"
echo "      ENVIRONMENT      = ${ENVIRONMENT:-<unset>}"
echo "      DATABASE_URL set = $([ -n "${DATABASE_URL:-}" ] && echo yes || echo NO)"
if [ -n "${DATABASE_URL:-}" ]; then
    REDACTED=$(printf '%s' "$DATABASE_URL" | sed -E 's#(://[^:]+:)[^@]+(@)#\1***\2#')
    echo "      DATABASE_URL     = $REDACTED"
fi
echo "      SECRET_KEY set   = $([ -n "${SECRET_KEY:-}" ] && echo yes || echo NO)"
echo "      Python version   = $(python --version 2>&1)"
echo "      Working dir      = $(pwd)"

# ----- 2. Required env var checks -------------------------------------
echo ""
echo "[2/4] Required variables:"
missing=0
if [ -z "${DATABASE_URL:-}" ]; then
    echo "      [MISSING] DATABASE_URL is not set." >&2
    echo "                In Railway → service → Variables, add:" >&2
    echo "                    DATABASE_URL = \${{Postgres.DATABASE_URL}}" >&2
    missing=1
fi
if [ -z "${SECRET_KEY:-}" ]; then
    echo "      [MISSING] SECRET_KEY is not set — refusing to start with the" >&2
    echo "                insecure built-in default. Generate one with:" >&2
    echo "                    python -c \"import secrets; print(secrets.token_urlsafe(48))\"" >&2
    missing=1
fi
if [ "${missing}" -ne 0 ]; then
    echo "" >&2
    echo "[FATAL] One or more required environment variables are missing." >&2
    exit 1
fi
echo "      OK"

# ----- 3. Database reachability probe ---------------------------------
echo ""
echo "[3/4] Probing PostgreSQL reachability..."
if ! python - <<'PY'
import asyncio, os, sys
from urllib.parse import urlparse

url = os.environ["DATABASE_URL"]
# Normalise SQLAlchemy driver scheme so the raw driver libs accept it
if url.startswith("postgresql+asyncpg://"):
    url = "postgresql://" + url[len("postgresql+asyncpg://"):]
elif url.startswith("postgres://"):
    url = "postgresql://" + url[len("postgres://"):]

p = urlparse(url)
print(f"      host={p.hostname} port={p.port} db={(p.path or '').lstrip('/')}")

try:
    import asyncpg
except ImportError as e:
    print(f"      [ERROR] asyncpg not installed: {e}", file=sys.stderr)
    sys.exit(2)

async def probe():
    conn = await asyncpg.connect(url, timeout=10)
    try:
        ver = await conn.fetchval("SELECT version()")
        print(f"      Connected. Server: {ver.splitlines()[0]}")
    finally:
        await conn.close()

try:
    asyncio.run(probe())
except Exception as e:
    print(f"      [ERROR] {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(3)
PY
then
    echo "" >&2
    echo "[FATAL] Could not reach the database. Common causes:" >&2
    echo "        - The Postgres service in Railway hasn't finished starting." >&2
    echo "        - DATABASE_URL points at a different project's Postgres." >&2
    echo "        - The Postgres reference variable wasn't resolved (check the value in Variables — it should NOT still show '\${{Postgres.DATABASE_URL}}' as raw text)." >&2
    exit 1
fi

# ----- 4. Schema init + migrations ------------------------------------
echo ""
echo "[4/4] Running database initialisation (create_all + alembic)..."
if ! python scripts/init_db.py; then
    echo "" >&2
    echo "[FATAL] init_db.py failed. See the Python traceback above." >&2
    echo "        If it's an Alembic 'relation already exists' error, the DB" >&2
    echo "        already has the schema and the script should have stamped" >&2
    echo "        the latest revision instead — re-run after deleting any" >&2
    echo "        stale alembic_version row, or wipe the Postgres volume." >&2
    exit 1
fi

echo ""
echo "[OK] All preflight checks passed. Launching:"
echo "     $*"
echo ""
exec "$@"
