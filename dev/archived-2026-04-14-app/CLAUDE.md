# CLAUDE.md — Agora Consulting AI: App-Level Agent Instructions

> This file is auto-loaded by every Claude Code session in this directory.
> All agents MUST read and follow these instructions.

---

## DOCKER ISOLATION — MANDATORY SAFETY RULE

**Agents must NEVER run:**
- `docker system prune`
- `docker volume prune`
- `docker image prune`
- Any global Docker cleanup commands

**Only `docker-compose` commands scoped to this directory (`SoF-Claude/dev/app/`) are permitted.**

All container names must use the `sof-` prefix (as mandated in parent CLAUDE.md).
All volume names must use the `sof-` prefix.
All network names must use the `sof-` prefix.
All exposed host ports must avoid common defaults to prevent collisions:
- PostgreSQL: **5433** (not 5432)
- Nginx: **8080** (not 80)
- Backend/Frontend: internal only (not exposed to host)

Before running any Docker commands, agents must verify they are in `SoF-Claude/dev/app/`.

Violating this rule risks destroying unrelated Docker workloads on the host machine.

---

## GOLDEN RULE

The app's existing **functionality must be preserved exactly as-is**. Only design, code structure, performance, and security may be modified.

---

## PROJECT STATUS — What Has Been Completed

### Phase 1: REBRAND (COMPLETE)
- [x] Forbes logos deleted (`forbes-logo.png`, `more-than-law-logo-clean.png`, `more-than-law-logo.png`)
- [x] `frontend/public/agora-logo.svg` created (text-based SVG)
- [x] `frontend/public/favicon.svg` created ("A" lettermark)
- [x] `frontend/src/components/Layout.tsx` — rebranded with dark nav, Agora logo, logout button, tagline
- [x] `frontend/tailwind.config.js` — new palette (primary blue, accent green, brand-dark, brand-surface, Inter font)
- [x] `frontend/index.html` — title + favicon updated
- [x] `frontend/src/index.css` — Inter font import added
- [x] `frontend/package.json` — name changed to `agora-sof-platform-frontend`
- [x] `frontend/src/pages/DashboardPage.tsx` — "Legal SoF Platform" → "Agora Consulting AI"
- [x] `frontend/src/pages/LoginPage.tsx` — rebranded with logo, gradient, title
- [x] `frontend/.env` — set to `http://localhost:8000`
- [x] `frontend/vite.config.ts` — sandbox URLs removed, port set to 5173
- [x] `backend/app/core/config.py` — PROJECT_NAME, CORS_ORIGINS, DATABASE_URL all updated
- [x] `backend/app/main.py` — title, service name, CORS locked to settings
- [x] `backend/.env` — PostgreSQL URL set
- [x] All hardcoded Forbes hex colors replaced in `SoFAssessment.tsx` (~25 occurrences)
- [x] All hardcoded Forbes hex colors replaced in `FundsLineage.tsx` (4 occurrences)
- [x] `frontend/public/test-api.html` deleted

### Phase 2: INFRASTRUCTURE (MOSTLY COMPLETE)
- [x] SQLite hacks removed from all 5 backend endpoint files (11 locations total)
- [x] `backend/sof_platform.db` deleted
- [x] `backend/app/db/session.py` — connection pooling (pool_size=20, max_overflow=10, pool_pre_ping, pool_recycle)
- [x] `nginx/nginx.conf` created — reverse proxy, security headers, rate limiting zones
- [x] `nginx/Dockerfile` created — nginx:1.25-alpine, non-root, healthcheck
- [x] `docker/Dockerfile.backend` — multi-stage build, non-root, healthcheck
- [x] `docker/Dockerfile.frontend` — non-root, healthcheck
- [x] `docker-compose.yml` — agora_* containers, postgres 16, network isolation, healthchecks, nginx service, parameterized credentials
- [x] `backend/scripts/init_db.py` — creates tables, runs Alembic migrations, seeds admin (admin@agora.ai)
- [x] `backend/entrypoint.sh` — runs init_db.py before uvicorn on container startup
- [x] `docker/Dockerfile.backend` — ENTRYPOINT set to entrypoint.sh
- [x] Stale file cleanup — deleted 5 files (compressed JSON, HTML test pages, backup)
- [x] Archive root .md files — 69 files moved to `docs/archive/`, kept README/DEPLOYMENT_READY/HANDOVER

### Phase 3: SECURITY HARDENING (MOSTLY COMPLETE)
- [x] `backend/app/core/security.py` — bcrypt via passlib, dual-hash migration, password policy validation
- [x] `backend/app/models/user.py` — added failed_login_attempts, locked_until, totp_secret, mfa_enabled
- [x] `backend/app/api/v1/endpoints/auth.py` — account lockout (5 attempts / 15 min), password rehashing on login, password policy on register
- [x] `backend/app/main.py` — security headers middleware (XCTO, XFO, HSTS, Referrer-Policy, Permissions-Policy, CSP), rate limiting via slowapi
- [x] `backend/app/services/totp_service.py` — TOTP MFA service created
- [x] `backend/app/api/v1/endpoints/mfa.py` — MFA setup/verify/disable/status endpoints
- [x] `backend/app/api/v1/__init__.py` — MFA router registered
- [x] `frontend/src/components/ProtectedRoute.tsx` — created
- [x] `frontend/src/App.tsx` — all routes wrapped with ProtectedRoute, login route added
- [x] `frontend/src/lib/api.ts` — API client created with auth headers
- [x] CORS locked to localhost variants only
- [x] `backend/requirements.txt` — added slowapi, pyotp, qrcode[pil], pip-audit; removed duplicate httpx
- [ ] Auth dependencies on matters/transactions/sof_assessment/statement_validation endpoints — NEEDS REVIEW (Security Expert)
- [x] `scripts/security_scan.sh` — runs pip-audit + npm audit, exits non-zero on findings

### Phase 4: REVIEW & QA (NOT STARTED)
- [ ] Forbes reference audit (grep across all files — must be zero)
- [ ] Hardcoded color audit (grep in frontend/src — must be zero)
- [ ] Docker build verification
- [ ] Security review

### Phase 5: LOCAL DEPLOYMENT (NOT STARTED)
- [ ] `docker-compose up --build -d`
- [ ] Database init
- [ ] Smoke test

---

## REMAINING WORK BY ROLE

### Code Expert — ALL COMPLETE
1. ~~Create `backend/scripts/init_db.py`~~ — DONE (creates tables + seeds admin@agora.ai with bcrypt)
2. ~~Update `backend/requirements.txt`~~ — DONE (added slowapi, pyotp, qrcode[pil], pip-audit; removed duplicate httpx)
3. ~~Delete stale files~~ — DONE (5 files removed)
4. ~~Archive root .md files~~ — DONE (69 files → `docs/archive/`, 3 kept)
5. ~~Create `scripts/security_scan.sh`~~ — DONE (pip-audit + npm audit)
6. Created `backend/entrypoint.sh` — Docker startup runs init_db.py before uvicorn
7. Updated `docker/Dockerfile.backend` — ENTRYPOINT wired to entrypoint.sh

### Security Expert
1. Review and add auth dependencies to unprotected endpoints (matters.py, transactions.py, sof_assessment.py, statement_validation.py)
2. Verify no hardcoded secrets anywhere
3. Verify PostgreSQL credentials are parameterized in docker-compose.yml

### Branding Expert
1. Visual consistency review across all modified frontend files
2. Verify zero Forbes references remain
3. Polish logo SVGs if needed

### Review Team Lead
1. Run Forbes reference audit
2. Run hardcoded color audit
3. Verify Docker builds
4. Produce structured review report

---

## TECH STACK

- **Frontend:** React 18 + Vite + Tailwind CSS + TypeScript
- **Backend:** FastAPI + SQLAlchemy (async) + Alembic
- **Database:** PostgreSQL 16 (containerized) — NO SQLITE
- **Proxy:** Nginx 1.25 (containerized)
- **Auth:** JWT + bcrypt + TOTP MFA
- **Containers:** Docker Compose with network isolation

---

## KEY FILE PATHS

| Purpose | Path |
|---|---|
| Docker Compose | `docker-compose.yml` |
| Backend Dockerfile | `docker/Dockerfile.backend` |
| Frontend Dockerfile | `docker/Dockerfile.frontend` |
| Nginx config | `nginx/nginx.conf` |
| Backend config | `backend/app/core/config.py` |
| Security/auth | `backend/app/core/security.py` |
| Main app | `backend/app/main.py` |
| DB session | `backend/app/db/session.py` |
| User model | `backend/app/models/user.py` |
| Auth endpoints | `backend/app/api/v1/endpoints/auth.py` |
| MFA endpoints | `backend/app/api/v1/endpoints/mfa.py` |
| Frontend entry | `frontend/src/App.tsx` |
| Layout | `frontend/src/components/Layout.tsx` |
| Auth store | `frontend/src/stores/authStore.ts` |
| API client | `frontend/src/lib/api.ts` |
| Tailwind config | `frontend/tailwind.config.js` |
| DB init script | `backend/scripts/init_db.py` |
| Backend entrypoint | `backend/entrypoint.sh` |
| Security scanner | `scripts/security_scan.sh` |
