# TCG Partner Portal

TCG's public Partner Network and authenticated workspace support partner onboarding, product discovery, controlled documents, deal registration, commercial agreements, quoting, MAF requests, orders and commissions.

**Implementation baseline: 1 October 2026.** The public portal, four-model commercial implementation and document-based Reseller/Referral onboarding are present in source. The current verification passes 69 backend tests, Ruff, strict Mypy, frontend lint/build and mocked browser checks. Live PostgreSQL, MinIO, ClamAV, SMTP and Kubernetes acceptance have not been performed.

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
| [Partner onboarding](docs/onboarding.md) | Private uploads, Legal review, SMTP worker, ClamAV and OTP activation |
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
- Reseller/Referral document collection, assigned Legal review, durable email delivery and OTP-controlled account activation.

## Local setup

Use Python 3.12+ and Node.js 22+ with versions compatible with the installed dependencies. PostgreSQL with pgvector and MinIO are managed outside this repository; no Docker Compose setup is included. A production backend Dockerfile is provided at `backend/Dockerfile`; `deploy/kubernetes` contains backend configuration and combined API/mail-worker Deployment templates. The database must exist and the MinIO bucket must be private. Production onboarding also requires ClamAV and TLS-protected SMTP; local development may omit them with the documented limitations.

Run these commands from the repository root. Keep the existing `.env`; use `.env.example` only to create a missing file. Configure the database, storage, JWT, CORS and seed-admin settings without committing secrets. Set `SEED_ADMIN_PASSWORD` to at least 12 characters before running backend commands.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
npm.cmd --prefix frontend ci
```

Take and verify a database backup before migrating an existing installation. The root `alembic.ini` points to the backend migration directory. Start the application with three terminals, each opened at the repository root.

**Terminal 1 — database preparation, storage bootstrap and API**

```powershell
.\.venv\Scripts\Activate.ps1
alembic upgrade head
python -m app.db.seed
python -m app.storage.bootstrap
uvicorn app.main:app --reload
```

Run the commands in order. When Uvicorn starts, the API is available at `http://localhost:8000`.

**Terminal 2 — onboarding mail worker**

```powershell
.\.venv\Scripts\Activate.ps1
python -m backend.app.services.onboarding_mail
```

Keep this terminal running so queued onboarding, review and activation emails are delivered. SMTP must be configured in `.env`; without it, the worker remains idle.

**Terminal 3 — frontend development server**

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location .\frontend
npm run dev
```

Open [the public portal](http://localhost:5173), [partner sign-in](http://localhost:5173/login) or [API documentation](http://localhost:8000/docs). Authenticated users enter `/dashboard`; commercial configuration and ledgers are at `/commercial-model`.

Build the production backend image from the repository root so the Dockerfile can copy the backend package and Alembic files:

```powershell
docker build -f backend/Dockerfile -t partner-portal-api:local .
```

The image defaults to the API command. Kubernetes can reuse it for the mail worker with `python -m app.services.onboarding_mail` and for the release Job with the Alembic, seed and storage-bootstrap commands in the operations guide. The root `.dockerignore` excludes `.env`, virtual environments, dependency trees and build output.

Before applying the Kubernetes templates, replace the image and every placeholder in `deploy/kubernetes/backend-config.yaml`. Prefer creating `partner-backend-secret` through the cluster's secret manager instead of storing real credentials in the repository. Then apply the configuration and combined Deployment in the intended namespace:

```powershell
kubectl -n <namespace> apply -f deploy/kubernetes/backend-config.yaml
kubectl -n <namespace> apply -f deploy/kubernetes/clamav.yaml
kubectl -n <namespace> apply -f deploy/kubernetes/backend-deployment.yaml
```

The ClamAV manifest creates an internal `clamav:3310` Service with a pinned official scanner image and health probes. Signatures use the container filesystem and are downloaded again whenever a Pod is recreated, so startup can take several minutes.

`MINIO_ENDPOINT` is the S3 API host and port, without a URL scheme or path. Vite reads the root environment: `VITE_PROXY_TARGET` sets the development `/api` proxy target; optional `VITE_API_URL` changes the browser API base. Never place secrets in `VITE_*` variables.

The current schema head is `20261001_0006`. Seeds create roles, capabilities, countries, mcube/LVA development SKUs and the configured administrator. They do not invent catalog prices, reseller discounts or SI shares. Revision `0006` adds onboarding/Legal review and deactivates users belonging to migrated pending Reseller/Referral applications until verification completes. Review affected users, legacy opportunities and document grants before rollout; see the [operations guide](docs/Phase1-Implementation.md).

## Verification

From the repository root:

```powershell
.\.venv\Scripts\ruff.exe check backend
.\.venv\Scripts\mypy.exe backend/app --config-file backend/pyproject.toml
.\.venv\Scripts\pytest.exe backend/tests -q
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run check:widget
```

The [commercial verification guide](docs/Commercial-Implementation.md#verification) documents the earlier commercial baseline; [the onboarding guide](docs/onboarding.md#verification) documents current onboarding checks. Browser tests use mocked APIs and do not demonstrate live infrastructure readiness. `/api/v1/health/ready` checks PostgreSQL and MinIO only; monitor ClamAV, SMTP delivery and the mail worker separately.

## API conventions

Routes use `/api/v1`, UUID identifiers, UTC timestamps, ISO dates and USD decimal amounts. Protected requests use the bearer token issued by `POST /api/v1/auth/token`. Errors use an `error` object containing `code`, `message`, `details` and `request_id`; `X-Request-ID` is accepted and returned. OpenAPI is available at `/openapi.json`.

## Partner onboarding

See [the onboarding setup guide](docs/onboarding.md) for company-document uploads, admin routing, legal review, SMTP configuration, and OTP activation.

## Standalone ezextend workspace

[react-design.jsx](frontend/ezextend/react-design.jsx) now includes the local sign-in flow and the full authenticated workspace. Configure `apiBaseUrl`; `workspaceUrl` is no longer used. See [ezextend setup and synchronization](docs/ezextend.md).
