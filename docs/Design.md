# Partner Portal — UX and Functional Design

This document describes the implemented UI as of 30 September 2026. Unimplemented refinements are tracked in [PRD.md](PRD.md#24-known-acceptance-refinements), not presented as available screens.

## 1. Experience and visual identity

The public journey is discover TCG → compare partnership paths → explore illustrative success stories → apply. The authenticated journey is register a deal → configure parties and economics → approve → finalize/accept a quote → order or record qualifying commission.

Public pages use a TCG identity of ivory, navy and burnt orange, DM Sans/Manrope with serif accents, and local SVG/CSS artwork. Workspace screens use deep green navigation, lime accents, light cards, forms and operational tables. Public CSS is scoped under `.portal`; reusable public sections and commercial editors keep spacing and behavior consistent.

Partner paths describe capabilities, not ranks. There are no tier badges, tier selectors or tier-derived benefits. Commercial numbers remain USD; live FX is not implemented.

## 2. Routes and navigation

| Route | Implemented experience |
| --- | --- |
| `/` | Landing hero, overview/ecosystem, products/services, benefits, paths, stories and CTA |
| `/partner-with-tcg` | Partnership benefits, ecosystem, onboarding steps and FAQs |
| `/partner-levels` | Partnership paths, requirements and comparison; URL retained for compatibility |
| `/partner-stories` | Manually controlled story carousel, narratives and product-information links |
| `/register` | Public three-step application; optional `?type=RESELLER` preselection |
| `/login` | Workspace sign-in |
| `/dashboard` | User/account overview, links and internal commercial summary |
| `/partners`, `/partners/new` | Partner listing/filtering and TCG-created partners |
| `/partners/:partnerId`, `/partners/:partnerId/users` | Company profile, approval/status actions and user administration |
| `/products`, `/pricing` | Catalog/SKU management and engagement-based resolved prices |
| `/documents` | Document search/list, authorized download and common publication controls |
| `/deals` | Deal creation, approval/submission and pipeline actions |
| `/commercial-model` | Commercial structure, terms, agreements, snapshots, commissions and review queue |
| `/commercial` | Quotes, MAF and Orders tabs |
| `/system` | Service readiness |

The authenticated sidebar labels `/commercial-model` as **Commercial model** for TCG and **My commissions** for partners. Actions are also enforced by the API. There are no standalone Customer Master or project-management pages in this version.

## 3. Registration and partner management

The public application has Company, Your details and Review steps. It captures company/contact details, country, a primary partnership interest and optional additional capabilities. It validates required fields, email/URL formats, a 12-character minimum password, confirmation and consent. Step navigation preserves entered data; passwords are not persisted to browser storage.

Submission sends `capability_codes` and company/contact data to the registration API. Confirmation appears only after API success, with a reference and review/next-step explanation. Option-loading and submission failures support retry. Approval deadlines are not promised.

TCG reviews requested capabilities and company details, approves or rejects with a reason, and controls status and capability changes. Partner administrators can edit permitted company/contact fields and manage their users. Profile pages show capabilities and countries. Commercial terms are managed in the commercial workspace, rather than through a tier assignment dialog.

## 4. Deals and components

The deal form begins with engagement model. TCG can select Direct without an external partner; other models require an active capable partner. Partners submit their own opportunities. The form captures product, name, customer/country, contact email, estimate and optional expected close date. TCG may link an existing customer organization.

The list displays model, approval, stage and estimated value, with a link to commercial configuration or migration review. Internal configuration captures an accountable user, participants, scoped role assignments and product/service components. Roles include customer relationship owner, bidder, contracting seller, mcube seller, delivery lead, referrer, product owner, technology provider and bill-to.

Participants have explicit capability, access and active controls. Components independently capture product owner, seller, delivery organization, billing organization and amount. SI responsibilities must be assigned explicitly. Errors identify missing roles, invalid capabilities, stale versions or required amendments.

Stage actions collect actual value/date for Won and a reason for Lost. Direct/Referral stage management remains with TCG. Some existing operational actions use browser prompt dialogs; a richer guided deal editor remains a refinement.

## 5. Commercial workspace

| Tab | Behavior |
| --- | --- |
| Structure | Select model/partner, edit membership, scoped primary responsibilities and solution components; capture amendment reason |
| Terms | TCG Admin drafts effective model-default, partner-agreement, opportunity or contract terms and approves versions |
| Agreements | TCG Admin manages organization/vendor identities, partner/vendor agreements, linked costs and draft contracts |
| Snapshots | TCG previews current approved terms, inspects frozen quote revisions and records conversion; partners see their own entitlement |
| Commissions | Show accrued, paid and outstanding amounts separately; TCG Admin records referenced payments/adjustments under an agreed policy |
| Migration review | TCG resolves legacy classification/structure before new commercial actions |

TCG Sales can work with structure, snapshots and review; terms and agreement administration are TCG Admin controls. Partner workspace tabs are limited to Snapshots and Commissions.

Referral terms expose the 10% model default and preserve an entered 0%. Eligibility explicitly captures components, eligible amount and discount/tax/vendor/credit/refund treatment. SI terms name the pool and denominator, allocation method, beneficiaries and residual; vendor deductions are explicit. Direct compensation is an optional, explicitly configured arrangement.

Amounts are labeled forecast, snapshotted, accrued or paid. Customer value, TCG entitlement, partner benefit, vendor obligations and commission expense are separate. Reseller margin is shown only for reseller opportunities and remains undisclosed when the selling price is private. The internal dashboard totals the latest stored snapshot per opportunity; it is an operational forecast, not accounting revenue.

## 6. Pricing and quote-to-order

Pricing selects engagement model and, where required, partner. It shows product/SKU, unit and USD price; the admin receives resolved source names. Catalog/agreement previews do not substitute for opportunity/contract quote pricing.

The quote builder inherits the deal model. It uses approved opportunities, SKU quantity and configured prices; manual extra line discounts are removed. SI quote creation requires the draft TCG contract reference from the commercial workspace. TCG finalization creates an immutable revision. Stale line pricing requires refresh, and commercial changes may require reapproval.

The reseller CTA is **Accept wholesale quote**. Other acceptance follows the contracting-party rules; the backend rejects an unauthorized actor even if an action is visible. Orders select an accepted quote and capture billing details and a commitment attachment, followed by review/return, confirmation, provisioning and activation.

MAF requests select an approved deal and real participating partner, capture tender details and supporting files, and require an issued document before issuance. Direct deals do not receive a fictitious partner solely to enable MAF.

## 7. Documents, errors and accessibility

The repository UI provides title/description search, metadata, current version and authorized download. Publishing exposes All Partners and TCG Internal. Capability/specific-partner scope and version APIs exist, but complete UI controls are deferred. Workflow attachment API coverage exceeds the current list/download controls in some screens.

Business-rule errors are shown near the action; forms retain data where implemented. Stale commercial edits instruct the user to reload. Account changes clear cached organization data.

Public layouts were checked at 320–1440px and commercial screens at desktop, tablet and 390px widths. Labels, focus states, semantic tables, keyboard controls, status text, reduced-motion support and automated WCAG A/AA scans are part of verification. Passing automated scans is not a substitute for complete manual accessibility acceptance.

## 8. Content readiness

Partner testimonials, people and success narratives are explicitly illustrative. Publish actual endorsements only after approved quotes/logos and verified metrics are supplied. No fabricated approval times or financial promises should replace the configured commercial terms. See [Partner-Portal-UI.md](Partner-Portal-UI.md) for public content and browser checks.
