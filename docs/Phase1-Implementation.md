# Phase 1 Implementation and Operations Guide

Updated **30 September 2026** for the public portal and commercial replacement. Use [PRD.md](PRD.md) for scope, [Architecture.md](Architecture.md) for actual entities and [Commercial-Implementation.md](Commercial-Implementation.md) for commercial APIs and migration verification.

The last implementation verification could not connect to the configured application database. No live migration was applied. The instructions below are the rollout procedure, not a record that deployment has occurred.

## 1. Delivered Scope

The application provides public onboarding, multi-capability partner administration, catalog/pricing, private content, deals/pipeline, versioned commercial agreements, quotes, MAF, orders and commission records. Every new opportunity selects Direct, Reseller, Referral or System Integrator. Direct needs no external partner. Tiers are retired from active classification, pricing and document grants.

Commercial terms resolve contract → opportunity → effective partner agreement → engagement default → catalog. Quotes freeze approved economics; orders copy accepted revisions. Commission requires Won plus recorded conversion, with settlement recorded separately. `ORDER_CONFIRMED` is persisted without an external publisher.

## 2. Prerequisites and Dependencies

Use Python 3.12+ and Node.js 22+ compatible with the installed dependencies. PostgreSQL and MinIO run outside this repository. The database must exist, and the database account must be able to apply migrations and enable `vector`.

Keep the intended root `.env`; create it from `.env.example` only when missing. Verify database, MinIO, JWT, CORS and seed-admin configuration without committing credentials. Set `SEED_ADMIN_PASSWORD` to at least 12 characters before running backend commands. `MINIO_ENDPOINT` is the S3 host/port, without a scheme/path; it is not the console URL. Vite reads the root environment. `VITE_PROXY_TARGET` controls the development `/api` proxy; optional `VITE_API_URL` sets the browser API base. Never expose secrets in `VITE_*` variables.

From the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
npm.cmd --prefix frontend ci
```

## 3. Database Migration and Legacy Review

| Revision | Scope |
| --- | --- |
| `20260922_0001` | Identity, permissions, audit, seeds and pgvector |
| `20260923_0002` | Original partner/type/tier/country schema |
| `20260923_0003` | Catalog and original pricing schema |
| `20260923_0004` | Content, customers, deals, quotes, MAF, orders and events |
| `20260930_0005` | Organizations, capabilities, commercial participation/terms/contracts, snapshots, conversion and commission ledger |

Alembic must run from **backend**, which contains `alembic.ini`. To render the entire migration chain without connecting to a database, start from the repository root:

```powershell
Push-Location backend
..\.venv\Scripts\alembic.exe upgrade head --sql > ..\.venv\commercial-upgrade.sql
Pop-Location
```

Before applying to an existing installation, verify the target and take a restorable backup. From the repository root:

```powershell
Push-Location backend
..\.venv\Scripts\alembic.exe current
..\.venv\Scripts\alembic.exe upgrade head
..\.venv\Scripts\alembic.exe current
Pop-Location
```

The resulting head should be `20260930_0005`. The migration is additive and preserves partner identifiers and historical quote/order monetary snapshots. It maps organizations/capabilities, uses consistent explicit quote evidence to classify legacy opportunities and flags **all legacy opportunities** for commercial review. It does not guess the model from partner type.

Tier-scoped documents become TCG Internal pending review. Legacy tier adjustments are deactivated, and old commercial rules are not converted into approved new agreements. The migration inserts the initial 10% referral model default. Review capabilities, roles/components and document grants before new commercial actions. Downgrade intentionally refuses destructive reversal; rollback requires a verified backup restoration.

## 4. Seeds and Private Storage

After migration, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m app.db.seed
.\.venv\Scripts\python.exe -m app.storage.bootstrap
```

Editable backend installation makes `app` importable from the root. Seeds are idempotent and create roles/permissions, capability/country master data, the configured administrator, mcube/LVA and development license/implementation SKUs. They do not seed authoritative prices, reseller discounts, SI splits or new tiers.

Seed keys:

- `foundation-identity-v1`
- `phase-1a-partner-master-data-v1`
- `phase-1b-product-pricing-v1`
- `phase-1-remaining-permissions-v1`
- `phase-1-mcube-display-name-v1`
- `commercial-model-owner-v1`

Bucket bootstrap creates a missing bucket and reuses an existing one. It does not audit or replace an existing policy; the bucket must remain private.

## 5. Start and Inspect

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In another terminal at the repository root:

```powershell
npm.cmd --prefix frontend run dev
```

| Entry point | Address |
| --- | --- |
| Public portal | `http://localhost:5173` |
| Partner sign-in | `http://localhost:5173/login` |
| Workspace | `http://localhost:5173/dashboard` |
| Commercial workspace | `http://localhost:5173/commercial-model` |
| API documentation | `http://localhost:8000/docs` |
| OpenAPI | `http://localhost:8000/openapi.json` |
| Liveness / readiness | `http://localhost:8000/api/v1/health/live`, `/api/v1/health/ready` |

Readiness checks database/storage; the frontend polls it on System status. Liveness alone does not establish database availability.

## 6. Automated Verification

From the repository root:

```powershell
.\.venv\Scripts\ruff.exe check backend
.\.venv\Scripts\mypy.exe backend/app --config-file backend/pyproject.toml
.\.venv\Scripts\pytest.exe backend/tests -q
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Recorded on 30 September 2026: **55 backend tests passed**, with Ruff, strict Mypy, ESLint and frontend type/build checks passing. Browser tests use mocked APIs; SQL/API tests include isolated SQLite fixtures, which do not prove PostgreSQL concurrency behavior. Fresh/legacy migrations were additionally executed in isolated PGlite PostgreSQL with pgvector omitted only for that harness.

Optional browser/migration dependencies and commands are documented in [Commercial-Implementation.md](Commercial-Implementation.md#verification). Use an installed Microsoft Edge browser and a running Vite server. Tests make no live payout, provisioning or email calls. Live PostgreSQL/MinIO smoke testing remains necessary.

## 7. Live Acceptance Smoke Test

Use a test environment and approved test data. Do not treat illustrative amounts as contractual defaults.

### Foundation and partner access

1. Verify liveness and database/storage readiness; sign in with the configured seed administrator.
2. Submit a public application requesting more than one capability; confirm only successful submission shows a reference.
3. Review/approve it as TCG Admin without tier assignment. Create Partner Sales and read-only users.
4. Verify another partner cannot read/change its resources by ID; verify suspension and account-switch cache clearing.

### Catalog, organization and terms

1. Configure an effective USD price on an active SKU and confirm its product owner.
2. Reuse an existing organization where it has multiple profiles; add explicit partner/vendor agreements as needed.
3. Draft/approve commercial terms using their intended scope and effective dates. Verify explicit zero is preserved and equal-specificity overlaps fail.
4. Preview pricing with the selected engagement model. Confirm there is no tier, automatic reseller discount or SI markup in resolution.
5. Review every migrated opportunity through Commercial model → Migration review before new quote activity.

### Four-model quote and order journeys

1. Create an opportunity for each model with valid participants, grants, scoped roles and components. Direct must work without a partner. Submit/approve each.
2. Verify same-customer/product protection conflict and 90-day expiry. Check stage-history and Won/Lost required fields.
3. Create quotes; SI must reference its draft TCG selling contract. Add SKU lines and finalize as TCG. Verify frozen terms/source versions.
4. Change a draft line's source price and confirm finalization requires removing/re-adding stale lines. Verify finalized historical revisions stay unchanged.
5. Have the reseller buyer accept wholesale. Verify TCG Admin cannot accept for it. Test SI buyer acceptance and TCG external-customer acceptance for Direct/Referral.
6. Create one order from each accepted quote using the authorized execution party. Upload commitment with kind `PURCHASE_ORDER`, submit, review/return, confirm, provision and activate.
7. Verify the copied accepted revision, status history and durable `ORDER_CONFIRMED` event. No external project should be assumed.

### Economics and commission

1. Confirm private reseller selling price produces an undisclosed margin, not zero; disclosed negative gross margin remains valid.
2. Exercise SI fixed, named-pool and component methods; check residual rounding, explicit vendor deductions and the whole-project majority warning.
3. Configure explicit referral eligibility and treatment rules. Verify 10% default and an approved 0% override, while forecast remains separate from accrual.
4. Mark a qualifying deal Won and record conversion against its agreed current Final/Accepted snapshot with actual eligible revenue. Verify retry creates no duplicate accrual and a Lost deal cannot accrue.
5. Under the agreed settlement policy, record referenced adjustments/payments; verify duplicate references, stale ledger state and overpayment are rejected. No money is transferred by these actions.
6. Verify referral users cannot view customer bids/orders, private vendor documents or other participants' entitlements.

### Documents, MAF and audit

1. Publish All Partners and TCG Internal documents; test authorized download, denial and version/checksum metadata. Use the API for capability/specific-partner scopes and new versions.
2. Verify broad library scope cannot expose linked private vendor/contract documents or unauthorized workflow attachments.
3. Create MAF for a real participating partner on an approved deal. Review, upload `ISSUED_DOCUMENT`, issue and verify protected download/90-day expiry.
4. Inspect audit records for partner, term, structure, deal, quote, MAF, order and commission actions, including actor and request context.

## 8. Operational Boundaries

Amounts remain USD; accepted snapshots never recalculate from new prices. Files must be nonempty and at most 25 MB; download links expire after ten minutes. There is no file malware scanner, scheduled expiry, external event publisher, automated payout or provisioning integration. The dashboard sums latest stored commercial snapshots per opportunity as operational forecasts, not booked revenue.

## 9. Troubleshooting

| Symptom | Check |
| --- | --- |
| Database connection refused | Configured service/host/port is reachable; confirm the intended target before retrying. |
| Database does not exist | Provision the named database or correct configuration before Alembic. |
| Alembic cannot find configuration | Run from `backend` using the root virtual environment. |
| MinIO readiness failure | S3 endpoint, credentials, TLS setting and private bucket existence; console port is not the API endpoint. |
| Empty/missing resolved pricing | Active SKU, effective catalog price, engagement model, partner eligibility and approved term dates. No authoritative prices are seeded. |
| HTTP 403 | User permission, active partner/capability, participation grant and legal contracting party; a valid ID is insufficient. |
| Commercial review/version conflict | Resolve legacy structure/reapproval or reload current version before editing. |
| Stale quote pricing | Remove/re-add affected draft lines, then finalize against current approved sources. |
| Quote cannot finalize | Approved/reviewed deal, TCG selling contract, valid scoped roles/components, approved terms and explicit compensation eligibility. |
| Order cannot submit | Accepted quote, execution permission and attachment kind `PURCHASE_ORDER`. |
| MAF cannot issue | Approved request and attachment kind `ISSUED_DOCUMENT`. |
| No commission accrual | Won plus recorded conversion, agreed snapshot and actual eligible basis are all required. |

## 10. Known Acceptance Refinements

[PRD Section 24](PRD.md#24-known-acceptance-refinements) is the maintained list. It includes general deal editing, customer administration/deduplication, fuller document and attachment UI, guided forms, expiry scheduling, quote thresholds and future external integrations. Public testimonials remain illustrative until approved real endorsements are supplied.
