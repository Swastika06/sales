# Partner Portal — Product Requirements Document

Current implementation baseline: **30 September 2026**. This document describes delivered behavior and separates remaining acceptance work. The detailed commercial specification is [Commercial-Model.md](Commercial-Model.md); operational evidence and deployment limits are in [Commercial-Implementation.md](Commercial-Implementation.md).

## 1. Product Summary

TCG Digital supplies mcube and LVA. The portal introduces its partner ecosystem, accepts applications and provides a shared workspace for partner administration, controlled content, deal registration, commercial agreements, quotes, MAF requests and orders.

## 2. Delivered Scope

The repository implements the public partner journey and the core Phase 0–1H workflows, including the commercial-model replacement. Partner capabilities, shared organizations, opportunity participation, versioned terms, immutable commercial snapshots and a conversion-based commission ledger are included. Source implementation is complete for this baseline; target-environment rollout and stakeholder acceptance remain separate.

## 3. Deferred Scope

Project delivery management, support/SLA, training/certification, renewals, QBR, partner health scoring, advanced analytics, AI/RAG, billing/invoicing, ERP integration, automated payouts and external event publication are not implemented. Live FX is also deferred; all authoritative amounts are USD.

## 4. Actors and Permissions

TCG Admin administers the platform; TCG Sales manages authorized sales workflows. Partner Admin manages its company/users and sales workflows; Partner Sales manages authorized sales workflows. Partner Pre-Sales and Partner Delivery have authorized read access in the current seed. Backend permissions and opportunity/contract membership govern access, including where a frontend action is visible.

## 5. Organizations and Partner Capabilities

A shared organization may have customer, partner and vendor profiles. Products have independent owner organizations; mcube belongs to TCG. Partners can hold several approved capabilities: `RESELLER`, `REFERRAL`, `SYSTEM_INTEGRATOR`.

Capabilities describe eligibility, not ranking or automatic deal access. Tier assignment, tier benefits and tier pricing are retired. Historical tier references remain for audit only. Countries describe coverage; multiple partners may operate in the same country, and country overlap does not block registration.

## 6. Partner Onboarding

Public visitors discover products, compare partnership paths, read illustrative stories and apply through a three-step Company → Your details → Review form. Applications collect company/contact details, countries, requested capabilities and initial administrator credentials. Password confirmation, consent and required fields are validated; confirmation appears only after successful API submission.

Self-registration creates `PENDING_APPROVAL`. TCG Admin reviews capabilities and approves or rejects, with a reason for rejection. TCG can also create partners directly. Supported statuses are `PENDING_APPROVAL`, `ACTIVE`, `REJECTED`, `SUSPENDED`, `INACTIVE`. Approval no longer assigns a tier.

## 7. Partner Profile

Profiles capture company/legal name, capabilities, countries, website, email, phone, address and primary contact details. TCG controls status and capability changes. Partner administrators manage permitted profile fields and their own users. Shared organization IDs allow an existing organization to be reused across profiles.

## 8. Deal Model

The UI calls an `Opportunity` a **Deal**. There is no separate Lead entity. Every new deal selects exactly one primary engagement model. Direct deals need no external partner; partner-led models require an eligible active partner. Additional organizations participate through explicit membership, scoped responsibilities and solution components.

## 9. Deal and Commercial Structure

The current deal form captures model, customer/country, product, name, contact email, estimated value and optional expected close date. TCG can select an existing customer organization. The commercial editor captures the accountable TCG user, participants, access grants, scoped primary roles and components.

Components independently identify product/service, owner, seller, delivery organization, bill-to and amount. Roles include customer relationship owner, bidder, contracting seller, mcube seller, delivery lead, referrer, product owner, technology provider and bill-to. An approved capability alone does not grant visibility.

## 10. Engagement Models

| Model | Implemented economics and execution |
| --- | --- |
| `DIRECT` | TCG contracts with the customer; full applicable customer value belongs to TCG by default. Optional partner compensation requires an explicit beneficiary and approved eligibility/rate. |
| `RESELLER` | TCG sells wholesale to the reseller. Customer selling price can remain private; undisclosed margin and partner benefit remain null. No referral allocation is permitted. |
| `REFERRAL` | TCG executes the customer quote/order. Default commission is 10% of explicitly eligible revenue; approved overrides allow 0–100%. Forecast is separate from earned commission. |
| `SYSTEM_INTEGRATOR` | Parties and responsibilities are explicit. Economics use fixed mcube value, a percentage of a named pool, or itemized component allocation. There is no automatic markup or assumed split. |

Vendor agreements remain independent of partner compensation. Vendor costs identify provider, buyer/payer, billing basis and scope. They reduce an SI pool only when explicitly included as deductions; a cost cannot be deducted twice.

## 11. Deal Approval and Changes

Approval states are `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`. TCG reviews submissions; rejected deals can be resubmitted. Commercial structure and term changes to an approved deal require reapproval. Concurrent edits use an expected version. Accepted structures require an amendment reason; accepted contract term changes require a replacement contract. General operational deal-field editing remains a refinement.

## 12. Duplicate and Conflict Rule

Conflict identity is canonical `customer_id` + `product_id`. Another approved, unexpired protected deal that is neither Won nor Lost blocks a conflicting submission/approval. A different product is allowed. PostgreSQL transaction advisory locks serialize checks for the same customer/product pair.

## 13. Deal Protection

Protection begins at approval and expires after 90 days. Won/Lost are terminal and stop blocking conflicts. There is no manual extension control. Changing the duration requires a future policy decision.

## 14. Pipeline

Stages are `REGISTERED`, `QUALIFIED`, `DISCOVERY`, `DEMO`, `POC`, `PROPOSAL`, `NEGOTIATION`, `WON`, `LOST`. Updates require an approved deal and authorized sales access. Direct/Referral stage management remains with TCG; partner management for other models follows commercial access. Transitions need not follow adjacent stages.

Won requires actual contract value and close date; Lost requires a reason. Every transition is recorded. Partner responses redact actual contract value and stage-history notes. Won alone does not accrue commission.

## 15. Products and Catalog

The initial catalog contains mcube and LVA with license/implementation SKUs. Products and SKUs are configurable, and product ownership is explicit. Authoritative SKU prices are intentionally not seeded; stakeholders must supply effective catalog prices and contractual inputs.

## 16. Commercial Resolution

Approved compatible parameters resolve in this order: **contract → opportunity → effective partner agreement → engagement default → catalog**. Effective dates, model and SKU specificity apply. Explicit zero overrides are retained; overlapping equally specific terms are rejected. Fixed prices replace catalog prices, and discounts do not compound.

USD calculations use decimal half-up rounding to two places. SI residuals go to the named beneficiary. The SI share of total project value is visible; a share of 50% or less raises a review warning rather than rejection.

Referral finalization requires an explicit eligible amount, component scope and treatment of discounts, taxes, vendor charges, credits and refunds. Accrual requires Won plus recorded conversion against the agreed current Final/Accepted snapshot, with actual eligible revenue under the same scope/treatments. Retries cannot duplicate accrual. Referenced adjustments and payments are separate append-only entries; settlement requires an agreed policy. No automatic payment is made.

## 17. Quotes

Quotes require an approved, classified, reviewed opportunity with valid roles/components and a TCG selling contract. The model is inherited from the deal. Reseller uses TCG-to-partner wholesale; Direct/Referral uses TCG-to-customer; SI requires an explicit draft contract reference.

SKU lines resolve applicable pricing when added. Manual extra line discounts are disabled; discounts belong in approved terms. Finalization rejects stale line prices/sources and freezes a numbered quote revision plus commercial snapshot. A Final quote can reopen as Draft; earlier revisions remain immutable. Accepted quotes are terminal.

Statuses are `DRAFT`, `UNDER_REVIEW`, `FINAL`, `ACCEPTED`, `EXPIRED`, `CANCELLED`. Reseller acceptance belongs to the wholesale buyer, including when a TCG user is an administrator. SI acceptance follows the contracting buyer; TCG records external customer acceptance for Direct/Referral and applicable SI customer contracts.

## 18. Manufacturer Authorization Form

MAF authorizes a real active participating partner for a named customer/product/tender. Creation requires an approved deal. Direct deals do not require a fictitious partner.

States are `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `RETURNED_FOR_CORRECTION`, `APPROVED`, `ISSUED`, `REJECTED`, `EXPIRED`. TCG controls review and issuance; return/rejection requires a reason. An `ISSUED_DOCUMENT` attachment is required before issue. Issuance records a 90-day expiry; document generation and scheduled expiry are not implemented.

## 19. Orders

One order may be created per accepted quote, subject to contracting-party execution access. It copies the accepted quote revision, including the frozen commercial reference. The order reference is assigned at creation. Submission requires a PO or signed commitment uploaded with attachment kind `PURCHASE_ORDER`.

States are `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `RETURNED_FOR_CORRECTION`, `CONFIRMED`, `PROVISIONING`, `ACTIVE`, `CANCELLED`. TCG reviews billing/commitment details, returns with a reason when needed, confirms and advances fulfilment status. Confirmation stores `ORDER_CONFIRMED` in the same transaction; no external provisioning integration is invoked.

## 20. Content and Attachments

PostgreSQL stores metadata/versions; private MinIO stores files. Categories cover sales enablement, product documentation, implementation guides, pricing, proposal/SOW templates, RFP and Other. API visibility supports `ALL_PARTNERS`, `PARTNER_TYPE` (any matching approved capability), `SPECIFIC_PARTNER`, `TCG_INTERNAL`. New tier scopes are rejected; migrated tier-scoped documents become internal pending review.

Downloads are authorized and signed for ten minutes. Uploads must be nonempty and at most 25 MB; versions retain SHA-256, MIME type, size and uploader. Linked private vendor/contract documents and workflow attachments remain subject to their parent access rules even if a broad library scope exists. Malware scanning and a content-type allowlist are not implemented.

## 21. Acceptance Status

The source baseline has 55 passing backend tests plus successful Ruff, strict Mypy, frontend type/build and ESLint checks recorded on 30 September 2026. Mocked public/commercial browser checks cover responsive layouts, forms, role views and automated accessibility. An isolated PostgreSQL migration harness checks fresh and legacy upgrades through `20260930_0005`.

These checks do not establish live deployment acceptance. The configured database refused connections during the implementation verification; no application database migration was applied. Live database/MinIO and stakeholder-data journeys remain to be verified using the [operations guide](Phase1-Implementation.md).

## 22. Required Business Configuration

Supply approved catalog prices, reseller wholesale terms, SI allocation agreements, referral eligibility/exclusion and settlement/refund policies, MAF template/signatory policy, retention policy and any quote approval thresholds. Public stories are illustrative and need approved endorsements before being presented as actual partner success stories. Retired tier adjustments and old percentage assumptions must not be reintroduced as defaults.

## 23. Technical Baseline

React/TypeScript/Vite uses React Router and TanStack Query. FastAPI exposes `/api/v1`, JWT authentication and backend authorization. SQLAlchemy async sessions, PostgreSQL/pgvector, Alembic and private MinIO provide persistence. The schema head is `20260930_0005`; immutable financial history and audit records preserve approved outcomes. See [Architecture.md](Architecture.md) for actual entities and transaction boundaries.

## 24. Known Acceptance Refinements

- General deal-field editing before resubmission is incomplete; commercial structure editing and reapproval are implemented.
- Customer capture/reuse and authorized listing exist; administrative editing, merging and deduplication do not.
- Capability/specific-partner document scopes and version uploads exist in the API; the publisher UI exposes All Partners and TCG Internal, with fuller version management deferred.
- Protected attachment APIs exceed the current rich list/download controls in some screens.
- Several operational actions use browser prompts, and SI quote creation requires a contract reference rather than a guided selector.
- Quote/MAF expiry has metadata and states, with no scheduler. MAF issuance uses uploaded documents.
- Quote approval thresholds await policy and are not enforced.
- `ORDER_CONFIRMED` is persisted, with no external publication or project consumer.
- Automated payout, invoice/ERP, live FX and complete amendment-lifecycle management are outside this baseline.
