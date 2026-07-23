# AI Tax Optimizer (India)

An implementation of [`AI-Tax-Optimizer-India-Architecture.md`](./AI-Tax-Optimizer-India-Architecture.md).
This repository realizes the **highest-priority, de-risking core** of that 17-week
blueprint: the deterministic, versioned **tax calculation engine** (§5), the tax
API (§4), auth + profile (§8), a rule-based optimizer, and a React/TypeScript UI —
all runnable locally today.

> **Disclaimer.** Informational only, not tax or financial advice. Tax rules change
> with every Union Budget — verify against the current Finance Act and consult a
> qualified professional before filing.

## What's implemented

| Blueprint section | Status | Notes |
|---|---|---|
| §5 Tax engine | ✅ | Pure/deterministic, old+new regime, §87A rebate, surcharge + **marginal relief**, cess, capital gains at special rates excluded from rebate. Versioned YAML rate tables for **AY 2025-26 & 2026-27**. |
| §4 Tax API | ✅ | `/tax/calculate`, `/tax/compare`, `/tax/simulate`, `/tax/capital-gains`, `/tax/computations` history. |
| §4 Optimizer | ✅ | Rule-based, ranked, savings quantified by re-running the engine (not guessed). Stateless endpoint **plus** persisted recommendations with accept/dismiss. |
| §8 Auth & RBAC | ✅ | Register/login/refresh/me, JWT, bcrypt, role guard, per-user data scoping. |
| §4 Profile & finances | ✅ | Profile + CRUD for all six heads: income, deductions, investments, loans, insurance, capital gains. |
| §4 Dashboard | ✅ | `/dashboard/summary` aggregates stored data through the engine; `/dashboard/forecast` projects growth onto the next AY. |
| §2.2 Hexagonal design | ✅ | Domain is framework-free; ports defined in `domain/ports`. |
| §9.2 Frontend | ✅ | Feature-folder SPA: auth gate, dashboard, finances CRUD, strategies, calculator, profile. |
| §5 Golden-file tests | ✅ | 12 engine + 6 API + 15 finances/dashboard cases — **33 passing**. |
| §3 Full ERD | 🟡 partial | All financial tables + recommendations. `DOCUMENT`/`EXTRACTED_FIELD` (Phase 3) and `CHAT_*`/`CITATION` (Phase 4) not yet modelled. `ROLE` is denormalised onto `users.role`. |
| §3 Alembic migrations | ✅ | Baseline migration for all 10 tables; app boots via `alembic upgrade head`. Tests still use `create_all` (fast, always-fresh). See *Schema changes* below. |
| §6 Agent · §7 RAG · Docs AI · Celery · IaC | ⛔ scoped out | Ports/contracts stubbed so adapters drop in without domain changes. |

## Run it locally

**Backend** (Python 3.11+):
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload            # http://127.0.0.1:8000/docs
pytest -q                                # 33 tests
```

**Frontend** (Node 18+):
```bash
cd frontend
npm install
npm run dev                              # http://127.0.0.1:5173 (proxies /api → :8000)
```

**Or the whole stack** (Postgres + Redis + Qdrant + apps):
```bash
docker compose up --build
```

## The engine is the point (§5)

All tax math is code, never the LLM. Rates live in
[`backend/app/config/tax_rules/*.yaml`](./backend/app/config/tax_rules) keyed by
assessment year — a new Budget is a **data change plus a golden-file test**, not an
engine change. `TAX_COMPUTATION.rules_version` pins the exact table used, so every
past computation is reproducible after the rules move.

Try it:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/tax/compare -H "Content-Type: application/json" -d '{
  "assessment_year": 2026, "regime": "new",
  "income": {"salary_gross": 1800000, "other": 25000},
  "deductions": {"80C": 150000, "80CCD1B": 50000, "80D": 25000},
  "tds_paid": 210000
}'
```

## The dashboard is a view of the engine, not a second implementation

`/dashboard/summary` does not re-derive any tax math. It reads your stored
financial heads, assembles them into the same domain `TaxInput` the calculator
uses ([`application/use_cases/assemble_tax_input.py`](./backend/app/application/use_cases/assemble_tax_input.py)),
and runs the one engine. A test asserts the two agree to the rupee, so the
dashboard cannot silently drift from the calculator.

Deductions for the same section **sum across heads** — an 80C ELSS investment
plus an 80C life premium plus a direct 80C row — and the engine then applies the
statutory cap, recording the trail (`"150000 (capped from 220000)"`). The
assembly layer never second-guesses the law.

## Layout
```
backend/   FastAPI, clean/hexagonal architecture (§9.1)
  app/domain/        pure entities, tax engine, optimizer, ports  ← no framework imports
  app/application/   Pydantic DTOs + use cases (stored rows → TaxInput)
  app/infrastructure/db  SQLAlchemy models + session
  app/api/v1/        routers + auth/RBAC deps
  app/config/tax_rules/  versioned YAML rate tables
  tests/             golden-file + API + finances/dashboard tests
frontend/  React + TS + Tailwind + Vite (§9.2)
  src/app/           shell, hash router, auth gate
  src/features/      auth · dashboard · finances · optimizer · calculator · profile
  src/components/ui/ Tailwind primitives
  src/lib/           api client, token storage
  src/store/         session context
```

## Schema changes

The app runs `alembic upgrade head` on startup (`run_migrations()`), so a new
column ALTERs onto an existing database instead of being silently skipped. To
add one: edit the model, then autogenerate and apply the migration —

```bash
cd backend
alembic revision --autogenerate -m "add income_sources.tds_paid"
alembic upgrade head        # or just restart the app
```

`env.py` takes the URL from the same `Settings` the app uses, and `render_as_batch`
is on so migrations authored on SQLite still apply on Postgres. The test suite
bypasses all this and builds the schema with `create_all` — fast and always
fresh, so no migration state leaks between runs.

## Next phases (per §13 roadmap)
Document AI (OCR → LLM extraction), RAG assistant (section-aware chunking + hybrid
retrieval + LangChain agent with the engine as a tool), Celery workers, reports,
and cloud IaC. The ports in `domain/ports` fix their contracts in advance.

Both remaining AI phases need credentials this repo does not have — an LLM API
key, an OCR provider, and a vector DB. They can be written against the ports,
but nothing about them can be *verified* locally until those exist. Alembic
migrations and the `ROLE` table (for §8's permission-based
`require_permission(...)`) are the next pieces that need no external service.
