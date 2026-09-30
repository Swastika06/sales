# mcube commercial and partner-management design

Effective decision date: 28 September 2026.

Status: implemented in source on 30 September 2026. See [implementation and verification](Commercial-Implementation.md) for delivered behavior, tests and migration instructions. Live database deployment remains separate.
This document supersedes earlier tier-based commercial requirements, the 1–5% referral
range / 3% default, and the temporary SI markup model.

## 1. Engagement model

Every opportunity has exactly one primary engagement model:
`DIRECT`, `RESELLER`, `REFERRAL`, or `SYSTEM_INTEGRATOR`.
Technology/vendor associations are independent and may accompany any model.

| Model | Customer relationship / contracting | TCG commercial entitlement | Partner benefit |
| --- | --- | --- | --- |
| Direct | TCG owns the relationship, bids, and sells | Applicable customer revenue | None by default; any exception requires an explicit associated beneficiary and arrangement |
| Reseller | Reseller owns the commercial relationship and determines its customer price | Agreed wholesale price charged to reseller | Customer selling price less wholesale purchase price; no separate referral commission |
| Referral | Partner introduces the opportunity; TCG owns engagement, bid, implementation, and commercial execution | Customer revenue; referral commission is recorded separately | 10% of explicitly eligible revenue when TCG wins and the opportunity becomes a successful customer/project |
| System Integrator | Contract determines relationship owner, bidder, seller, and delivery lead | Agreed value attributable to mcube | Major share of the overall project under configurable project/contract terms |

Direct is an opportunity classification, not a synthetic external partner record. A partner
can have multiple capabilities: Reseller, Referral, and System Integrator. There are no ranks,
tiers, or tier-derived benefits. Capability permits participation but does not determine a
deal's terms or automatically grant access.

TCG can act as a solution integrator on a Direct deal using AWS technology. Its delivery role
does not by itself change the primary engagement model to System Integrator; that model
describes the commercial collaboration with an external SI.

## 2. Parties, roles, and relationships

Use a shared organization identity for TCG, customers, partners, and technology vendors.
An organization may hold multiple profiles. The same company can be a vendor in one
agreement and a reseller or SI in another; avoid duplicate legal entities.

Separate long-term relationships from opportunity-specific participation. The table below maps the design to the implemented persistence model:

| Entity | Essential fields / purpose |
| --- | --- |
| `organizations` | ID, legal/display name, organization identifiers, active status; seed TCG as an internal organization |
| `partners` | Existing partner-profile table with organization ID, onboarding status, contacts and countries; preserves partner IDs |
| `partner_capabilities` | Partner ID + capability; unique pair, no ordinal rank |
| `vendor_profiles` | Organization ID, provider category, commercial contact; independent of partner onboarding |
| `partner_agreements` | Parties, capability, effective dates, status, document reference; optional parent for project terms |
| `vendor_agreements` | Provider, contracting buyer, license/consumption model, billing basis, effective dates, private contract reference |
| `opportunities` | Customer, primary engagement model, optional primary commercial partner, internal accountable user, stage, currency |
| `opportunity_participants` | Opportunity + organization; participating status and explicit access grant |
| `opportunity_role_assignments` | Participant + role + scope; scope may be entire opportunity, contract, or solution component |
| `solution_components` | Opportunity, product/SKU or external service, owner organization, selling organization, delivering organization, billing party |
| `opportunity_vendor_links` | Opportunity/component + vendor agreement, usage responsibility, payer, cost treatment |
| `commercial_contracts` | Opportunity, seller, buyer, kind, version, status, document and accepted quote reference; effective dates belong to term versions |
| `commercial_term_versions` | Agreement/opportunity/contract scope, effective dates, approved status, calculation parameters and source |
| Allocation JSON | Validated definitions in `commercial_term_versions.parameters`; computed entitlements in immutable snapshot payloads, with no separate allocation table |
| `commercial_snapshots` | Opportunity, quote/revision and engagement version with frozen roles, inputs, terms, rounding, allocations and source versions; orders copy accepted revision data |
| `conversion_evidence` | One recorded conversion per opportunity, agreed snapshot, evidence, actual eligibility and recording user |
| `commission_accruals` | Beneficiary, unique qualifying event, frozen eligible amount/rate/entitlement and settlement policy |
| `commission_adjustments`, `commission_payments` | Separate append-only referenced entries; accrued, adjusted, paid and outstanding amounts remain distinct |

Roles include `CUSTOMER_RELATIONSHIP_OWNER`, `BIDDER`, `CONTRACTING_SELLER`,
`MCUBE_SELLER`, `DELIVERY_LEAD`, `REFERRER`, `PRODUCT_OWNER`, `TECHNOLOGY_PROVIDER`,
and `BILL_TO`. Each role references a participant rather than a text name.
For customer relationship and delivery, mark exactly one primary responsible party per scope;
allow additional contributors. Each contract has one legal seller and one buyer. Separate
contracts represent reseller-to-customer and TCG-to-reseller transactions without double
counting them as TCG revenue. Record referral submission/acceptance and attribution separately
from ongoing customer ownership.

Products retain an owner independently from the seller or delivery lead. TCG owns mcube;
an AWS component can have AWS as its provider while TCG sells and delivers the overall solution.
Store secret-manager references for provider credentials, never API keys in commercial records.

## 3. Commercial calculation rules

Use decimal arithmetic and the existing USD transaction currency. Store rates with sufficient
precision and round final line allocations to two decimals using half-up rounding. Allocate
any one-cent percentage-split residual to the named residual beneficiary, so totals reconcile.

Maintain distinct measures: customer contract value, TCG entitlement, partner entitlement,
vendor cost, commission expense, and margin. These are operational commercial measures;
do not collapse them into one `revenue` field or treat gross/net accounting recognition as
automatically settled by this model.

### Reseller

`TCG entitlement = agreed wholesale line amounts after agreed wholesale discounts`.

`Reseller gross margin = customer net selling value − wholesale purchase value`.

The reseller sets the customer selling price independently. If not disclosed, margin is
unknown, not zero. A negative margin is possible and must not change TCG's wholesale amount.
Wholesale pricing may be fixed or resolved from configurable price/discount terms. Customer
price is not an input into TCG pricing unless expressly agreed. Referral allocations for this
transaction are invalid. Vendor expenses remain separate from this gross margin calculation.

### Referral

`Commission = eligible revenue × resolved referral rate / 100`.

The initial default is **10%**, replacing the earlier 3% and 1–5% restriction. Authorized
partner/opportunity terms may override the default. Validate configured rates from 0 to 100;
an explicit zero must not fall back to 10. A referral partner is neither the mcube purchaser
nor its reseller. Commission is an expense/payable, not a reduction in customer invoice value.

Each term version must explicitly identify eligible components/lines, eligible amount, and
the treatment of discounts, taxes, pass-through vendor charges, credits, and refunds. The
user has not defined these exclusions; do not assume total contract value is eligible revenue.
Permit estimates in draft but block commercial finalization if the eligibility basis is absent.

Record forecast commission separately. Accrue only on `WON` plus recorded customer/project
conversion evidence (accepted contract/order or explicitly recorded conversion evidence).
No commission accrues for pending/lost opportunities or a bid win without conversion.
Payout timing is a separate configurable settlement policy; no automatic payout is implied.
Use a unique qualifying-event/beneficiary key to prevent duplicate accrual on retries. Preserve
original accruals and record credits/refunds as referenced adjustments according to agreed terms.

The implementation requires a TCG user to record conversion evidence against the current Final
or Accepted quote snapshot; quote acceptance alone does not record conversion. Actual eligible
revenue must preserve the agreed component scope and treatment definitions and cannot exceed
actual contract value. Referenced payments record settlement but do not transfer funds.

### System Integrator

Support a fixed mcube allocation, a percentage split of a named pool, and itemized component
allocations. Every percentage names its denominator; never apply a percentage to an ambiguous
"project value." Contract configuration defines whether a pool is gross or net of named costs.

For a simple two-party pool `P` and TCG percentage `t`:

`TCG entitlement = P × t / 100`; `SI entitlement = P − TCG entitlement`.

For component-based terms, sum the TCG-assigned mcube amounts and the SI-assigned amounts.
Do not apply the old 15% SI markup. Require explicit terms; no invented default share.
Validate allocation totals, pool scope, and no duplicate allocation of the same amount. A
cost cannot both reduce the pool and be deducted again from the resulting entitlements.
Show the SI's share of the overall project and flag when it is not the major share. This is
a review exception against the stated business expectation, not a hardcoded percentage split.

### Direct and vendor relationships

Direct defaults to the full applicable customer commercial amount for TCG and zero partner
allocation. Additional compensation needs an explicit partner beneficiary, basis, and approved
term version; adding a technology vendor never creates a commission or revenue share.

Vendor agreements retain independent license, usage, infrastructure, or service charges.
Record who contracts with and pays the vendor (TCG, SI, reseller, or customer). A vendor's
invoice is a cost obligation for its buyer, not automatically a project revenue split.
Only explicit project terms can include/exclude vendor costs in a calculation pool. Vendor
cost updates do not revise accepted customer prices or allocations automatically.

### Term resolution and snapshots

For each compatible parameter, precedence is: approved contract terms, opportunity terms,
partner agreement/partner-specific terms, engagement-model default, then applicable catalog
price. Resolve only within the selected engagement model and relevant component scope.
Explicit fixed prices replace the calculated price; discounts do not silently stack. Reject
overlapping active terms of equal specificity rather than choosing an arbitrary row.
Record the source of every resolved parameter. There is no tier stage.

Freeze resolved roles, beneficiaries, eligibility, rates, amounts, and source versions at quote
finalization. The accepted revision feeds the order snapshot. Closure commission uses the agreed
terms with actual eligible revenue, preserving the forecast separately. Later edits create new
versions and must never recalculate finalized history. Changing engagement model or primary
commercial parties after approval requires reapproval; accepted contracts require an amendment.

## 4. Workflow and authorization

The deal form starts with engagement model, customer and product. The commercial workspace then
configures components, participants, customer relationship owner, bidder, contracting seller,
mcube seller, delivery lead and terms. Defaults assist entry but server-side validation enforces the model:

- Direct requires TCG as primary customer owner, bidder, and contracting seller; no partner required.
- Reseller requires an active reseller participant and wholesale terms; reseller owns the customer
  commercial relationship and customer price. No referral allocation is allowed.
- Referral requires an attributed referral participant; TCG handles bidding, selling, delivery,
  and commercial execution. Show eligible revenue and the 10% default explicitly.
- SI requires an SI participant, explicit role ownership, allocation basis, and agreed shares.
- Vendor associations are optional repeatable rows in all four models and have their own agreements.

Partners may submit their own opportunities/referrals; TCG reviews and manages commercial
approval. In Referral and Direct flows TCG handles customer quote/order execution. Reseller
acceptance of the TCG wholesale quote must not be described as customer acceptance. For SI,
route acceptance and order actions to the specified contracting parties. Keep partner MAF
authorization available where applicable; do not require a fictitious MAF partner for Direct.

Opportunity membership and permissions replace reliance on a single `partner_id` for access.
Keep internal responsible user, customer relationship owner, and portal access owner distinct.
Referral users can view their submission, approved progress, and their commission; they do not
automatically see customer bid details, vendor agreements, or other participants' economics.
SIs/resellers see explicitly shared records and their own terms. Vendor participation alone
grants no portal access. TCG cross-organization access remains role-controlled. Enforce the
same rules on list, detail, export, nested snapshot, document, and attachment endpoints.
Never interpret a null primary partner as a public/unscoped record.

Replace tier filters, badges, selectors, pricing adjustments, and document visibility with
capability/explicit participant scopes. Separate commercial summary panels for customer value,
TCG entitlement, partner benefit, and vendor costs, subject to permissions. Show draft,
approved, snapshotted, accrued, and paid amounts with distinct labels.

## 5. Acceptance scenarios

Illustrative values below are acceptance fixtures, not catalog prices or contractual defaults.

| Scenario | Expected result |
| --- | --- |
| Reseller buys at $80,000 and sells at $100,000 | TCG $80,000; reseller gross margin $20,000; referral commission $0 |
| Reseller keeps customer price private | TCG $80,000; reseller margin unknown; transaction remains valid |
| Referral, contract $100,000, explicitly eligible $80,000, 10% | $8,000 forecast; $8,000 accrued only after win and conversion; customer value remains $100,000 |
| Same referral is lost or still pending | No accrued commission |
| Referral partner has explicit 12% project rate on $80,000 | $9,600 commission when qualified; changing defaults later does not change history |
| SI project $200,000, approved whole-project split 30% TCG / 70% SI | TCG $60,000; SI $140,000 |
| SI project $200,000, fixed mcube allocation $50,000 | TCG $50,000; SI residual $150,000 if explicitly agreed |
| Direct customer contract $100,000, no partner terms | TCG commercial amount $100,000; partner allocation $0; no partner record required |
| Direct + AWS; contract $100,000 and TCG vendor charge $10,000 | TCG customer amount $100,000; vendor cost $10,000; no automatic AWS share |
| Direct with explicitly approved 5% partner compensation on $40,000 | $2,000 partner compensation; beneficiary and scope stored; no implicit default |
| SI + AWS with customer paying AWS separately | SI/TCG pool follows project contract; AWS charge excluded unless explicitly included |
| One company resells one deal and refers another | Independent terms and permissions; no inherited reseller commission |
| Same conversion event processed twice | One commission accrual |
| Unauthorized participant requests quote snapshot or vendor contract | Access denied or appropriately filtered; no commercial leakage |
| Legacy accepted quote contains a tier discount | Historical total preserved; new quotes cannot resolve tiers |

Also test zero overrides, missing eligibility, excessive percentage totals, rounding residuals,
equal-priority effective-date overlaps, changes requiring reapproval, cross-partner IDs, vendor
cost double deduction, and attempted referral commissions on reseller transactions.

## 6. Implementation and migration map

The pre-migration application required a partner on opportunities, quotes and orders, used a
single partner type and tier pricing, and scoped access through that primary partner. Migration
`20260930_0005` and the corresponding API/UI changes replace these assumptions together.

| Area | Delivered change |
| --- | --- |
| Identity | Add shared organizations and multi-capability mappings while retaining existing partner/customer IDs. Direct has no synthetic partner. |
| Participation | Add explicit participants, scoped roles, solution components, vendor obligations and accountable TCG ownership. |
| Legacy classification | Use unambiguous consistent quote evidence, never partner type alone. All existing opportunities require structure review; ambiguous models remain unset in the migration review queue. New non-review records require a valid model. |
| Pricing | Replace tier/type formulas with approved effective term resolution and a Decimal calculator. Insert the initial 10% referral default; do not convert ambiguous legacy terms into new agreements. |
| Contracts and history | Store contracts, term versions, immutable quote/commercial snapshots and accepted revision copies on orders. Preserve existing finalized quote/order totals and identifiers. |
| Commission | Record conversion evidence, idempotent accrual, referenced adjustments and payments separately. |
| Authorization | Update deal, quote, order, document and attachment checks to use capabilities, explicit grants and contracting parties. Null partner IDs never bypass scope. |
| Tier retirement | Remove current selectors, assignment, pricing and configuration endpoints. Retain historical tables/references; deactivate adjustments and restrict tier-scoped documents to TCG Internal pending review. |
| UI | Deliver public partnership paths, multi-capability applications, model-first deal creation, commercial structure/terms/agreements, forecasts/snapshots, commission ledger and migration review. |
| Verification | Exercise calculator, isolated API/SQL workflows, public/commercial browser checks and fresh/legacy PostgreSQL migration fixtures. Live target acceptance remains separate. |

The original logical `partner_profiles` and `commercial_allocations` concepts are implemented
through existing `partners` and validated term/snapshot JSON respectively. Effective dates live
on terms and agreements. Accepted economics are linked through the accepted quote and immutable
revision; a complete standalone contract-amendment lifecycle is not implemented. Structural
amendment reasons, reapproval and replacement contracts protect accepted terms.

The configured database refused connections during implementation verification on 30 September
2026; no application database was migrated. Take and verify a backup before rollout. Destructive
downgrade is intentionally refused. See [Commercial-Implementation.md](Commercial-Implementation.md)
for source/API mapping and [Phase1-Implementation.md](Phase1-Implementation.md) for operating commands.

## 7. Configurable policy inputs still needed

The four engagement models, no-tier decision, reseller economics, and initial 10% referral
default are confirmed requirements. Eligible revenue inclusions/exclusions, conversion evidence
accepted by operations, referral payout timing, refund treatment, actual reseller prices, SI
allocation agreements, and exceptions to the SI-major-share expectation remain contractual
configuration inputs. Do not invent these as global rules. Draft records can be incomplete;
require the relevant inputs at the commercial approval/accrual gate described above.
