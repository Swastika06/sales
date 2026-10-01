# Partner Portal — Project Memory and Decision Log

Updated **1 October 2026** to reflect the public portal, commercial-model implementation and document-based partner onboarding. This log records current decisions; use the linked specifications for full contracts and operating instructions.

## 1. Product Context

TCG Digital supplies mcube and LVA. The public Partner Network introduces its ecosystem and accepts applications; the authenticated workspace supports partner and commercial operations.

## 2. Local Development Stack

React/TypeScript/Vite, React Router and TanStack Query connect to FastAPI, SQLAlchemy async sessions, PostgreSQL with pgvector and private MinIO. Production onboarding also uses ClamAV, TLS-protected SMTP and a durable mail worker. The repository includes one production backend Dockerfile reused by the API, mail worker and migration Job, plus templates for backend configuration, a combined API/mail-worker Kubernetes Deployment and an internal ClamAV workload/Service. ClamAV signatures are ephemeral and refresh when its Pod starts. Compose, API-Service, migration-Job and Ingress definitions are not yet included. JWT provides API authentication and derives encryption for pending onboarding mail. pgvector availability does not mean AI search is implemented.

## 3. Delivered Baseline

Phase 0 and the core Phase 1A–1H workflows are implemented in source. The public partner journey and commercial replacement were completed on 30 September 2026; Legal document review and OTP activation were added on 1 October 2026. Schema head is `20261001_0006`. Live rollout and stakeholder acceptance remain distinct from source completion.

## 4. Partner Capabilities

Reseller, Referral and System Integrator are independently approved capabilities. A partner may hold several. Existing partner IDs remain stable and map to shared organizations. Legacy primary type is retained for compatibility; active participation uses capabilities.

## 5. Tier Retirement

Silver/Gold/Platinum classification, assignment, benefits and pricing are retired. Historical tables/references are retained only for audit. The public `/partner-levels` URL remains for compatibility but presents **Partnership paths**, not ranked tiers.

## 6. Territory

Countries describe coverage. Multiple partners may share a country, and territory does not block deal registration.

## 7. Partner Creation

TCG Admin can create partners; public self-registration requires review. Applications request capabilities and collect company/contact details and initial administrator credentials. Approval does not assign a tier.

## 8. Roles and Access

Roles are TCG Admin, TCG Sales, Partner Admin, Partner Sales, Partner Pre-Sales and Partner Delivery. Backend permissions remain authoritative. Partner access additionally requires active organization membership, approved capability and an explicit opportunity grant. Vendor relationships alone grant no access; a missing primary partner never makes a deal public. Authentication changes clear cached query data.

## 9. Deal Model

One Deal/Opportunity entity is used, with no separate Lead. Every new deal selects Direct, Reseller, Referral or System Integrator. Direct does not require an external partner. Organizations, capabilities, scoped roles and product ownership are separate concepts.

## 10. Approval and Amendments

TCG controls approval. Commercial edits use expected versions and require reapproval when previously approved. Accepted structures need an amendment reason; accepted contract terms need a replacement contract. General deal-field editing before resubmission remains incomplete.

## 11. Conflict Identity

Canonical customer ID + product ID identifies potential conflicts. Another approved, protected nonterminal opportunity blocks a conflict; a different product does not. PostgreSQL advisory locks serialize the check.

## 12. Protection

Approval starts 90-day protection. Won and Lost stop blocking other opportunities. Manual extension is not implemented; changing the duration requires policy work.

## 13. Pipeline

Registered → Qualified → Discovery → Demo → POC → Proposal → Negotiation describes the available working stages, not a mandatory adjacent sequence. Won requires actual value/date; Lost requires a reason. Both are terminal. Direct/Referral execution remains with TCG. Partner responses redact actual value and history notes.

## 14. Products and Ownership

Seeded products are mcube and LVA, each with license/implementation SKUs. No authoritative SKU prices are seeded. Product ownership is explicit; mcube belongs to TCG. A customer, partner and vendor may reuse the same underlying organization.

## 15. Currency and Rounding

Authoritative currency is USD. Decimal half-up rounding applies to cents; split residuals go to an explicit beneficiary. Live FX is not implemented and must not alter accepted history if added later.

## 16. Engagement Economics

Reseller uses an agreed wholesale amount; private customer selling price leaves margin/partner benefit null. SI uses an explicit fixed mcube amount, named-pool percentage or itemized allocation. Direct defaults to TCG entitlement, with optional approved partner compensation. Vendor obligations remain independent and identify their payer.

## 17. Superseded Assumptions

The 23 September baseline contained temporary reseller 20% discount, referral 3% within 1–5%, SI 15% markup and tier percentage assumptions. The 28 September commercial specification superseded these; the 30 September implementation removed them from active resolution and configuration. They must not be restored by seeds or copied into contracts as defaults.

## 18. Referral and Settlement

Default referral rate is 10%, with explicit 0–100% overrides. Eligible component scope, amount and discount/tax/vendor/credit/refund treatments are contractual inputs. Forecast does not mean earned commission. Won plus recorded conversion against frozen terms is required; actual eligible revenue is explicit. Accrual is idempotent. Adjustments and payments are append-only, referenced and subject to settlement policy; there is no automatic payout.

## 19. Quotes

Quotes inherit the approved deal model, resolve current scoped terms and require valid commercial structure. SI needs an explicit draft contract. Finalization rejects stale lines and writes immutable quote/commercial snapshots. Final quotes may reopen while retaining prior revisions; Accepted quotes cannot be rewritten. The reseller buyer accepts wholesale; other acceptance follows the contracting buyer and TCG customer-execution rules.

## 20. Orders

One order per accepted quote copies its accepted revision. The reference is assigned on creation; submission requires a `PURCHASE_ORDER` commitment attachment. TCG reviews, returns, confirms, provisions and activates. Confirmation persists `ORDER_CONFIRMED`; external publication and project creation are deferred.

## 21. MAF

MAF is separate from quote/order and requires a real active participating partner and approved deal. TCG review/issuance requires reasons for return/rejection and an `ISSUED_DOCUMENT` before issue. Issue records a 90-day expiry. Document generation and expiry scheduling are not implemented.

## 22. Documents

Private MinIO stores files; PostgreSQL stores metadata, checksums and versions. Downloads expire in ten minutes; uploads must be nonempty and at most 25 MB. Visibility is All Partners, Partner Type (approved capability), Specific Partner or TCG Internal. Legacy tier-scoped documents become internal pending review. Linked vendor/private contract restrictions override broad library grants.

## 23. Term Resolution

Resolve approved compatible parameters by contract → opportunity → effective partner agreement → engagement default → catalog. Model, effective dates and SKU scope apply. Explicit zero is preserved, equally specific overlaps are rejected, fixed prices replace catalog and discounts do not stack. Approved terms are versioned; source versions are frozen in snapshots.

## 24. Required Business Inputs

Actual catalog prices, wholesale agreements, SI pools/allocations, eligible referral revenue and exclusions, settlement/refund policy, MAF template/signatory, quote thresholds and retention policy require approved configuration. Public partner stories are illustrative; actual endorsements require approved content.

## 25. Source-of-Truth Rule

Use the latest confirmed stakeholder clarification, then confirmed product decisions, then earlier source material. Development assumptions are not contracts. [Commercial-Model.md](Commercial-Model.md) defines the current economics; [Rules.md](Rules.md) and [PRD.md](PRD.md) describe the implemented baseline and known limits.

## 26. History and Concurrency

Never recalculate historical quotes/orders from current prices. Snapshot, revision, conversion and commission records are protected by PostgreSQL immutability triggers. Opportunity row/version checks and term-scope advisory locks reject conflicting changes. Payment recording checks outstanding balance and expected ledger state. No live payment or provisioning integration is included.

## 27. Schema and Seeds

The six revisions cover foundation (`20260922_0001`), legacy partner management (`20260923_0002`), catalog/pricing (`20260923_0003`), sales/content (`20260923_0004`), the commercial replacement (`20260930_0005`) and private onboarding/Legal verification (`20261001_0006`). Revision `0005` preserves historical monetary values, maps capabilities, classifies only supported quote evidence and flags all legacy opportunities for review. Revision `0006` migrates pending Reseller/Referral applicants into document collection and deactivates their users pending verification. Destructive downgrade is refused.

Six idempotent seed keys are `foundation-identity-v1`, `phase-1a-partner-master-data-v1`, `phase-1b-product-pricing-v1`, `phase-1-remaining-permissions-v1`, `phase-1-mcube-display-name-v1` and `commercial-model-owner-v1`. The initial 10% referral default is inserted by the commercial migration, not by catalog seeding.

## 28. User Experience

Public routes cover landing, partnership benefits, paths, illustrative stories and application. Workspace navigation covers Overview, partners/users, Products & SKUs, Pricing, Documents, Deals & pipeline, Commercial model (My commissions for partners), Quote to order and System status. The commercial page has Structure, Terms, Agreements, Snapshots, Commissions and Migration review tabs; permissions restrict each view. [Design.md](Design.md) maps the routes and current controls.

## 29. Verification Baseline

Recorded on 1 October 2026: 69 backend tests, Ruff, strict Mypy, frontend type/build, ESLint, onboarding browser checks and embedded-workspace checks passed. The 30 September commercial baseline also passed its isolated PGlite migration checks, but revision `0006` has not been accepted against live PostgreSQL, MinIO, ClamAV or SMTP. Mocked checks do not establish live infrastructure readiness or complete manual accessibility acceptance.

## 30. Operation and Deployment State

During the implementation verification, the configured application database refused connections. No application database migration was applied, and `.env` was not changed. Verify the target and backup before following [Phase1-Implementation.md](Phase1-Implementation.md); this documentation update does not deploy the application. Alembic commands run from `backend`. Preserve accepted snapshots and supply approved commercial configuration before live acceptance.

## 31. Known Acceptance Gaps

The maintained list is [PRD Section 24](PRD.md#24-known-acceptance-refinements): general deal editing, customer administration/deduplication, full document-scope/version UI, richer attachment controls, guided operational forms, scheduled expiry, quote thresholds, external events and future integrations. Commercial structure editing, term approval, conversion evidence and commission records are implemented and should not be listed as missing.
