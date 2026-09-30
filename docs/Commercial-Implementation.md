# Commercial model implementation

Implemented against `Commercial-Model.md` on 30 September 2026. Database deployment is separate from the source implementation. The configured local database refused connections during the implementation verification on that date; no application database was migrated and `.env` was not changed.

## Delivered behavior

- Opportunities explicitly select Direct, Reseller, Referral or System Integrator. Direct has no required external partner. Organizations can hold customer, partner and vendor profiles; approved partners can have several capabilities.
- Explicit opportunity membership controls progress and commercial visibility. Capability alone grants no deal access. Quotes and orders also require the appropriate contracting party. Referral users see their submission, progress, own forecast and commission ledger, while customer quote/order execution remains with TCG. Linked vendor documents remain internal. Signing out clears cached organizational data.
- The commercial workspace at `/commercial-model` provides participants, scoped roles, product/service components, organizations, agreements, vendor obligations, contracts, versioned terms, previews, snapshots, conversion evidence, payments, adjustments and migration review. The dashboard separates customer, TCG, partner, vendor and commission amounts.
- Reseller wholesale pricing is independent of customer selling price. Undisclosed margin and partner benefit remain null. Negative gross margin is allowed. Referral allocations on reseller transactions are rejected.
- Referral defaults to 10%, supports explicit 0–100% overrides, and requires an explicit component scope, amount and treatment of discounts, taxes, vendor charges, credits and refunds at finalization. Forecasts remain separate from accrual. Accrual requires both WON and recorded conversion, uses actual eligible revenue with frozen terms, and is idempotent by opportunity conversion/beneficiary.
- SI supports fixed mcube, named-pool percentage and component allocations. Half-up decimal rounding reconciles to the named residual beneficiary. Explicit vendor deductions apply once. The SI share of the whole project is displayed and flagged when it is not the majority. There is no automatic markup or invented split.
- Direct defaults to the full applicable customer amount for TCG, with separate vendor obligations. Partner compensation requires an associated beneficiary, explicit eligibility/rate and approved terms.
- Terms resolve contract → opportunity → partner agreement → model default → catalog, with parameter sources retained. Equal-specificity overlapping terms are rejected. Fixed prices replace catalog prices; discounts do not compound. Draft items with changed prices/sources cannot be finalized until refreshed.
- Finalized quotes freeze commercial inputs, roles, costs, allocations and source versions. Orders copy the accepted quote revision. Approved commercial changes require reapproval; accepted structures require an amendment reason and accepted contract terms require a replacement agreement. PostgreSQL triggers protect snapshots, revisions, conversion evidence and commission ledger rows from mutation.
- Tier selectors, registration assignment, active pricing rules and API configuration have been retired. Historical tier tables and references remain for audit; they are excluded from all new price resolution.

## Implementation map

| Area | Location |
| --- | --- |
| Decimal calculator and term precedence | `backend/app/domain/commercial.py` |
| Validated API inputs | `backend/app/schemas/commercial.py` |
| Organization, participation, terms, snapshot and ledger persistence | `backend/app/models/commercial.py` |
| Resolution, engagement validation, snapshot and accrual services | `backend/app/services/commercial.py` |
| Membership and contracting-party authorization | `backend/app/services/commercial_access.py` |
| Commercial administration and reporting API | `/api/v1/commercial` |
| Workspace | `frontend/src/pages/CommercialModelPage.tsx`, `frontend/src/features/commercial/` |
| Additive migration | `backend/alembic/versions/20260930_0005_commercial_model.py`; revision `20260930_0005` |

`partners` remains the partner-profile table to preserve its existing identifiers. Allocation definitions are stored in validated versioned term JSON; computed allocations are persisted in immutable snapshots. Accepted contract economics are represented by their accepted quote and immutable quote revision. These avoid parallel mutable financial totals.

## API and client compatibility

Commercial routes are under `/api/v1/commercial`. OpenAPI at `/docs` describes the validated request bodies. TCG-only reads and administration are distinct from partner-filtered snapshot and commission views.

| Method and relative route | Purpose |
| --- | --- |
| `POST /calculate` | TCG calculation/validation without saving an agreement |
| `GET /organizations`, `POST /organizations` | List identities; TCG Admin creates/reuses identified organizations |
| `POST /vendors` | Create an independent vendor profile |
| `GET /agreements` | TCG Admin reads partner/vendor agreements and vendor profiles |
| `POST /partner-agreements`, `POST /vendor-agreements` | Create effective agreements |
| `GET /migration-review` | TCG list of opportunities requiring classification/structure review |
| `GET /opportunities/{opportunity_id}` | Read full internal structure or the requesting partner's limited participation |
| `PUT /opportunities/{opportunity_id}` | TCG sales configuration using `expected_version` and any required amendment reason |
| `POST /opportunities/{opportunity_id}/preview` | TCG preview from approved resolved terms |
| `POST /opportunities/{opportunity_id}/vendors` | Link an explicit vendor obligation/payer |
| `POST /contracts` | Create a draft selling contract |
| `GET /terms`, `POST /terms`, `POST /terms/{term_id}/approve` | TCG Admin manages effective versioned terms |
| `GET /opportunities/{opportunity_id}/snapshots` | Read immutable history; partner response exposes own entitlement only |
| `POST /opportunities/{opportunity_id}/conversion` | TCG records evidence and actual eligibility against the agreed snapshot |
| `GET /commissions` | Internal or beneficiary-filtered accrual/adjustment/payment balances |
| `POST /commissions/{accrual_id}/adjustments`, `POST /commissions/{accrual_id}/payments` | TCG Admin appends referenced settlement records |
| `GET /summary` | TCG operational totals from each opportunity's latest stored snapshot |

Existing client contracts changed:

- Partner registration/create/update uses `capability_codes`. Registration options still name the capability catalog `partner_types`; legacy `partner_type_code` input and the primary-type response remain for compatibility. Tier fields/options are removed. Partner approval sends an empty object `{}`.
- Deal creation requires `engagement_model`; Direct permits no `partner_id`. Quote creation inherits the deal model and optionally takes `contract_id`, which is required for SI. Quote/order responses can have null primary partner IDs.
- `GET /api/v1/pricing/resolved` requires `engagement_model`, with optional `partner_id` and `as_of`. Partner users can access their own Reseller/SI pricing; Direct/Referral customer pricing remains with TCG. Old tier/type adjustment and override configuration endpoints are retired.
- `PARTNER_TYPE` document scope matches approved capabilities. New `PARTNER_TIER` input is invalid; do not drop its filter to make old documents public.
- Version conflicts and stale commercial/price sources reject changes. Reload current state or refresh draft quote lines rather than overwriting accepted history.

Snapshot totals are operational measures, not booked accounting revenue. Contract acceptance does not automatically record conversion; use the conversion endpoint before expecting qualifying commission. Recording a payment does not invoke a payment provider.

## Start using the implementation

1. Start the PostgreSQL and MinIO services configured in the existing `.env`. Take and verify a database backup before applying the migration to an existing installation.
2. From the repository root, install backend dependencies with `.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"`.
3. From `backend`, run `..\.venv\Scripts\alembic.exe upgrade head`, then `..\.venv\Scripts\python.exe -m app.db.seed`. Restart the API and frontend as described in the README.
4. Sign in as TCG Admin. Review partner capabilities and open **Commercial model → Migration review**. Legacy classification uses explicit quote evidence, never partner type alone. All legacy opportunities require review of their roles/components before new commercial actions. Existing accepted quote/order totals are retained.
5. Register a deal with its engagement model. Configure participants, roles and components; create SI contracting parties and relevant vendor agreements. Draft and approve applicable commercial terms, then submit/reapprove the opportunity.
6. Create and finalize the quote in **Quote to order**. Resellers accept their wholesale quote; SI acceptance follows the contracting buyer; TCG records external customer acceptance for Direct/Referral. Use the accepted quote to create an order.
7. For compensation, mark the opportunity won and record verifiable customer/project conversion against the agreed snapshot, including actual eligible revenue. Record payments or referenced adjustments separately under the agreed settlement policy.

Tier-scoped documents are migrated to TCG Internal pending review. Legacy ambiguous pricing is not silently converted. The migration intentionally refuses destructive downgrade; restore a verified backup if rollback is required.

## Verification

Recorded baseline on **30 September 2026**: 55 backend tests passed; Ruff, strict Mypy, frontend TypeScript/production build and ESLint passed. These results describe implementation verification, not a fresh live-environment acceptance run.

- Backend calculator and isolated SQL/API tests cover the acceptance examples, zero overrides, missing eligibility, SI rounding and majority review, deductions, term overlaps, stale versions/prices, Direct quote-to-order, reseller/SI buyer acceptance, referral conversion retries, lost referrals, payments/adjustments, amendments, document/attachment denial and null-partner isolation.
- Isolated SQL/API tests use SQLite fixtures; they do not establish PostgreSQL locking/concurrency behavior.
- PostgreSQL migration execution was verified using an isolated PGlite PostgreSQL engine for both fresh installation and an upgrade with legacy tier-bearing data. Assertions check historical totals/snapshots, capability mapping, review flags, restricted document visibility and immutable history. The unrelated pgvector extension is omitted from that isolated test; normal deployment still requires PostgreSQL with pgvector.
- Public and commercial browser checks use mocked API responses, headless Edge and axe. They verify navigation, application validation/retry, correct payloads, explicit zero commercial terms, role-filtered views, desktop/tablet/mobile layout and no detected WCAG A/AA violations in the tested screens.
- No live infrastructure, payout, email or provisioning action is performed by these tests.

Reproduce the source checks from the repository root:

```powershell
.\.venv\Scripts\ruff.exe check backend
.\.venv\Scripts\mypy.exe backend/app --config-file backend/pyproject.toml
.\.venv\Scripts\pytest.exe backend/tests -q
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run lint
```

For browser/migration harnesses, use an installed Microsoft Edge browser and install optional local test dependencies in `frontend` with `npm.cmd install --no-save --package-lock=false playwright @axe-core/playwright @electric-sql/pglite`. With Vite running at `http://localhost:5173`, run `node scripts/verify-portal.mjs` and `node scripts/verify-commercial-ui.mjs` from `frontend`. The public harness also accepts `PORTAL_URL`; the commercial harness uses port 5173. Reports and screenshots are written under `frontend/node_modules/.cache/`.

Generate offline migration SQL from `backend` with `..\.venv\Scripts\alembic.exe upgrade head --sql > ..\.venv\commercial-upgrade.sql`, then run `node scripts/verify-commercial-migration.mjs` from `frontend`. The harness creates only disposable in-memory databases.

Eligibility exclusions, settlement/refund policies, actual reseller prices and SI agreements remain explicit contractual inputs. The implementation does not invent these policies.
