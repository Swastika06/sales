# Phase 1 Implementation and Operations Guide

Updated **1 October 2026** for the public portal, commercial replacement and document-based partner onboarding. Use [PRD.md](PRD.md) for scope, [Architecture.md](Architecture.md) for actual entities, [Commercial-Implementation.md](Commercial-Implementation.md) for commercial APIs and migration verification, and [onboarding.md](onboarding.md) for the detailed applicant/Legal workflow.

The last implementation verification could not connect to the configured application database. No live migration was applied. The instructions below are the rollout procedure, not a record that deployment has occurred.

## 1. Delivered Scope

The application provides public onboarding, multi-capability partner administration, catalog/pricing, private content, deals/pipeline, versioned commercial agreements, quotes, MAF, orders and commission records. Reseller and Referral applicants upload company, PAN and GSTIN documents for assigned Legal review, then activate through an emailed OTP. Every new opportunity selects Direct, Reseller, Referral or System Integrator. Direct needs no external partner. Tiers are retired from active classification, pricing and document grants.

Commercial terms resolve contract → opportunity → effective partner agreement → engagement default → catalog. Quotes freeze approved economics; orders copy accepted revisions. Commission requires Won plus recorded conversion, with settlement recorded separately. `ORDER_CONFIRMED` is persisted without an external publisher.

## 2. Prerequisites and Dependencies

Use Python 3.12+ and Node.js 22+ compatible with the installed dependencies. PostgreSQL and MinIO run outside this repository. The database must exist, and the database account must be able to apply migrations and enable `vector`. Local development and production require a reachable ClamAV daemon supporting INSTREAM on TCP 3310. Production onboarding also requires a TLS-enabled SMTP service and a continuously running onboarding mail worker.

Keep the intended root `.env`; create it from `.env.example` only when missing. Verify database, MinIO, JWT, CORS, seed-admin, portal URL, SMTP and ClamAV configuration without committing credentials. Local development uses `CLAMAV_HOST=localhost` and `CLAMAV_PORT=3310`; the API rejects an empty scanner host and document uploads fail if the daemon cannot be reached. Set `SEED_ADMIN_PASSWORD` to at least 12 characters and keep `JWT_SECRET_KEY` stable while onboarding mail is pending because it encrypts queued payloads. Production requires an HTTPS `PUBLIC_PORTAL_URL`, TLS-enabled SMTP and a reachable `CLAMAV_HOST`. `MINIO_ENDPOINT` is the S3 host/port, without a scheme/path; it is not the console URL. Presigned downloads use that endpoint, so it must resolve in applicant/admin browsers as well as from the API. Vite reads the root environment. `VITE_PROXY_TARGET` controls the development `/api` proxy; optional `VITE_API_URL` sets the browser API base. Never expose secrets in `VITE_*` variables.

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
| `20261001_0006` | Private onboarding documents, Legal review, OTP activation, durable mail and rate limits |

The root `alembic.ini` resolves the backend migration directory. To render the entire migration chain without connecting to a database, start from the repository root:

```powershell
.\.venv\Scripts\alembic.exe upgrade head --sql > .\.venv\full-upgrade.sql
```

Before applying to an existing installation, verify the target and take a restorable backup. From the repository root:

```powershell
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
```

The resulting head should be `20261001_0006`. Revision `0005` is additive and preserves partner identifiers and historical quote/order monetary snapshots. It maps organizations/capabilities, uses consistent explicit quote evidence to classify legacy opportunities and flags **all legacy opportunities** for commercial review. It does not guess the model from partner type.

Revision `0006` creates draft onboarding applications for existing pending Reseller/Referral partners that have a matching primary-contact user, then deactivates users belonging to those applications. Existing active partners are preserved. Review the affected partners and communicate the new document/verification step before rollout. The onboarding migration refuses downgrade because it holds review and verification records; rollback requires restoring the verified backup.

Tier-scoped documents become TCG Internal pending review. Legacy tier adjustments are deactivated, and old commercial rules are not converted into approved new agreements. The migration inserts the initial 10% referral model default. Review capabilities, roles/components and document grants before new commercial actions. Downgrade intentionally refuses destructive reversal; rollback requires a verified backup restoration.

## 4. Seeds, Private Storage and Delivery Services

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

All onboarding document uploads require ClamAV. The API streams each file to the configured daemon before writing it to MinIO and fails closed if the scanner is unavailable. Production activation email requires a separate worker process using the same database, JWT and SMTP settings as the API:

```powershell
.\.venv\Scripts\python.exe -m app.services.onboarding_mail
```

The worker polls the PostgreSQL outbox, retries transient failures and uses row locking so multiple replicas do not process the same row concurrently. SMTP delivery is at least once; monitor failed outbox rows and retain the JWT secret while encrypted payloads are pending.

## 5. Start and Inspect

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

For an end-to-end onboarding run, start ClamAV first and run the mail worker in another terminal. Local development expects ClamAV at `localhost:3310`; the API refuses an empty `CLAMAV_HOST`, and uploads fail closed if the daemon is unavailable. Production additionally refuses to start without secure SMTP configuration.

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

Readiness checks database/storage; the frontend polls it on System status. It does not check ClamAV, SMTP or the mail-worker process, so those dependencies require separate monitoring. Liveness alone does not establish dependency availability.

## 6. Automated Verification

From the repository root:

```powershell
.\.venv\Scripts\ruff.exe check backend
.\.venv\Scripts\mypy.exe backend/app --config-file backend/pyproject.toml
.\.venv\Scripts\pytest.exe backend/tests -q
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Recorded on 1 October 2026: **69 backend tests passed**, with Ruff, strict Mypy, ESLint, frontend type/build, onboarding browser checks and standalone workspace checks passing. Browser tests use mocked APIs; SQL/API tests include isolated SQLite fixtures, which do not prove PostgreSQL concurrency or live ClamAV/SMTP behavior. The earlier commercial migration chain was executed in isolated PGlite PostgreSQL with pgvector omitted only for that harness; revision `0006` still requires target-PostgreSQL acceptance.

Optional browser/migration dependencies and commands are documented in [Commercial-Implementation.md](Commercial-Implementation.md#verification). Use an installed Microsoft Edge browser and a running Vite server. Tests make no live payout, provisioning or email calls. Live PostgreSQL/MinIO smoke testing remains necessary.

## 7. Live Acceptance Smoke Test

Use a test environment and approved test data. Do not treat illustrative amounts as contractual defaults.

### Foundation and partner access

1. Verify liveness and database/storage readiness; sign in with the configured seed administrator.
2. Submit a Reseller/Referral application with valid company-license, PAN and GSTIN files; confirm signature checks, clean ClamAV status and private MinIO keys.
3. Resume the draft with applicant credentials, replace one document, submit it, route it as TCG Admin and review it through a separately authenticated Legal account.
4. Exercise request-changes/resubmission, rejection and approval. Confirm the mail worker delivers the current OTP, expired/incorrect/replayed codes fail, and successful verification activates only the applicant.
5. Verify admin approval/status endpoints and normal login cannot bypass incomplete onboarding. Verify another partner cannot read/change resources by ID, then check suspension and account-switch cache clearing.

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

## 8. Kubernetes Production Layout

The production image is built from the repository root with `docker build -f backend/Dockerfile -t <registry>/partner-portal-api:<tag> .`. One image serves the API, mail worker and migration Job. `deploy/kubernetes/backend-config.yaml` provides ConfigMap/Secret placeholders, `deploy/kubernetes/backend-deployment.yaml` runs the API and mail worker as separate containers in one Pod, and `deploy/kubernetes/clamav.yaml` provides the scanner Deployment and internal Service. ClamAV signatures are ephemeral and refresh whenever its Pod starts. API-Service, migration-Job and Ingress definitions remain to be added. A production release comprises these workloads:

| Definition | Responsibility | Important configuration |
| --- | --- | --- |
| API `Deployment` + `ClusterIP Service` | Runs Uvicorn/FastAPI and handles uploads | Application Secret, port 8000, live/ready probes, trusted proxy headers |
| Mail-worker `Deployment` | Runs `python -m app.services.onboarding_mail` continuously | Same image, database, JWT and SMTP Secret as the API; no public Service |
| Migration `Job` | Runs `alembic upgrade head`, seeds and bucket bootstrap once per release | Same image/config; complete before the API/worker rollout |
| ClamAV `Deployment` + `ClusterIP Service` | Exposes INSTREAM scanning to API Pods on TCP 3310 | Keep internal, update signatures, add startup/readiness checks and suitable memory |

PostgreSQL and MinIO may be managed services or stateful in-cluster workloads with tested persistent volumes and backups. MinIO's presigned-download hostname must be browser reachable. SMTP normally remains an external or shared internal service.

Route `/api` on the portal hostname to the API Service while preserving `/api/v1/...`. Permit at least 12 MB request bodies because onboarding accepts a 10 MB file plus multipart overhead. Use a request timeout long enough for upload, ClamAV scanning and MinIO storage; the frontend currently defaults to 15 seconds. Configure Uvicorn to trust only the Ingress proxy addresses so database-backed IP rate limits see applicant addresses rather than a single proxy address.

Release in this order: build/push the image, back up PostgreSQL, ensure PostgreSQL/MinIO/ClamAV/SMTP are reachable, run the versioned migration Job, inspect its logs and schema head, roll out the API, then roll out the mail worker. Verify `/health/live`, `/health/ready`, a real clean/malicious-file scan path, SMTP delivery, OTP activation and a presigned browser download.

## 9. Operational Boundaries

Amounts remain USD; accepted snapshots never recalculate from new prices. Shared-library/workflow files must be nonempty and at most 25 MB; onboarding documents are limited to 10 MB and require a clean ClamAV result in every runtime environment. Download links expire after ten minutes. There is no scheduled expiry worker, external event publisher, automated payout or provisioning integration. The dashboard sums latest stored commercial snapshots per opportunity as operational forecasts, not booked revenue.

## 10. Troubleshooting

| Symptom | Check |
| --- | --- |
| Database connection refused | Configured service/host/port is reachable; confirm the intended target before retrying. |
| Database does not exist | Provision the named database or correct configuration before Alembic. |
| Alembic cannot find configuration | Run from the repository root using the root `alembic.ini`, or from `backend` using its local configuration. |
| MinIO readiness failure | S3 endpoint, credentials, TLS setting and private bucket existence; console port is not the API endpoint. |
| Browser cannot open a download URL | `MINIO_ENDPOINT` in the presigned URL must be resolvable and trusted by the browser, not only by cluster DNS. |
| Upload returns 413 | Increase the Ingress request-body limit above the 10 MB application limit to allow multipart overhead. |
| Upload returns scanner 503 | `CLAMAV_HOST`/port, Service connectivity, daemon readiness and virus-signature availability. Local development and production fail closed. |
| Activation email remains queued | Mail-worker Pod, SMTP/TLS/authentication settings and pending/failed `onboarding_mail` rows. `/health/ready` does not cover these. |
| Applicants share rate limits | Configure trusted forwarded headers so the API sees the client address instead of the Ingress address. |
| Empty/missing resolved pricing | Active SKU, effective catalog price, engagement model, partner eligibility and approved term dates. No authoritative prices are seeded. |
| HTTP 403 | User permission, active partner/capability, participation grant and legal contracting party; a valid ID is insufficient. |
| Commercial review/version conflict | Resolve legacy structure/reapproval or reload current version before editing. |
| Stale quote pricing | Remove/re-add affected draft lines, then finalize against current approved sources. |
| Quote cannot finalize | Approved/reviewed deal, TCG selling contract, valid scoped roles/components, approved terms and explicit compensation eligibility. |
| Order cannot submit | Accepted quote, execution permission and attachment kind `PURCHASE_ORDER`. |
| MAF cannot issue | Approved request and attachment kind `ISSUED_DOCUMENT`. |
| No commission accrual | Won plus recorded conversion, agreed snapshot and actual eligible basis are all required. |

## 11. Known Acceptance Refinements

[PRD Section 24](PRD.md#24-known-acceptance-refinements) is the maintained list. It includes general deal editing, customer administration/deduplication, fuller document and attachment UI, guided forms, expiry scheduling, quote thresholds and future external integrations. Public testimonials remain illustrative until approved real endorsements are supplied.
