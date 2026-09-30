# TCG Partner Portal

TCG's public Partner Network and authenticated workspace support partner onboarding, product discovery, controlled documents, deal registration, commercial agreements, quoting, MAF requests, orders and commissions.

**Implementation baseline: 30 September 2026.** The public portal and four-model commercial implementation are present in source. The last verification passed 55 backend tests, static checks, production build, browser checks and isolated PostgreSQL migration tests. The configured application database refused connections during that verification; live migration and environment acceptance were not performed.

## Documentation

| Document | Purpose |
| --- | --- |
| [Product requirements](docs/PRD.md) | Delivered scope, contractual inputs and known acceptance gaps |
| [Commercial model](docs/Commercial-Model.md) | Authoritative Direct, Reseller, Referral and SI business decisions |
| [Business rules](docs/Rules.md) | Current workflow, pricing and authorization rules |
| [Architecture](docs/Architecture.md) | Actual code structure, persistence and access boundaries |
| [UX design](docs/Design.md) | Public and authenticated routes, screens and interactions |
| [Public portal](docs/Partner-Portal-UI.md) | Visual identity, registration and illustrative content |
| [Operations guide](docs/Phase1-Implementation.md) | Setup, migrations, seeds, smoke tests and troubleshooting |
| [Commercial implementation](docs/Commercial-Implementation.md) | Commercial APIs, migration compatibility and verification harnesses |
| [Decision log](docs/Memory.md) | Current decisions and superseded assumptions |
| [Delivery phases](docs/Phases.md) | Implemented milestones and deferred work |

## Implemented capabilities

- Responsive public landing, partnership paths, product/solution highlights, illustrative partner stories and a three-step application.
- Partner approval, profiles, users and multiple capabilities: Reseller, Referral and System Integrator. There are no active partner tiers.
- Explicit Direct, Reseller, Referral or System Integrator classification on each opportunity; shared organization identities, participants, responsibilities and solution components.
- Effective USD catalog prices and approved commercial terms, with separate customer value, TCG entitlement, partner benefit, vendor obligations and commission expense.
- Private documents, protected deals, pipeline history, immutable finalized quote revisions, contracting-party acceptance, MAF issuance and quote-based orders.
- Referral forecasts, conversion-qualified accruals, append-only adjustments and recorded payments. Referral defaults to 10% of explicitly eligible revenue; actual eligibility and settlement policies must be configured.
- Versioned migration, legacy review queue, backend authorization, audit records and a durable `ORDER_CONFIRMED` integration event.

## Local setup

Use Python 3.12+ and Node.js 22+ with versions compatible with the installed dependencies. PostgreSQL with pgvector and MinIO are managed outside this repository; no Docker Compose setup is included. The database must exist and the MinIO bucket must be private.

Run these commands from the repository root. Keep the existing `.env`; use `.env.example` only to create a missing file. Configure the database, storage, JWT, CORS and seed-admin settings without committing secrets. Set `SEED_ADMIN_PASSWORD` to at least 12 characters before running backend commands.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
npm.cmd --prefix frontend ci
```

Take and verify a database backup before migrating an existing installation. Alembic commands run from **backend**, where `alembic.ini` and the migration directory reside:

```powershell
Push-Location backend
..\.venv\Scripts\alembic.exe current
..\.venv\Scripts\alembic.exe upgrade head
..\.venv\Scripts\python.exe -m app.db.seed
Pop-Location
.\.venv\Scripts\python.exe -m app.storage.bootstrap
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In another terminal at the repository root:

```powershell
npm.cmd --prefix frontend run dev
```

Open [the public portal](http://localhost:5173), [partner sign-in](http://localhost:5173/login) or [API documentation](http://localhost:8000/docs). Authenticated users enter `/dashboard`; commercial configuration and ledgers are at `/commercial-model`.

`MINIO_ENDPOINT` is the S3 API host and port, without a URL scheme or path. Vite reads the root environment: `VITE_PROXY_TARGET` sets the development `/api` proxy target; optional `VITE_API_URL` changes the browser API base. Never place secrets in `VITE_*` variables.

The current schema head is `20260930_0005`. Seeds create roles, capabilities, countries, mcube/LVA development SKUs and the configured administrator. They do not invent catalog prices, reseller discounts or SI shares. The commercial migration inserts the initial 10% referral default. Review legacy opportunities and document grants before new commercial work; see the [operations guide](docs/Phase1-Implementation.md).

## Verification

From the repository root:

```powershell
.\.venv\Scripts\ruff.exe check backend
.\.venv\Scripts\mypy.exe backend/app --config-file backend/pyproject.toml
.\.venv\Scripts\pytest.exe backend/tests -q
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

The [commercial verification guide](docs/Commercial-Implementation.md#verification) documents browser and disposable PostgreSQL migration checks. Browser tests use mocked APIs; they do not demonstrate live infrastructure readiness. Check `/api/v1/health/live` and `/api/v1/health/ready` when running against real services.

## API conventions

Routes use `/api/v1`, UUID identifiers, UTC timestamps, ISO dates and USD decimal amounts. Protected requests use the bearer token issued by `POST /api/v1/auth/token`. Errors use an `error` object containing `code`, `message`, `details` and `request_id`; `X-Request-ID` is accepted and returned. OpenAPI is available at `/openapi.json`.
