# Partner Portal — Delivery Phases

Status as of **30 September 2026**. “Implemented” refers to the repository baseline, not deployment or final stakeholder acceptance. Current business behavior is defined in [PRD.md](PRD.md) and [Commercial-Model.md](Commercial-Model.md).

## Delivered milestones

| Milestone | Implemented scope |
| --- | --- |
| Phase 0 — Foundation | React/TypeScript/Vite, FastAPI, PostgreSQL/pgvector, MinIO integration, JWT, errors, audit, migrations and idempotent seeds |
| Phase 1A — Partner management | Public/TCG registration, review, profiles, countries, users, roles and backend isolation; capabilities now replace tiers |
| Phase 1B — Catalog and pricing | Products/SKUs, effective USD prices and approved scoped commercial terms; no seeded authoritative prices |
| Phase 1C — Content | Private files, metadata, categories, versions, authorized downloads and search; full scope/version UI remains a refinement |
| Phase 1D — Customers and deals | Customer capture/reuse, deal submission/review, conflict checks, 90-day protection and private attachments |
| Phase 1E — Pipeline | Authorized stage updates/history, Won/Lost validation and operational views |
| Phase 1F — Quotes | Deal-derived model, configured SKU pricing, contracting-party acceptance and immutable final revisions |
| Phase 1G — MAF | Approved-deal requests, review/return, issued-document upload, issuance and expiry metadata |
| Phase 1H — Orders | Accepted-quote snapshot, commitment upload, review/return, confirmation, provisioning/activation status and durable event |
| Public Partner Network | Responsive landing, products/solutions, benefits, partnership paths, illustrative stories and three-step application |
| Commercial replacement | Shared organizations, multiple capabilities, four engagement models, participants/roles/components, vendor agreements, versioned terms, snapshots, conversion-based commission and migration review |

The commercial replacement supersedes tier-based pricing, provisional reseller discounts, old referral assumptions and automatic SI markup. It includes Direct opportunities without an external partner. Vendor obligations remain separate from compensation.

## Remaining rollout and acceptance work

1. Verify the target database/storage configuration and backup; apply through `20261001_0006`, run seeds, verify the private bucket, and review pending Reseller/Referral users that the onboarding migration deactivates.
2. Review migrated capabilities, internalized tier-scoped documents and every legacy opportunity before new commercial execution.
3. Configure approved catalog prices, wholesale/SI terms, referral eligibility and settlement policies.
4. Run the live role-isolation, document, four-model quote/order and commission smoke tests in the [operations guide](Phase1-Implementation.md).
5. Complete stakeholder review, manual accessibility acceptance and approved public partner content.

The configured database refused connections during the earlier implementation verification, so live migration and end-to-end acceptance remain unverified. The current source passes 69 backend tests, Ruff, strict Mypy, frontend lint/build and mocked onboarding/workspace browser checks. Revision `0006`, ClamAV and SMTP still require live acceptance. See [Commercial-Implementation.md](Commercial-Implementation.md#verification) and [onboarding.md](onboarding.md#verification) for evidence and limits.

## Acceptance refinements

General deal-field editing, customer administration/deduplication, full document-scope/version UI, richer attachment controls, guided forms/contract selection, expiry scheduling and quote approval thresholds remain. The authoritative list is [PRD Section 24](PRD.md#24-known-acceptance-refinements).

## Future Phase 2 — Implementation and Delivery

Potential scope: publish/consume `ORDER_CONFIRMED`, create delivery projects, track requirements and milestones, infrastructure readiness, installation, testing, UAT, go-live and handover. The current event is stored transactionally; it has no external consumer.

## Future Phase 3 — Support and Subscription

Potential scope: support tickets, SLA/escalation, knowledge base, subscription/license visibility, renewal alerts and expansion opportunities. Billing, ERP integration and automated payments require separately defined scope.

## Future Phase 4 — Enablement and Governance

Potential scope: training, certification, partner health, QBR, reporting, joint business plans and advanced analytics. Capabilities remain distinct from any future qualification program.

## Future Phase 5 — AI and Advanced Search

Potential scope: document extraction, embeddings, semantic search, RAG and similar-deal discovery. The database has pgvector, but these workflows do not yet exist.
