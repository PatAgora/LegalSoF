# CONSOLIDATED PROJECT PLAN — Agora Consulting AI

**Document:** Master Execution Plan (All Agents)
**Date:** 2026-02-28
**Status:** AWAITING PM APPROVAL — No code changes until this plan is signed off
**Project:** Agora Consulting AI — Anti-Financial Crime Application
**Phase:** Phase 1 — Local Deployment Only (localhost, Docker)

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Current Application Inventory](#2-current-application-inventory)
3. [Code Expert Plan](#3-code-expert-plan)
4. [Branding Expert Plan](#4-branding-expert-plan)
5. [Security Expert Plan](#5-security-expert-plan)
6. [Review Team Lead Plan](#6-review-team-lead-plan)
7. [Cross-Agent Dependencies](#7-cross-agent-dependencies)
8. [Risk Register](#8-risk-register)
9. [Docker Isolation Rules](#9-docker-isolation-rules)
10. [Execution Sequence](#10-execution-sequence)
11. [Definition of Done](#11-definition-of-done)

---

## 1. EXECUTIVE SUMMARY

This document consolidates the execution plans from all four specialist agents (Code Expert, Branding Expert, Security Expert, Review Team Lead) into a single assessable plan. The Project Manager must review and approve this plan before any code changes are made.

### Golden Rule
> The app's existing **functionality must be preserved exactly as-is**. Only the design, code structure, performance, and security may be modified or refactored.

### Key Numbers

| Metric | Value |
|--------|-------|
| Total Python files | 74 |
| Total TypeScript files | 18 |
| Total lines of code | ~25,000+ |
| Backend services LOC | 14,421 |
| API endpoint LOC | 4,627 |
| Database models | 10 tables + 1 association table |
| Docker containers (current) | 4 (postgres, backend, frontend, nginx) |
| Docker containers (planned) | 6 (+ pgbouncer, redis) |
| Security BLOCKERs found | 6 |
| Security MAJORs found | 12 |
| Estimated total effort | ~120 hours across all agents |

---

## 2. CURRENT APPLICATION INVENTORY

### 2.1 Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend Framework | FastAPI | 0.109.0 |
| ASGI Server | Uvicorn | 0.27.0 |
| Database | PostgreSQL 16 (Alpine) | Containerized |
| ORM | SQLAlchemy | 2.0.25 (async via asyncpg) |
| Migrations | Alembic | 1.13.1 |
| Frontend | React 18 + TypeScript + Vite | 5.0.12 |
| CSS | TailwindCSS | 3.4.1 |
| State Management | Zustand | 4.5.0 |
| Reverse Proxy | Nginx | 1.25 Alpine |
| Containerization | Docker + Docker Compose | v3.8 spec |
| Auth | JWT (python-jose) + bcrypt + TOTP | — |
| Document Processing | pdfplumber, PyMuPDF, pytesseract | — |

### 2.2 Application Features (All Must Be Preserved)

- **Authentication:** JWT login, registration (admin-only), password policy, account lockout
- **MFA:** TOTP setup, verification, disable (via pyotp)
- **RBAC:** Admin, Partner, Analyst roles
- **Matter Management:** CRUD, workflow states, risk ratings, analyst assignment, reference number generation
- **Document Intelligence:** PDF/DOCX/XLSX upload, heuristic extraction, AI-assisted extraction, OCR
- **Funds Chain Reconstruction:** Source identification, transfer tracking, amount reconciliation, timeline view
- **Consistency & Risk Checks:** Amount consistency, date alignment, identity consistency, gap detection, circular flow detection
- **Transaction Review & AML Monitoring:** Upload/parse, 7+ AML rules, country risk, keyword matching, alert generation, dashboard
- **SoF Assessment Engine:** Claim extraction, evidence matching, funding tracing, risk decision, file note generation
- **Statement Validation:** Bank statement authenticity pipeline, 6-stage validation
- **Audit Logging:** AuditLog model with action types, IP/user-agent capture

### 2.3 File Size Analysis (Oversized Files Flagged)

**Endpoint files:**

| File | Lines | Assessment |
|------|-------|-----------|
| `sof_assessment.py` | 2,187 | CRITICAL — needs splitting |
| `transactions.py` | 923 | LARGE — needs splitting |
| `matters.py` | 897 | LARGE — needs splitting |
| `statement_validation.py` | 206 | OK |
| `auth.py` | 191 | OK |
| `mfa.py` | 128 | OK |

**Service files:**

| File | Lines | Assessment |
|------|-------|-----------|
| `universal_financial_parser.py` | 2,260 | CRITICAL — needs splitting |
| `sof_assessment_engine.py` | 2,065 | CRITICAL — needs splitting |
| `enhanced_universal_parser.py` | 1,666 | LARGE |
| `document_verifier.py` | 1,081 | LARGE |
| `natwest_statement_parser.py` | 1,081 | MODERATE |
| `file_processor.py` | 960 | MODERATE |
| `pdf_extractor.py` | 960 | MODERATE |
| `statement_validation_pipeline.py` | 914 | MODERATE |
| `bank_statement_pdf_parser.py` | 800 | MODERATE |

### 2.4 Frontend Pages & Components

| File | Purpose | Lines |
|------|---------|-------|
| `LoginPage.tsx` | Authentication | 93 |
| `DashboardPage.tsx` | Main dashboard with stats | 157 |
| `MattersPage.tsx` | Matters list, create, filter | 344 |
| `MatterDetailPage.tsx` | Matter detail with tabs | 422 |
| `Layout.tsx` | Nav bar + content wrapper | 62 |
| `SoFAssessment.tsx` | Assessment component | ~900+ |
| `FundsLineage.tsx` | Funds lineage tracing | ~600+ |
| `TransactionList.tsx` | Transaction list + alerts | 496 |
| `TransactionUpload.tsx` | File upload | 170 |
| `TransactionAlerts.tsx` | Alert cards | 124 |
| `TransactionDashboard.tsx` | KPI stats | 99 |
| `StatusUpdateModal.tsx` | Status transition modal | 316 |

### 2.5 Database Schema (10 Tables)

- `users` — Authentication, RBAC, MFA, lockout tracking
- `matters` — Core case entity with workflow states
- `questionnaire_responses` — Client evidence questionnaire
- `documents` — Uploaded evidence files
- `entities` — Parties, accounts, organizations
- `fundsevents` — Funds chain tracking (+ `document_event_links` M2M)
- `checks` — Consistency and risk checks
- `notes`, `approvals` — Matter commentary and sign-off
- `audit_logs` — Audit trail
- `transactions`, `transaction_alerts` — AML monitoring
- `ref_country_risk`, `kyc_profiles`, `transaction_config` — Reference data
- `statement_validations`, `statement_validation_flags`, `statement_validation_transactions` — Validation

### 2.6 Current Docker Architecture

```
4 containers:
  sof-postgres      (postgres:16-alpine, port 5432 exposed to host)
  sof-backend       (python:3.11-slim, port 8000 internal)
  sof-frontend      (node:18-alpine, port 5173 internal)
  sof-nginx         (nginx:1.25-alpine, port 80 exposed)

2 networks:
  backend-net       (backend + postgres)
  frontend-net      (frontend + nginx + backend)

1 volume:
  postgres_data     (database persistence)
```

---

## 3. CODE EXPERT PLAN

### 3.1 Identified Issues (Severity-Ordered)

#### CRITICAL Issues

**C1: Sync DB Session Anti-Pattern**
- Location: `matters.py`, `transactions.py`, `sof_assessment.py`
- Multiple endpoint files create ad-hoc synchronous SQLAlchemy engines via `create_engine()` + `sessionmaker()` on every single request
- Each request creates a new engine with its own connection pool — massive connection leak risk
- Pattern: `db_url = str(settings.DATABASE_URL).replace("postgresql+asyncpg", "postgresql")` followed by `engine = create_engine(db_url)` in nearly every endpoint function
- **Fix:** Create a single shared synchronous engine + session factory in `db/session.py` and use via FastAPI dependency

**C2: File-Based Storage (`/tmp/sof_assessment_storage.json`)**
- SoF assessment data, bank statements, uploaded file metadata, and results stored in a JSON file on `/tmp`
- Lost on container restart, no concurrency protection, no transactions, tight coupling
- Both `matters.py` and `transactions.py` read from this same `/tmp` file
- **Fix (Phase 1):** Move storage to a mounted Docker volume (`/app/data/`) instead of `/tmp`. Add file locking. Preserves existing functionality.
- **Fix (Phase 2 — future):** Migrate to PostgreSQL tables. Requires PM approval as functionality change.

**C3: No PgBouncer Connection Pooling**
- CLAUDE.md mandates PgBouncer but none exists
- SQLAlchemy's built-in pool (`pool_size=20, max_overflow=10`) is insufficient for 100+ concurrent users
- **Fix:** Add `sof-pgbouncer` container between backend and PostgreSQL

**C4: No Redis Container**
- No Redis for caching, session storage, or rate limiting backend
- `slowapi` uses in-memory storage (lost on restart, not shared across workers)
- **Fix:** Add `sof-redis` container

#### MAJOR Issues

**M1: Docker Compose Hardening**
- Volume names not project-prefixed
- Network names are generic (`backend-net`, `frontend-net`)
- Port 5432 exposed to host
- No `restart` policies
- No memory/CPU limits
- No `.env` at docker-compose level
- Compose version `3.8` deprecated
- **Fix:** Update docker-compose.yml with `sof-` prefix on all resources, remove host port mapping for DB, add restart policies and resource limits

**M2: Nginx Needs Fixes**
- `nginx.conf` references `/var/run/nginx.pid` which requires root
- Missing gzip compression
- Missing WebSocket support for HMR in development
- **Fix:** Update nginx.conf and Dockerfile

**M3: Frontend Dockerfile Not Multi-Stage**
- Backend Dockerfile correctly uses multi-stage build, frontend does not
- **Fix:** Add multi-stage Dockerfile.frontend with production target

**M4: Database Schema Missing Indexes**
- Missing composite indexes for common query patterns:
  - `transaction_alerts.matter_id + severity`
  - `audit_logs.matter_id + created_at`
  - `documents.matter_id + status`
  - `statement_validations.matter_id + status`
  - `checks.matter_id + status`
  - `fundsevents.matter_id + sequence_order`
  - `transactions.matter_id + txn_date`
- **Fix:** Create Alembic migration with composite indexes

**M5: Oversized Files Need Splitting**
- `sof_assessment.py` (2,187 lines) — mixes storage, date parsing, funds lineage, AI assessment, file upload, API endpoints
- `transactions.py` (923 lines) — mixes CSV parsing, alert generation, dashboard stats, API endpoints
- `matters.py` (897 lines) — mixes workflow engine, Word doc generation, completion calc, API endpoints
- **Fix:** Split into focused modules (see Section 3.3)

**M6: Duplicate `get_sync_db()` Functions**
- Defined identically in `transactions.py`, `sof_assessment.py`, `statement_validation.py`
- **Fix:** Consolidate into `db/session.py`

#### MODERATE Issues

- No test configuration or `conftest.py`
- Missing `.env.example` at Docker Compose level
- Alembic hardcoded URL conflicts with env-based approach
- Admin seed scripts have inconsistent credentials (two different scripts, different passwords)
- Health check endpoint doesn't actually check database connectivity
- Test files scattered across multiple directories

### 3.2 Target Docker Architecture

```
                    +------------------+
                    |    sof-nginx     |
                    |   (port 80)      |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
    +---------+---------+     +-------------+---------+
    |   sof-frontend    |     |    sof-backend        |
    |  (port 5173 int)  |     |    (port 8000 int)    |
    +-------------------+     +----------+------------+
                                         |
                              +----------+------------+
                              |   sof-pgbouncer       |
                              |   (port 6432 int)     |
                              +----------+------------+
                                         |
                              +----------+------------+
                              |   sof-postgres        |
                              |   (port 5432 int)     |
                              +----------+------------+

    +-------------------+
    |    sof-redis      |
    |  (port 6379 int)  |
    +-------------------+
```

**Key changes from current:**
- PgBouncer between backend and PostgreSQL (transaction mode, max 200 client connections)
- Redis for rate limiting backend and caching
- All container names prefixed `sof-`
- PostgreSQL port no longer exposed to host
- All volumes prefixed `sof-`
- All networks prefixed `sof-`
- Restart policies on all containers
- Memory/CPU limits on all containers

### 3.3 Code Refactoring Plan

**Split `sof_assessment.py` (2,187 lines -> ~5 files):**

| New File | Content | Approx Lines |
|----------|---------|------|
| `endpoints/sof_assessment.py` | API route handlers only | ~400 |
| `services/sof_storage.py` | JSON storage load/save, file locking | ~100 |
| `services/funds_lineage.py` | `run_automated_funds_lineage()` and helpers | ~500 |
| `services/sof_assessment_engine.py` | Already exists — keep as-is | 2,065 |
| `utils/date_helpers.py` | `parse_date_flexible()`, `format_date_uk()` | ~30 |

**Split `transactions.py` (923 lines -> ~3 files):**

| New File | Content | Approx Lines |
|----------|---------|------|
| `endpoints/transactions.py` | API route handlers only | ~300 |
| `services/transaction_alert_generator.py` | Alert generation from SoF bank statements | ~300 |
| `services/transaction_dashboard.py` | Dashboard statistics calculation | ~200 |

**Split `matters.py` (897 lines -> ~3 files):**

| New File | Content | Approx Lines |
|----------|---------|------|
| `endpoints/matters.py` | API route handlers only | ~200 |
| `services/matter_workflow.py` | Workflow engine, status transitions, completion % | ~250 |
| `services/matter_report.py` | Word document report generation | ~350 |

**Utility Consolidation:**
- `parse_date_flexible()` defined in 3+ places → `app/utils/date_helpers.py`
- `get_sync_db()` defined in 3 places → `app/db/session.py`
- `_safe_load_storage()` / `load_storage()` / `save_storage()` → `app/services/sof_storage.py`

### 3.4 Database Optimization Plan

**New Alembic Migration — Composite Indexes:**

```sql
CREATE INDEX ix_transaction_alerts_matter_severity ON transaction_alerts (matter_id, severity);
CREATE INDEX ix_audit_logs_matter_created ON audit_logs (matter_id, created_at DESC);
CREATE INDEX ix_documents_matter_status ON documents (matter_id, status);
CREATE INDEX ix_statement_validations_matter_status ON statement_validations (matter_id, status);
CREATE INDEX ix_checks_matter_status ON checks (matter_id, status);
CREATE INDEX ix_fundsevents_matter_sequence ON fundsevents (matter_id, sequence_order);
CREATE INDEX ix_transactions_matter_date ON transactions (matter_id, txn_date);
```

**Connection Pooling Update:**
- Backend connects through PgBouncer (port 6432) instead of PostgreSQL directly
- Reduce SQLAlchemy pool to `pool_size=5` since PgBouncer handles pooling
- Keep `pool_pre_ping=True` for PgBouncer connection recycling

**Health Check Enhancement:**
- `/health` endpoint to verify: database connectivity, PgBouncer connectivity, Redis connectivity, disk space

### 3.5 Testing Plan

**Current test coverage is minimal:**
- 2 test files in `backend/tests/`
- 6 scattered test scripts in wrong directories
- No `conftest.py`, no fixtures, no factories

**Planned test structure:**

```
backend/tests/
  conftest.py                          — Test DB, fixtures, factories
  test_auth.py                         — Auth endpoint tests
  test_matters.py                      — Matters CRUD + workflow
  test_transactions.py                 — Transaction upload + alerts
  test_sof_assessment.py               — SoF assessment flow
  test_statement_validation.py         — Already exists
  test_statement_validation_integration.py — Already exists
  test_health.py                       — Health check tests
  test_models.py                       — Model creation/validation
  test_security.py                     — Security utils tests
  load/
    locustfile.py                      — Load testing with Locust
```

### 3.6 Code Expert Execution Sequence

| Phase | Description | Dependencies |
|-------|-------------|-------------|
| **A: Infrastructure** | Docker hardening, PgBouncer, Redis, nginx fixes, Dockerfiles | None |
| **B: Database & Session** | Shared sync engine, PgBouncer config, composite indexes, health check | Phase A |
| **C: Code Refactoring** | Split oversized files, consolidate duplicates, replace inline engines | Phase B |
| **D: Testing** | conftest.py, endpoint tests, model tests, load testing | Phase C |
| **E: Verification** | Clean docker build, health checks, full test suite, smoke test | Phase D |

**Estimated effort:** ~40 hours

---

## 4. BRANDING EXPERT PLAN

### 4.1 Brand Reference Analysis

**Brand Identity Direction (from CLAUDE.md + existing logo assets):**
- **Sector:** Anti-Financial Crime Solutions for law firms
- **Tone:** Professional, authoritative, trustworthy
- **Aesthetic:** Clean, modern, minimal
- **Audience:** Lawyers, compliance officers, paralegals

**Existing Logo Colors Extracted:**
- `#1a1a2e` — Deep navy/dark (logo "AGORA" text, `brand-dark`)
- `#4a6cf7` — Medium blue (logo "Consulting AI" text, `primary-500`)
- `#64748b` — Slate gray (tagline text)

**Note:** WebFetch to agoraconsulting.ai was denied by permissions. Palette is extrapolated from existing logo colors and brand description. May need refinement after PM/stakeholder review of live site.

### 4.2 Brand Audit: Current vs. Target

| Aspect | Current State | Target State |
|--------|---------------|--------------|
| Overall Tone | Developer prototype — functional but generic | Professional, authoritative — law-firm-grade |
| Color Palette | Generic blue/gray — looks like SaaS template | Refined navy/blue with warm neutral undertones |
| Typography | Inter is good but used inconsistently | Inter retained with strict hierarchy rules |
| Navigation | Minimal dark bar, functional but plain | Distinguished header with clear brand presence |
| Icons | Unicode emojis throughout | Heroicons (already a dependency) — professional |
| Buttons | Inconsistent sizing and radius | Standardized sizes (sm/md/lg), consistent 8px radius |
| Cards | Plain white with basic shadow | Subtle border + shadow, optional header stripe |
| Tables | Inconsistent markup patterns | Unified table component |
| Loading | Basic spinner only | Skeleton loaders for content, spinner for actions |
| Empty States | Emoji + text | Icon-based with clear call to action |
| Accessibility | Partial — some focus rings | Full WCAG 2.1 AA compliance |

### 4.3 Issues Identified in Current State

1. **Inconsistent border-radius:** `rounded-lg`, `rounded-md`, `rounded` mixed across buttons/inputs/cards
2. **Inconsistent padding:** Button padding varies (`py-2 px-4`, `py-3 px-4`, `px-6 py-2`)
3. **Inconsistent table patterns:** One uses HTML `<table>`, another uses CSS grid
4. **Heavy emoji usage:** Emojis used for icons throughout — unprofessional for law firm
5. **No consistent spacing scale:** Margins and paddings are ad-hoc
6. **Debug information visible:** Several components display API URLs and debug info to users
7. **Default credentials shown on login page:** Security concern and unprofessional
8. **Missing focus-visible styles:** Some elements have focus rings, others don't
9. **Browser `alert()` for feedback:** Uses `alert()` for success messages — should use toast notifications
10. **No breadcrumb navigation:** Deep pages lack context
11. **Green accent scale unused:** Defined in Tailwind config but not applied

### 4.4 Proposed Color Palette

**Primary Colors (Navy/Blue Authority Scale):**

```
primary-50:  #f0f4ff    Background tints, hover states
primary-100: #dce4f7    Light backgrounds, selected states
primary-200: #b8c9ef    Borders, dividers
primary-300: #8ba7e3    Disabled states, tertiary text
primary-400: #5d82d4    Secondary interactive elements
primary-500: #3461c7    Links, secondary buttons
primary-600: #1e3f8f    PRIMARY BRAND COLOR — buttons, active states
primary-700: #173172    Hover states on primary elements
primary-800: #122659    Nav bar background, dark surfaces
primary-900: #0d1b42    Deepest navy, text on light backgrounds
```

**Neutral Colors (Warm Slate Scale):**

```
neutral-50:  #f8f9fb    Page backgrounds
neutral-100: #f1f3f6    Card backgrounds, alternating rows
neutral-200: #e2e5eb    Borders, dividers
neutral-300: #c8cdd6    Disabled text, placeholders
neutral-400: #9ba3b1    Secondary text, icons
neutral-500: #6b7280    Body text (secondary)
neutral-600: #4b5563    Body text (primary)
neutral-700: #374151    Headings (secondary)
neutral-800: #1f2937    Headings (primary)
neutral-900: #111827    Strongest text, page titles
```

**Semantic Colors:**

| Purpose | 50 | 500 | 600 | 700 |
|---------|-----|-----|-----|-----|
| Success | #f0fdf4 | #22c55e | #16a34a | #15803d |
| Warning | #fffbeb | #f59e0b | #d97706 | #b45309 |
| Danger | #fef2f2 | #ef4444 | #dc2626 | #b91c1c |
| Info | #eff6ff | #3b82f6 | #2563eb | #1d4ed8 |

**Status-to-Color Mapping:**

| Status | Background | Text | Border |
|--------|-----------|------|--------|
| Draft | neutral-100 | neutral-700 | neutral-200 |
| Awaiting Client | info-50 | info-700 | info-200 |
| Under Review | warning-50 | warning-700 | warning-200 |
| Queries Raised | warning-100 | warning-800 | warning-300 |
| Approved | success-50 | success-700 | success-200 |
| Rejected | danger-50 | danger-700 | danger-200 |
| Completed | primary-50 | primary-700 | primary-200 |

| Risk Level | Background | Text |
|-----------|-----------|------|
| Low | success-50 | success-700 |
| Medium | warning-50 | warning-700 |
| High | danger-50 | danger-700 |
| Critical | danger-100 | danger-900 |

### 4.5 Typography System

**Font:** Keep Inter — excellent for data-dense professional applications.

```
Primary:  'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif
Mono:     'JetBrains Mono', 'Fira Code', 'Source Code Pro', Menlo, monospace
```

Remove weight 300 (light) — poor readability at small sizes.

**Type Scale:**

| Token | Size | Weight | Usage |
|-------|------|--------|-------|
| display-lg | 30px | 700 (bold) | Page titles |
| display-sm | 24px | 700 (bold) | Modal titles, section headers |
| heading-lg | 20px | 600 (semibold) | Card titles, panel headers |
| heading-sm | 18px | 600 (semibold) | Sub-section headers |
| body-lg | 16px | 400 (normal) | Primary body text |
| body-md | 14px | 400 (normal) | Secondary text, descriptions |
| label | 14px | 500 (medium) | Form labels, table headers |
| caption | 12px | 400 (normal) | Timestamps, metadata |
| overline | 11px | 600 (semibold) | Table column headers, UPPERCASE |
| stat | 30px | 700 (bold) | Stat card values |

### 4.6 Component Style Guide Summary

**Buttons (3 sizes, 5 variants):**
- Sizes: sm (`text-xs px-3 py-1.5`), md (`text-sm px-4 py-2`), lg (`text-sm px-6 py-3`)
- Variants: primary, secondary, danger, ghost, link
- All use `rounded-md`, `font-medium`, `shadow-sm`
- Disabled: `opacity-50 cursor-not-allowed pointer-events-none`

**Cards:**
- Standard: `bg-white rounded-lg border border-neutral-200 shadow-sm p-6`
- Elevated: same with `shadow-md`
- Interactive: adds `hover:shadow-md hover:border-neutral-300 cursor-pointer`

**Form Inputs:**
- Standard: `px-3.5 py-2.5 text-sm border border-neutral-300 rounded-md`
- Focus: `focus:ring-2 focus:ring-primary-500 focus:border-primary-500`
- Error: `border-danger-500 focus:ring-danger-500`

**Tables:**
- Standardize on HTML `<table>` for accessibility
- Header: `bg-neutral-50 text-xs font-semibold uppercase tracking-wider`
- Rows: `hover:bg-neutral-50 divide-y divide-neutral-200`

**Navigation:**
- Nav bar: `bg-primary-800 h-16`
- Active link: `text-white border-b-2 border-white`
- Inactive: `text-primary-200 hover:text-white`

**Modals:**
- Overlay: `bg-neutral-900/50 backdrop-blur-sm`
- Container: `bg-white rounded-lg shadow-xl max-w-md`
- Structured: header / body / footer sections

**New: Toast Notifications (replacing browser `alert()`):**
- `fixed top-4 right-4 z-50` with slide-in animation
- Uses Heroicons for status icons

### 4.7 Page-by-Page Redesign Plan

**Login Page:**
- Replace gradient with solid `neutral-50` background
- Add Agora logo prominently above form
- Remove default credentials display (or dev-only env check)
- Add "Anti-Financial Crime Solutions" tagline below logo
- Standardize input styling
- Add "Forgot Password?" link placeholder

**Layout / Navigation:**
- Reduce nav height from h-20 to h-16
- Change background to `primary-800`
- Dynamic active link detection based on current route
- Add user avatar initial circle
- Style logout as ghost button with icon

**Dashboard:**
- New card styling with semantic top-border accents per stat type
- Standardize activity items and pending actions
- Proper heading hierarchy

**Matters Page:**
- Standardize create modal with header/body/footer
- Unified table styling with hover states
- Consistent badge system for status and risk columns
- Add row click navigation

**Matter Detail Page:**
- Replace all emoji tab names with Heroicons:
  - SoF Assessment → `DocumentTextIcon`
  - Transaction Review → `ExclamationTriangleIcon`
  - Funds Lineage → `ArrowsRightLeftIcon`
- Replace button emojis with Heroicons
- Add breadcrumb: `Matters > {Reference Number}`
- Add matter summary panel above tabs

**Transaction Components:**
- Remove debug info from UI
- Convert CSS grid to HTML table for accessibility
- Standardize severity badges
- Clean up empty states

**SoF Assessment, Funds Lineage, Status Update Modal:**
- Replace emojis with Heroicons
- Apply consistent card/badge/form styling
- Replace `alert()` with toast notifications

### 4.8 Accessibility Checklist (WCAG 2.1 AA)

| Category | Requirements |
|----------|-------------|
| **Color Contrast** | 4.5:1 minimum for normal text, 3:1 for large text. Fix: `neutral-400` placeholders fail (3.1:1) → use `neutral-500` (5.9:1) |
| **Keyboard** | All interactive elements focusable, focus order follows layout, modals trap focus, Escape closes modals, skip-to-content link |
| **Semantic HTML** | `<main>`, `<nav>`, `<header>`, `<footer>` landmarks. Heading hierarchy (single `<h1>` per page). Tables use proper `<th scope>` |
| **Screen Reader** | Images have `alt` text, decorative icons `aria-hidden`, stand-alone icon buttons have `aria-label`, status changes via `aria-live` |
| **Motion** | Respect `prefers-reduced-motion`, no content conveyed solely by color |
| **Responsive** | Desktop (1280px+) full layout, tablet (768px+) responsive collapse, 44x44px minimum touch targets |

### 4.9 Branding Implementation Sequence

1. Tailwind config update (colors, typography tokens)
2. Global styles (`index.css`)
3. Logo and favicon color update
4. Layout/Navigation
5. Login Page
6. Dashboard
7. Matters Page
8. Matter Detail Page
9. Transaction components
10. SoF Assessment component
11. Funds Lineage component
12. Status Update Modal
13. Accessibility final pass

**Estimated files to modify:** 15
**Estimated effort:** ~30 hours
**No new npm packages required** — Heroicons and Headless UI already dependencies

---

## 5. SECURITY EXPERT PLAN

### 5.1 Current Security Posture — What's Good

| Area | Status | Details |
|------|--------|---------|
| Password hashing | DONE | Bcrypt via passlib CryptContext |
| Password policy | DONE | 12+ chars, uppercase, lowercase, digits, special |
| Account lockout | DONE | 5 attempts, 15-min lockout |
| RBAC | DONE | 3 roles (Admin, Partner, Analyst) with dependency enforcement |
| Rate limiting | DONE | slowapi (60/min) + Nginx (60r/m API, 5r/m login) |
| Security headers | DONE | X-Content-Type-Options, X-Frame-Options, HSTS, CSP, Referrer-Policy, Permissions-Policy |
| Non-root containers | DONE | All 4 containers run as non-root users |
| Network segmentation | DONE | backend-net and frontend-net |
| Structured logging | DONE | structlog throughout |
| MFA enrollment | DONE | TOTP setup/verify/disable endpoints exist |
| Audit log model | DONE | Comprehensive action types, IP/user-agent capture |

### 5.2 Security BLOCKERs (6 — Must Fix Before Any Deployment)

**B1: MFA Not Enforced During Login**
- Location: `auth.py`, lines 82-168
- Login endpoint issues full access tokens WITHOUT checking `mfa_enabled`
- Users with MFA enabled bypass it entirely — the MFA system provides zero security value
- **Impact:** Complete MFA bypass
- **Fix:** Two-phase login: Phase 1 validates credentials → returns `mfa_pending` token if MFA enabled. Phase 2 new endpoint `/auth/mfa/authenticate` validates TOTP + `mfa_pending` token → issues full tokens.

**B2: Hardcoded Default Secrets**
- `backend/.env`: `SECRET_KEY=your-secret-key-here-change-in-production`
- `config.py`: fallback `secrets.token_urlsafe(32)` generates new key on restart → invalidates all JWTs
- `docker-compose.yml`: `SECRET_KEY=${SECRET_KEY:-dev-secret-key-change-in-production}`
- `docker-compose.yml`: default Postgres credentials `postgres:postgres`
- **Impact:** Predictable JWT signing keys allow token forgery
- **Fix:** Generate strong defaults, remove fallbacks, require explicit `.env`

**B3: No .gitignore File**
- No `.gitignore` exists anywhere in the project
- `.env` file containing secrets has no protection from version control
- **Impact:** All secrets exposed if pushed to any repository
- **Fix:** Create `.gitignore` at project root

**B4: TOTP Secret Stored in Plaintext**
- Location: `user.py`, line 36: `totp_secret = Column(String(64), nullable=True)`
- If database compromised, attacker can generate valid TOTP codes for any user
- **Impact:** Complete MFA bypass on database compromise
- **Fix:** Encrypt TOTP secrets at rest using Fernet encryption derived from SECRET_KEY

**B5: No Token Revocation / Logout Mechanism**
- No logout endpoint exists. No token blacklist, no session table, no revocation
- JWTs remain valid until expiry (24 hours access, 7 days refresh)
- **Impact:** Stolen tokens cannot be invalidated. Users who leave the firm retain access for up to 7 days
- **Fix:** Token blacklist table in PostgreSQL, `jti` claim on JWTs, `/auth/logout` endpoint, blacklist check in `decode_token()`

**B6: Sensitive Data in `/tmp` as Unencrypted JSON**
- Location: `sof_assessment.py`, line 72: `STORAGE_FILE = Path("/tmp/sof_assessment_storage.json")`
- Replicated in `matters.py` (line 23) and `transactions.py` (lines 230-239, 349, 463, 701)
- Highly sensitive financial crime investigation data stored world-readable in `/tmp`
- **Impact:** Any process or user on the host can read privileged law firm work product — data breach vector
- **Fix:** Move to encrypted storage on mounted volume or PostgreSQL

### 5.3 Security MAJORs (12 — Must Fix Before Production)

| ID | Issue | Impact | Fix |
|----|-------|--------|-----|
| M1 | No CSRF protection | Cross-site request forgery on state-changing operations | Add CSRF middleware/tokens |
| M2 | CSP allows `unsafe-inline` and `unsafe-eval` | Negates most XSS protections | Remove; use nonces |
| M3 | No password history/rotation | Users can reuse compromised passwords | Add `password_history` table, enforce rotation |
| M4 | No breach detection (HaveIBeenPwned) | Users can set known-breached passwords | k-anonymity API check |
| M5 | Sync DB anti-pattern creates connection leaks | Connection exhaustion under load, DoS | Shared sync engine in `db/session.py` |
| M6 | PostgreSQL port 5432 exposed to host | Database accessible outside container network | Remove host port mapping |
| M7 | Debug mode enabled by default | SQL queries logged, stack traces exposed | Set `DEBUG=False` by default |
| M8 | API documentation exposed unauthenticated | Full API schema visible to anyone | Gate `/docs` and `/redoc` behind auth |
| M9 | Auth events not persisted to audit_logs DB table | No tamper-resistant queryable audit trail | Write auth events to `audit_logs` table |
| M10 | Nginx on port 80 only, no TLS | All traffic unencrypted; HSTS header meaningless | Add TLS termination (self-signed for local) |
| M11 | No concurrent session limits | Compromised account usable from multiple locations | Session tracking table, configurable limit |
| M12 | File upload validation insufficient | Only extension check, no MIME/magic bytes, no malware scan | Add MIME validation, file size check at app level |

### 5.4 Security MINORs (4)

| ID | Issue | Fix |
|----|-------|-----|
| N1 | `datetime.utcnow()` deprecated in Python 3.12+ | Use `datetime.now(timezone.utc)` |
| N2 | Sequential integer user IDs in JWT `sub` claim | Enables IDOR enumeration; consider UUIDs |
| N3 | No request ID correlation for audit trail | Add middleware generating unique request IDs |
| N4 | Error responses leak raw exception messages | Sanitize error details in production |

### 5.5 Threat Model (STRIDE)

#### Spoofing (Identity)

| Threat | Mitigation | Gap | Risk |
|--------|-----------|-----|------|
| Credential theft via network sniffing | HSTS header | No TLS configured | CRITICAL |
| JWT token forgery | HS256 signing | Default/predictable SECRET_KEY | CRITICAL |
| MFA bypass | TOTP exists | Not enforced during login | CRITICAL |
| Session hijacking | Bearer token auth | No token binding, no session tracking | HIGH |
| Brute force login | Lockout after 5 | No progressive delay | MEDIUM |

#### Tampering

| Threat | Mitigation | Gap | Risk |
|--------|-----------|-----|------|
| JWT modification | HS256 signature | Weak key allows forgery | CRITICAL |
| Audit log tampering | Audit model | No write-once enforcement | HIGH |
| SoF data tampering | None | World-readable `/tmp` JSON | CRITICAL |
| File upload tampering | Extension check | No integrity verification | MEDIUM |

#### Repudiation

| Threat | Mitigation | Gap | Risk |
|--------|-----------|-----|------|
| Deny performing action | AuditLog, structlog | Auth events not in DB | HIGH |
| Deny approving matter | Approval model | No digital signature | MEDIUM |

#### Information Disclosure

| Threat | Mitigation | Gap | Risk |
|--------|-----------|-----|------|
| Secrets in code | Env vars | Default secrets hardcoded | CRITICAL |
| TOTP secrets in DB | None | Plaintext storage | CRITICAL |
| API schema exposed | Swagger/ReDoc | Unauthenticated access | HIGH |
| SQL logging in production | Debug mode | DEBUG=True by default | HIGH |
| SoF data readable | None | `/tmp` is world-readable | CRITICAL |

#### Denial of Service

| Threat | Mitigation | Gap | Risk |
|--------|-----------|-----|------|
| Connection exhaustion | Pool (20+10) | Sync anti-pattern bypasses pool | HIGH |
| CPU exhaustion via PDF | None | No timeout on PDF processing | HIGH |
| Large file upload | Nginx 50MB | No app-level check | MEDIUM |

#### Elevation of Privilege

| Threat | Mitigation | Gap | Risk |
|--------|-----------|-----|------|
| IDOR (horizontal) | Auth deps | No per-matter ownership validation | HIGH |
| Container escape | Non-root users | No read-only fs, no seccomp | MEDIUM |
| DB privilege escalation | Default user | App connects as superuser `postgres` | HIGH |

### 5.6 Security Controls Matrix

| Control | Status |
|---------|--------|
| Password hashing (bcrypt) | DONE |
| Password policy (12+ complexity) | DONE |
| Account lockout | DONE |
| RBAC enforcement | DONE |
| Rate limiting (app + nginx) | DONE |
| Security headers | PARTIAL — CSP too permissive |
| MFA enrollment | DONE |
| **MFA enforcement at login** | **MISSING** |
| **Token revocation / logout** | **MISSING** |
| **CSRF protection** | **MISSING** |
| **TLS encryption** | **MISSING** |
| Secrets management | WEAK — defaults hardcoded |
| **TOTP encryption at rest** | **MISSING** |
| Audit logging (persistent) | PARTIAL — model exists, auth events not persisted |
| Container hardening | PARTIAL — non-root, but no read-only fs |
| Dependency scanning | NOT RUN (pip-audit included but never executed) |
| **.gitignore** | **MISSING** |

### 5.7 Dependency Vulnerability Concerns

| Package | Version | Concern |
|---------|---------|---------|
| `python-jose` | 3.3.0 | Unmaintained since 2022, known CVEs. Migrate to `PyJWT` |
| `passlib` | 1.7.4 | Compatibility issues with bcrypt >= 4.1. Pin bcrypt version |
| `psycopg2-binary` | 2.9.9 | Binary dist not recommended for production; use `psycopg2` |
| `sentry-sdk` | 1.39.2 | Sends error data to external service — disable or scrub for law firm |
| `boto3` / `minio` | — | Included but may be unused; unnecessary attack surface |

### 5.8 Security Implementation Priority

**Phase 1 — Critical Blockers (before ANY deployment):**

| # | Task | Effort |
|---|------|--------|
| 1 | Create `.gitignore` | 5 min |
| 2 | Fix hardcoded secrets, generate strong defaults | 1 hour |
| 3 | Implement MFA enforcement during login (two-phase auth) | 4 hours |
| 4 | Encrypt TOTP secrets at rest (Fernet) | 2 hours |
| 5 | Implement token revocation and logout | 3 hours |
| 6 | Move SoF storage from `/tmp` to encrypted volume or PostgreSQL | 4 hours |

**Phase 2 — Major Issues (before production):**

| # | Task | Effort |
|---|------|--------|
| 1 | TLS in Nginx (self-signed for local) | 2 hours |
| 2 | Remove PostgreSQL host port mapping | 10 min |
| 3 | Disable debug mode by default | 30 min |
| 4 | Restrict API docs to authenticated users | 1 hour |
| 5 | Tighten CSP policy (remove unsafe-inline/eval) | 2 hours |
| 6 | Persistent audit logging for auth events | 3 hours |
| 7 | File upload validation hardening | 2 hours |
| 8 | Fix sync DB connection leak | 3 hours |
| 9 | Password history and breach detection | 3 hours |
| 10 | Concurrent session limits | 2 hours |
| 11 | CSRF protection | 2 hours |

**Phase 3 — Hardening (pre-production polish):**

| # | Task | Effort |
|---|------|--------|
| 1 | Container security hardening (read-only fs, seccomp, no-new-privileges) | 4 hours |
| 2 | PostgreSQL dedicated user (minimal privileges) | 2 hours |
| 3 | Dependency audit and replacements | 3 hours |
| 4 | Security testing (SAST via bandit, SCA via pip-audit, container scan via trivy) | 4 hours |
| 5 | Minor issues (N1-N4) | 2 hours |

**Total estimated security effort: ~48 hours**

### 5.9 Incident Response Plan Outline

| Phase | Actions |
|-------|---------|
| **Preparation** | Define incident classification (P1-P4), establish response team, pre-configure audit log queries |
| **Detection** | Monitor audit_logs for anomalies, alert on lockouts, track error rates |
| **Containment** | Disable affected accounts, revoke tokens, block IPs at Nginx |
| **Eradication** | Identify root cause, patch vulnerability, rotate all secrets, rebuild images |
| **Recovery** | Verify controls operational, re-enable accounts after identity verification, monitor for recurrence |
| **Lessons Learned** | Document timeline/impact/root cause, update threat model, brief compliance team |

---

## 6. REVIEW TEAM LEAD PLAN

### 6.1 Review Team Structure

```
Review Team Lead
├── Code Reviewer       → Paired with Code Expert (1:1)
├── Branding Reviewer   → Paired with Branding Expert (1:1)
└── Security Reviewer   → Paired with Security Expert (1:1)
```

### 6.2 Review Process Workflow

```
Step 1: SUBMISSION     → Agent marks work "Ready for Review" → PM notifies RTL
Step 2: ASSIGNMENT     → RTL assigns to appropriate specialist reviewer
Step 3: EXECUTION      → Reviewer performs review against checklist (4-hour target)
Step 4: COLLATION      → RTL collects all reports, deduplicates, cross-references
Step 5: SUBMIT TO PM   → Consolidated report → PM redistributes to agents
Step 6: ACTION         → Agents fix BLOCKERs/MAJORs, resubmit for targeted re-review
Step 7: SIGN-OFF       → All BLOCKERs/MAJORs resolved → RTL issues sign-off
```

### 6.3 Severity Rating System

| Severity | Symbol | Definition | Deployment Impact |
|----------|--------|-----------|-------------------|
| BLOCKER | RED | Critical defect — security vuln, data loss, functionality breakage, compliance violation | Blocks deployment. Must fix immediately. |
| MAJOR | ORANGE | Significant defect — degraded functionality, poor security, significant UX issue | Blocks deployment if unresolved by deploy date. |
| MINOR | YELLOW | Low-impact — cosmetic, code style, minor inconsistency, minor performance | Does not block deployment. |
| SUGGESTION | BLUE | Enhancement — better approach, optimization, future-proofing | At agent's discretion. |

### 6.4 Feedback Report Template

```
=================================================================
REVIEW FEEDBACK REPORT
=================================================================
Report ID:        RTL-REPORT-YYYY-MM-DD-NNN
Domain:           Code / Branding / Security
Reviewer:         Code Reviewer / Branding Reviewer / Security Reviewer
Date:             YYYY-MM-DD
Review Scope:     [What was reviewed]
Files Reviewed:   [Absolute file paths]
-----------------------------------------------------------------

FINDING #RTL-NNN
  Severity:       BLOCKER / MAJOR / MINOR / SUGGESTION
  Category:       [e.g., Authentication, Docker, UI Consistency]
  File(s):        [Absolute path(s)]
  Line(s):        [Line range]
  Description:    [What was found]
  Impact:         [What risk this creates]
  Recommendation: [What should be done]
  Assigned To:    [Code Expert / Branding Expert / Security Expert]
  Status:         OPEN

-----------------------------------------------------------------

SUMMARY
  BLOCKERs:       N  — Must fix before deployment
  MAJORs:         N  — Must fix, can proceed with other work
  MINORs:         N  — Should fix, non-blocking
  SUGGESTIONs:    N  — Nice to have

REVIEW VERDICT:   PASS / PASS WITH CONDITIONS / FAIL
=================================================================
```

### 6.5 Code Reviewer Checklist (26 items)

**A. Functionality Preservation (9 items):**
- All API endpoints respond identically
- All frontend routes render and function
- Matter CRUD, document upload, transaction review, SoF assessment all work
- Login/logout/session management works
- Dashboard displays correct data

**B. Docker & Infrastructure (12 items):**
- `docker-compose up --build` completes without errors
- All containers start and pass health checks
- All containers run as non-root
- Data persists across restarts
- Network isolation verified
- No hardcoded credentials in Docker configs
- Multi-stage builds verified
- Health checks have appropriate intervals
- Container restart policies defined

**C. Database & Schema (14 items):**
- PostgreSQL 16 confirmed
- Migrations run cleanly
- Appropriate indexes exist
- No N+1 query patterns
- Connection pooling adequate for 100+ users
- Sessions properly commit/rollback/close
- No raw SQL injection vectors
- Timezone-aware datetimes throughout

**D. Code Quality (9 items):**
- No dead code/unused imports
- Consistent code style
- Error handling covers all paths
- Structured logging used consistently
- No `print()` in production code
- Environment variables for all config

**E. Performance (7 items):**
- Pagination on queries
- Large file uploads streamed
- No synchronous blocking in async endpoints
- Connection pooling adequate
- Nginx worker_connections appropriate

**F. Testing (5 items):**
- Unit tests for core business logic
- Integration tests for API endpoints
- Tests can run via pytest
- No tests reference external services

### 6.6 Branding Reviewer Checklist (24 items)

**A. Brand Alignment (7 items):**
- Color palette matches brand direction
- Typography professional and law-firm appropriate
- Logo renders correctly
- Brand tagline displayed appropriately
- Overall tone: professional, authoritative, trustworthy

**B. Component Consistency (8 items):**
- Buttons: consistent size, color, hover/disabled states
- Form inputs: consistent borders, focus, error styling
- Cards: consistent radius, shadow, padding
- Tables: consistent header/row/hover styling
- Badges: consistent styling for severity levels

**C. User Flows (7 items):**
- Login flow clear and professional
- Dashboard key metrics visible
- Matters list sortable/filterable
- All flows appropriate for legal professionals

**D. States (5 items):**
- Loading states present
- Error states with recovery actions
- Empty states with helpful messaging
- Success states with confirmation

**E. Responsive Design (5 items):**
- Desktop (1280px+) optimal
- Tablet (768px+) reflows appropriately

**F. Accessibility WCAG 2.1 AA (8 items):**
- Form inputs have labels
- Color contrast 4.5:1 minimum
- Focus indicators visible
- Keyboard navigation works
- Screen reader compatible
- No info conveyed by color alone

### 6.7 Security Reviewer Checklist (43 items)

**A. Authentication (9 items):**
- Bcrypt hashing, password policy, lockout, registration restricted, failed logins logged

**B. Token Management (7 items):**
- Appropriate expiry, type differentiation, refresh mechanism, revocation, strong signing key

**C. MFA (7 items):**
- Setup, verification, disable, status endpoint, **enforcement during login**, backup codes, encrypted storage

**D. RBAC (6 items):**
- Roles defined, enforcement applied, no privilege escalation, IDOR protection

**E. HTTP Security Headers (7 items):**
- All standard headers present and correctly configured

**F. Input Validation (7 items):**
- Pydantic schemas, ORM-only queries, file upload restrictions, XSS/CSRF prevention

**G. Secrets Management (5 items):**
- No secrets in source, strong defaults, Docker secrets for production

**H. Container Security (10 items):**
- Non-root, minimal images, network isolation, PostgreSQL hardened, read-only filesystems

**I. Audit & Logging (6 items):**
- Auth events persisted, structured logging, tamper-resistant, sensitive data not logged

**J. Dependencies (4 items):**
- Scanned for CVEs, outdated packages identified, lock files committed

### 6.8 Preliminary Findings (Pre-Review Flags)

**For Code Reviewer:**
1. No test suite found — only ad-hoc scripts
2. Frontend Dockerfile not multi-stage
3. API client (`api.ts`) only has 2 methods — appears incomplete
4. DashboardPage uses hardcoded sample data
5. `docker-compose.yml` uses deprecated `version: '3.8'`

**For Branding Reviewer:**
1. Default credentials displayed on login page
2. Tailwind palette may not align with agoraconsulting.ai (needs site verification)
3. No loading/empty/error states in DashboardPage
4. Navigation has no dynamic active state detection

**For Security Reviewer:**
1. MFA not enforced at login
2. Tokens stored in localStorage (XSS vector)
3. No token refresh or revocation mechanism
4. CSP allows `unsafe-inline` and `unsafe-eval`
5. PostgreSQL port 5432 exposed to host
6. No CSRF protection
7. TOTP secret stored plaintext
8. 24-hour access token expiry excessive for law firm
9. SECRET_KEY has default fallback
10. No `.gitignore`

### 6.9 Review Timeline SLAs

| Activity | Target | Maximum |
|----------|--------|---------|
| Initial full review (per domain) | 4 hours | 8 hours |
| Re-review (targeted, post-fix) | 2 hours | 4 hours |
| Collation of all reports | 1 hour | 2 hours |
| Consolidated report delivery | 1 hour | 2 hours |

**Expected cycle:** 2-3 review cycles to resolve all BLOCKERs and MAJORs.

### 6.10 Definition of "Review Complete"

A domain is **COMPLETE** when:
1. Zero BLOCKER findings remain OPEN or IN PROGRESS
2. Zero MAJOR findings remain OPEN or IN PROGRESS
3. All MINOR findings resolved or documented with deferral justification
4. All SUGGESTION findings acknowledged
5. All checklist items explicitly assessed (PASS / FAIL / N/A)
6. Re-review performed on all actioned findings
7. No new BLOCKERs or MAJORs introduced by fixes

**Full Project Sign-Off** requires all three domains COMPLETE.

---

## 7. CROSS-AGENT DEPENDENCIES

### 7.1 Dependency Map

```
┌──────────────────────────────────────────────────────────────────────┐
│                     EXECUTION DEPENDENCIES                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Security B3 (.gitignore)          ──► Must be FIRST action         │
│                                                                      │
│  Code Phase A (Docker infra)       ──► Security M6 (remove PG port) │
│                                    ──► Security container hardening  │
│                                                                      │
│  Code Phase B (DB session fix)     ──► Security M5 (sync DB leak)   │
│                                    ──► Both agents fixing same root  │
│                                       cause — coordinate to avoid    │
│                                       conflict                       │
│                                                                      │
│  Code Phase C (file refactoring)   ──► Security B6 (/tmp storage)   │
│                                    ──► Code moves storage from /tmp  │
│                                       to volume; Security encrypts   │
│                                       it — must sequence correctly   │
│                                                                      │
│  Branding (all)                    ──► Independent of Code/Security  │
│                                    ──► Can run in parallel           │
│                                    ──► BUT: if Code Expert changes   │
│                                       component file structure,      │
│                                       Branding must apply to new     │
│                                       file locations                 │
│                                                                      │
│  Security (auth hardening)         ──► May change auth endpoint      │
│                                       contracts (MFA two-phase)      │
│                                    ──► Frontend LoginPage must be    │
│                                       updated by Branding Expert     │
│                                       to handle MFA flow             │
│                                                                      │
│  Review Team                       ──► Begins after agents submit    │
│                                       completed work per phase       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.2 Shared File Conflicts

The following files are touched by multiple agents and require coordination:

| File | Code Expert | Branding Expert | Security Expert |
|------|------------|-----------------|-----------------|
| `docker-compose.yml` | Container names, networks, volumes, PgBouncer, Redis | — | Port removal, security_opt, read_only, secrets |
| `main.py` | — | — | Security headers, CSP, debug mode, CSRF |
| `auth.py` | Sync DB fix | — | MFA enforcement, logout, audit logging |
| `LoginPage.tsx` | — | Visual redesign | MFA two-phase flow UI |
| `nginx.conf` | Gzip, WebSocket, pid fix | — | TLS, server_tokens, header cleanup |
| `session.py` | Shared sync engine, PgBouncer URL | — | — |
| `config.py` | PgBouncer config | — | Debug default, secret validation |

**Resolution:** Code Expert executes first (infrastructure), then Security Expert (hardening), then Branding Expert (visual). Shared files are modified sequentially, not concurrently.

---

## 8. RISK REGISTER

| # | Risk | Likelihood | Impact | Owner | Mitigation |
|---|------|-----------|--------|-------|------------|
| R1 | Sync DB refactoring breaks query behavior | Medium | High | Code Expert | Test every endpoint before/after; compare response payloads |
| R2 | PgBouncer misconfiguration causes connection errors | Medium | High | Code Expert | Test with simple queries first; fallback to direct connection |
| R3 | Port 5432 conflict with host PostgreSQL | High | Medium | Code Expert | Use configurable port in `.env`; document |
| R4 | File storage path change breaks existing data | Medium | High | Code Expert | Mount new path but check old `/tmp` as fallback |
| R5 | Splitting service files introduces import errors | Low | Medium | Code Expert | Run full import test after each split |
| R6 | MFA two-phase login breaks existing frontend flow | Medium | High | Security Expert | Backward compatible — no MFA = same as current |
| R7 | CSP tightening breaks frontend | High | Medium | Security Expert | Test all pages after CSP changes; nonce system for inline scripts |
| R8 | Token revocation adds latency to every request | Low | Medium | Security Expert | Efficient blacklist lookup (indexed by JTI) |
| R9 | Color palette doesn't match actual agoraconsulting.ai brand | Medium | Medium | Branding Expert | Get PM to verify palette against live site before implementation |
| R10 | Emoji-to-Heroicon replacement misses some instances | Low | Low | Branding Expert | Grep for unicode emoji patterns after replacement |
| R11 | Accessibility changes alter visual appearance unexpectedly | Low | Medium | Branding Expert | Visual regression testing after each page |
| R12 | Docker prune commands destroy other projects' resources | High | Critical | ALL | **Rule 12 enforced** — only scoped `docker-compose` commands |
| R13 | Agent writes files outside SoF-Claude directory | Medium | High | ALL | All file paths must start with `/Users/patrickstones/Desktop/SoF-Claude/` |
| R14 | Agents make conflicting changes to shared files | Medium | High | PM | Sequential execution per dependency map |
| R15 | Review cycle takes too long, blocking deployment | Medium | Medium | Review Team Lead | Parallel reviews, 4-hour SLA, targeted re-reviews |

---

## 9. DOCKER ISOLATION RULES

**These rules are NON-NEGOTIABLE and apply to ALL agents.**

### Rule 12 (Added to CLAUDE.md)

Agents must **NEVER** run:
- `docker system prune`
- `docker volume prune`
- `docker image prune`
- Any global Docker cleanup command

**Only `docker-compose` commands scoped to `SoF-Claude/dev/app/` are permitted.**

All Docker resources must use the `sof-` prefix:

| Resource Type | Naming Convention | Examples |
|--------------|-------------------|----------|
| Containers | `sof-{service}` | `sof-postgres`, `sof-backend`, `sof-frontend`, `sof-nginx`, `sof-pgbouncer`, `sof-redis` |
| Volumes | `sof-{name}` | `sof-postgres_data`, `sof-backend_uploads`, `sof-redis_data` |
| Networks | `sof-{name}` | `sof-backend-net`, `sof-frontend-net` |

**Before running any Docker commands:**
1. Verify you are operating within `SoF-Claude/dev/app/`
2. Run `docker ps` to check existing containers — do NOT interfere with non-project containers
3. Run `docker network ls` to check existing networks — do NOT interfere with non-project networks

**Agents must NEVER stop, remove, or interfere with any Docker containers, images, networks, or volumes that are not part of this project.**

### Rule 13 (Added to CLAUDE.md)

**Local hosting only (Phase 1).** All services run on localhost. No cloud deployment, no external URLs, no public-facing endpoints. This restriction remains in effect until explicit sign-off for Phase 2.

---

## 10. EXECUTION SEQUENCE

### Recommended Phased Approach

```
PHASE 0: IMMEDIATE (Day 0, 30 minutes)
├── Security Expert: Create .gitignore (B3)
├── Security Expert: Fix hardcoded secrets (B2)
└── Code Expert: Verify sof- prefix on all Docker resources

PHASE 1: INFRASTRUCTURE (Days 1-2)
├── Code Expert Phase A:
│   ├── Harden docker-compose.yml (sof- prefixes, restart policies, limits)
│   ├── Add sof-pgbouncer container
│   ├── Add sof-redis container
│   ├── Fix nginx.conf (gzip, pid, WebSocket)
│   └── Multi-stage Dockerfile.frontend
└── Security Expert (parallel, non-conflicting files):
    ├── Remove PostgreSQL host port mapping (M6)
    ├── Add security_opt to containers
    └── Disable debug mode by default (M7)

PHASE 2: DATABASE & AUTH (Days 3-4)
├── Code Expert Phase B:
│   ├── Shared sync engine in db/session.py
│   ├── PgBouncer connection config
│   ├── Alembic migration for composite indexes
│   ├── Enhanced health check endpoint
│   └── Consolidate admin seed scripts
└── Security Expert (parallel, non-conflicting files):
    ├── MFA enforcement during login (B1)
    ├── Token revocation and logout (B5)
    ├── Encrypt TOTP secrets at rest (B4)
    └── Persistent auth audit logging (M9)

PHASE 3: CODE REFACTORING + SECURITY HARDENING (Days 5-7)
├── Code Expert Phase C:
│   ├── Extract utils/date_helpers.py
│   ├── Extract services/sof_storage.py (move from /tmp to volume)
│   ├── Extract services/funds_lineage.py
│   ├── Extract services/matter_workflow.py
│   ├── Extract services/matter_report.py
│   ├── Extract services/transaction_alert_generator.py
│   ├── Extract services/transaction_dashboard.py
│   ├── Slim down endpoint files
│   └── Replace all inline create_engine() calls
└── Security Expert (parallel, non-conflicting files):
    ├── TLS in Nginx (M10)
    ├── Tighten CSP (M2)
    ├── CSRF protection (M1)
    ├── File upload hardening (M12)
    ├── Password history/breach detection (M3, M4)
    ├── Concurrent session limits (M11)
    └── Restrict API docs (M8)

PHASE 4: BRANDING (Days 5-9, parallel with Phase 3)
├── Branding Expert (independent of Code/Security):
│   ├── Tailwind config update
│   ├── Global styles
│   ├── Logo/favicon update
│   ├── Layout/Navigation
│   ├── Login Page (must coordinate with Security for MFA flow)
│   ├── Dashboard, Matters, Matter Detail pages
│   ├── Transaction components
│   ├── SoF Assessment, Funds Lineage
│   ├── Status Update Modal
│   └── Accessibility pass

PHASE 5: TESTING (Days 8-10)
├── Code Expert Phase D:
│   ├── conftest.py with fixtures
│   ├── Auth, matters, transactions, health tests
│   ├── Move scattered test files
│   └── Load testing harness (Locust)
└── Security Expert:
    ├── SAST scan (bandit)
    ├── SCA scan (pip-audit, trivy)
    ├── Secrets scan (trufflehog)
    └── Business logic testing

PHASE 6: REVIEW (Days 10-12)
├── Review Team Lead triggers parallel reviews
├── Code Reviewer assesses Code Expert work
├── Branding Reviewer assesses Branding Expert work
├── Security Reviewer assesses Security Expert work
├── Consolidated report to PM
└── Action/re-review cycles until sign-off

PHASE 7: LOCAL DEPLOYMENT VERIFICATION (Day 12-13)
├── Clean docker-compose build from scratch
├── All containers start and pass health checks
├── Full test suite passes
├── Manual smoke test of all features
├── Zero functionality regression confirmed
└── PM sign-off for local deployment
```

---

## 11. DEFINITION OF DONE

### Per-Phase Completion Criteria

- [ ] All containers build without errors
- [ ] All containers pass health checks
- [ ] All existing API endpoints return identical responses (before/after)
- [ ] All existing tests pass
- [ ] No new secrets hardcoded
- [ ] No files outside `/Users/patrickstones/Desktop/SoF-Claude/` modified
- [ ] All container names use `sof-` prefix
- [ ] All Docker networks and volumes use `sof-` prefix
- [ ] No existing Docker resources on host disturbed
- [ ] All changes are local-only (no cloud references)

### Final Deployment Criteria

- [ ] All 6 Security BLOCKERs resolved
- [ ] All 12 Security MAJORs resolved
- [ ] Code Review: PASS
- [ ] Branding Review: PASS
- [ ] Security Review: PASS
- [ ] Full test suite passes (backend + frontend)
- [ ] Load test confirms 100+ concurrent user capacity
- [ ] Manual smoke test of all 6 API endpoint groups
- [ ] All 4 frontend pages render correctly with new branding
- [ ] WCAG 2.1 AA accessibility verified
- [ ] PM final sign-off

---

**END OF CONSOLIDATED PROJECT PLAN**

**Submitted to Project Manager for review and approval.**
**No code changes will be made until this plan is signed off.**
