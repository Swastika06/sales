# Partner Portal — Business Rules

Current rules as implemented on **30 September 2026**. The [commercial specification](Commercial-Model.md) defines the detailed economics; [PRD acceptance refinements](PRD.md#24-known-acceptance-refinements) distinguish outstanding work. Earlier tier and temporary pricing rules are superseded, not alternative active policies.

## 1. Rule Priority

Latest confirmed stakeholder instructions take precedence over earlier decisions and development assumptions. Contractual amounts, exclusions and settlement policies must be explicit. Proposed future policy is not treated as implemented behavior.

## 2. Partner Rules

- **R-PARTNER-001:** Partners may have multiple approved capabilities: Reseller, Referral and System Integrator.
- **R-PARTNER-002:** Tier classification and assignment are retired; historical references are retained for audit.
- **R-PARTNER-003:** Capability, opportunity role, engagement model and product ownership are separate concepts.
- **R-PARTNER-004:** TCG Admin controls capability approval; capability alone grants no deal access.
- **R-PARTNER-005–007:** Countries describe coverage. Multiple partners may share a country; territory does not block deal registration.
- **R-PARTNER-008–010:** TCG Admin may create partners; self-registration requires approval before active partner access.
- **R-PARTNER-011:** Rejection requires a stored reason.
- **R-PARTNER-012:** One organization may hold customer, partner and vendor profiles without conflating their commercial relationships.

## 3. Access Rules

- **R-ACCESS-001:** Partner access requires an active partner, approved capability, active opportunity participation and the required explicit access grant.
- **R-ACCESS-002:** `NONE`, `PROGRESS` and `COMMERCIAL` grants control opportunity visibility. Referral access does not expose customer bids, quotes/orders or private vendor costs.
- **R-ACCESS-003:** APIs enforce access on lists, details, mutations and downloads; navigation is not authorization.
- **R-ACCESS-004–005:** Roles are TCG Admin/Sales and Partner Admin/Sales/Pre-Sales/Delivery. Administrative commercial actions remain TCG Admin controlled.
- **R-ACCESS-006:** Quote/order access and execution also follow the legal contracting parties. A null primary partner never opens access.
- **R-ACCESS-007:** Partner deal responses redact actual contract value and stage-history notes. Shared snapshots expose only the requesting partner's entitlement.
- **R-ACCESS-008:** Vendor-profile membership alone grants no opportunity or document visibility. Broad document grants cannot bypass linked private contract restrictions.

## 4. Deal Rules

- **R-DEAL-001–002:** Deal and Opportunity describe one entity; no separate Lead entity is implemented.
- **R-DEAL-003:** Approval states are Draft, Submitted, Under Review, Approved and Rejected.
- **R-DEAL-004:** Rejected deals can be resubmitted. General deal-field editing remains a documented refinement.
- **R-DEAL-005:** Authorized TCG users approve/reject deals; approval requires sales-management permission.
- **R-DEAL-006–007:** Commercial structure/term edits require version checks and reapproval of approved deals. Accepted structures require an amendment reason; accepted contract terms require a new contract.
- **R-DEAL-008:** Legacy review must be resolved before new commercial execution. New opportunities require one valid primary model.

## 5. Conflict Rules

- **R-CONFLICT-001:** Same canonical customer + product + another approved, unexpired protected nonterminal deal is a conflict.
- **R-CONFLICT-002:** A different product is allowed for the same customer.
- **R-CONFLICT-003:** Use canonical IDs, with PostgreSQL advisory locks serializing the customer/product check.

## 6. Protection Rules

- **R-PROTECT-001:** Protection starts at approval.
- **R-PROTECT-002:** It lasts 90 days unless the opportunity becomes Won/Lost first.
- **R-PROTECT-003:** Won and Lost are terminal and excluded from active conflicts.
- **R-PROTECT-004:** Manual extensions are not implemented.

## 7. Pipeline Rules

- **R-PIPE-001:** Stages are Registered, Qualified, Discovery, Demo, POC, Proposal, Negotiation, Won and Lost. Adjacent-stage progression is not mandatory.
- **R-PIPE-002:** Approved deals may be advanced by authorized sales users; Direct/Referral execution remains with TCG.
- **R-PIPE-003:** Preserve every stage change in history.
- **R-PIPE-004:** Won requires actual contract value and close date.
- **R-PIPE-005:** Lost requires a reason; neither terminal state may transition further.

## 8. Engagement and Vendor Rules

- **R-COMM-001–003:** Capability and scoped role are distinct from the opportunity's primary engagement model.
- **R-COMM-004:** Models are `DIRECT`, `RESELLER`, `REFERRAL`, `SYSTEM_INTEGRATOR`.
- **R-COMM-005:** A partner may participate differently on different deals if its approved capabilities and grants permit it.
- **R-COMM-006:** Direct requires no synthetic partner. Partner compensation requires an explicit associated beneficiary and approved eligibility/rate.
- **R-COMM-007:** Scoped primary roles must be unique per role/scope. Product ownership, selling, delivery and billing are independently assigned.
- **R-COMM-008:** Vendor obligations retain provider, buyer/payer, scope, billing basis and agreement evidence. Store a secret reference, never an API key in agreement fields.
- **R-COMM-009:** Vendor costs are separate by default; only explicitly named costs reduce an SI pool, once.

## 9. Product Rules

- **R-PRODUCT-001:** Initial products are mcube and LVA; TCG owns mcube.
- **R-PRODUCT-002:** Products/SKUs are configurable entities, not fixed columns on a deal.
- **R-PRODUCT-003:** Authoritative prices require approved business configuration and are not seeded.

## 10. Currency and Pricing Rules

- **R-PRICE-001–002:** Store and calculate authoritative amounts in USD using Decimal with half-up rounding to two places.
- **R-PRICE-003–004:** Live FX is not implemented. Any future informational equivalent must not alter stored accepted values.
- **R-PRICE-005:** Resolve compatible parameters by contract → opportunity → effective partner agreement → engagement default → catalog, considering SKU specificity and effective dates.
- **R-PRICE-006:** Approved versioned terms define the economics. Equal-specificity overlaps are rejected; explicit zero is retained.
- **R-PRICE-007:** Reseller revenue for TCG is agreed wholesale. Undisclosed selling price leaves margin/partner benefit null; disclosed negative margin is allowed. Referral allocations are invalid for Reseller.
- **R-PRICE-008:** Referral uses explicit eligible revenue and component/treatment definitions. Approved rate overrides permit 0–100%.
- **R-PRICE-009:** The referral engagement default is 10%; it does not imply all contract value is eligible.
- **R-PRICE-010:** SI uses fixed mcube value, a percentage of a named pool or itemized component allocations. Assign the rounding residual explicitly; flag whole-project SI share at or below 50% for review.
- **R-PRICE-011:** Tier rules, automatic reseller discounts and SI markups are retired. Fixed prices replace catalog prices; discounts do not stack.

## 11. Quote Rules

- **R-QUOTE-001:** Quotes inherit the model of an approved, reviewed deal and require valid components, roles and a TCG selling contract. SI requires an explicit draft contract.
- **R-QUOTE-002:** Finalization verifies current prices/sources and freezes an immutable numbered revision and commercial snapshot.
- **R-QUOTE-003:** An accepted quote is required to create an order. Acceptance checks current commercial approval/version and the contracting buyer.
- **R-QUOTE-004:** Lines use approved resolved pricing. Extra manual line discounts are disabled.
- **R-QUOTE-005:** Only the reseller buyer accepts its wholesale quote. SI acceptance follows its buyer; TCG records external customer acceptance where applicable. TCG Admin status does not override reseller acceptance ownership.
- **R-QUOTE-006:** Final quotes may reopen as Draft while preserving earlier revisions. Accepted quotes cannot be rewritten.

## 12. MAF Rules

- **R-MAF-001–003:** MAF is a separate authorization for a real participating partner, approved deal and named customer/product/tender context.
- **R-MAF-004:** States are Draft, Submitted, Under Review, Returned for Correction, Approved, Issued, Rejected and Expired.
- **R-MAF-005–006:** The partner must be active and the deal approved at request creation.
- **R-MAF-007:** TCG controls review/issuance; return/rejection needs a reason. Issue requires an uploaded `ISSUED_DOCUMENT` and records 90-day expiry. No automatic document generation or expiry job exists.

## 13. Order Rules

- **R-ORDER-001–003:** One order per accepted quote; preserve its accepted revision. Submission requires a PO/signed commitment with kind `PURCHASE_ORDER`.
- **R-ORDER-004:** States are Draft, Submitted, Under Review, Returned for Correction, Confirmed, Provisioning, Active and Cancelled.
- **R-ORDER-005–006:** TCG reviews commitment/billing details and returns for correction with a reason. Later pricing must not recalculate the stored quote snapshot.
- **R-ORDER-007:** The order reference is assigned at creation.
- **R-ORDER-008–010:** Reseller executes its wholesale order; Direct/Referral execution remains with TCG; SI follows its contracting parties.
- **R-ORDER-011:** Confirmation durably stores `ORDER_CONFIRMED` in the same transaction.
- **R-ORDER-012:** External event publication and automatic project creation are deferred.

## 14. Content Rules

- **R-DOC-001–002:** Store files in private MinIO and metadata/versions in PostgreSQL.
- **R-DOC-003:** Categories cover sales enablement, product documentation, implementation guides, pricing, proposal/SOW templates, RFP and Other.
- **R-DOC-004:** Visibility supports All Partners, Partner Type (approved capability), Specific Partner and TCG Internal. New tier visibility is invalid; legacy tier scope migrates to internal pending review.
- **R-DOC-005:** Downloads require authorization and expire in ten minutes. Files must be nonempty and at most 25 MB; record size, MIME type, SHA-256 and uploader.
- **R-DOC-006:** Workflow attachments and linked private contracts enforce parent access regardless of broad library visibility.

## 15. History and Commission Rules

- **R-HISTORY-001–003:** Never recalculate accepted/finalized history from current terms. Freeze amounts, roles, costs, eligibility, rates and source versions; orders copy accepted quote history.
- **R-HISTORY-004:** Retain deal and order status histories.
- **R-HISTORY-005:** Accrue commission only after Won plus recorded conversion referencing the agreed current Final/Accepted snapshot. Actual eligible revenue must use the frozen scope/treatments and cannot exceed actual contract value.
- **R-HISTORY-006:** A qualifying conversion/beneficiary can accrue only once. Forecasts are not accruals; losing a deal creates no accrual.
- **R-HISTORY-007:** Referenced adjustments and payments are append-only. Require settlement policy, unique references and current ledger state; payment must not exceed outstanding commission. No automatic payout occurs.
- **R-HISTORY-008:** PostgreSQL triggers protect immutable history and approved term parameters. Supersession creates a version rather than overwriting historical parameters.

## 16. Audit Rules

Record high-value partner/role changes, catalog and term approvals, commercial structure changes, deal approvals/stages, quote finalization/acceptance, MAF issue, order confirmation and commission activity with actor/entity/request context. Preserve legacy identifiers and monetary history during migration. Isolated verification is not evidence of live target deployment.
