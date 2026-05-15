# CLAUDE.md — Legal SoF (Source of Funds)

Production-track MVP for automating Source of Funds (SoF) confirmation in legal
firms. FastAPI backend + React/TypeScript frontend.

This working copy was restored from the local working version of 2026-02-28
and pushed to `https://github.com/PatAgora/LegalSoF` on 2026-05-15, replacing
the previous remote `main` (which was older and had less functionality).

---

## Layout

```
.
├── dev/archived-2026-04-14-app/   ← live application (FastAPI + React)
│   ├── backend/                   ← FastAPI app, alembic migrations, tests
│   ├── frontend/                  ← React + Vite + TypeScript
│   ├── docker/                    ← Dockerfiles
│   ├── docker-compose.yml
│   ├── docs/                      ← internal docs (handover, audit notes)
│   └── test_data/
├── SOF Demo 1/                    ← Barclays/Completion demo dataset
├── SOF Demo 2/                    ← HSBC/Santander multi-statement dataset
└── scripts/                       ← top-level helper scripts
```

The `dev/archived-2026-04-14-app/` directory name is historical — that folder
holds the active app. Renaming it (to e.g. `app/`) is a deferred clean-up; keep
the path stable until the rename is done deliberately and all references are
updated.

## Running locally

```bash
cd dev/archived-2026-04-14-app
cp .env.example .env          # then fill in real values
cp backend/.env.example backend/.env
docker compose up --build -d
```

Frontend dev server, alembic, and backend test commands are documented in
`dev/archived-2026-04-14-app/README.md` and `HANDOVER.md`.

## Branches

- `main` — current restored baseline (force-pushed 2026-05-15).
- `backup/2026-01-26-full-working-version` — earlier remote snapshot, preserved.
- `fix/pdf-verification-and-file-persistence` — earlier remote work; superseded
  by the restored local version but kept on the remote as a reference.

## Conventions

- UK English & Welsh law. GBP. DD/MM/YYYY. Tax year April–April.
- Never commit `.env` files. Templates live alongside as `.env.example`.
- No `git push`, `git commit`, or `git add` without explicit instruction.
- Before declaring a task complete: run the regression checklist; verify no 500s,
  console errors, or broken routes; confirm no secrets in any committed file.
