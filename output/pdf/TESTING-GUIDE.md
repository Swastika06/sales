# Partner onboarding test samples and database analysis

Analysis date: 5 October 2026. Source inspection plus read-only inspection of the configured PostgreSQL database. Database revision: `20261001_0006`; 52 public tables including Alembic metadata. No database records were changed.

## Upload samples

All six PDFs contain fictional test data, are one page, and are under 3 KB. They are not official certificates. The current implementation does not OCR files, authenticate government registrations, or validate GSTIN checksums; it validates the upload signature/extension, malware scan, number formats, and PAN/GSTIN consistency. Legal must review the files separately.

| Form field | Reseller | Referral |
| --- | --- | --- |
| Company and legal name | Sample Reseller Technologies Private Limited | Sample Referral Consulting Private Limited |
| Capability | RESELLER | REFERRAL |
| Country | India (IN) | India (IN) |
| Address | 100 Sample Avenue, Kolkata, West Bengal, India | 100 Sample Avenue, Kolkata, West Bengal, India |
| Primary contact name | Sample Reseller Contact | Sample Referral Contact |
| Company license number | SAMPLE-RES-2026-001 | SAMPLE-REF-2026-001 |
| Company license upload | reseller-company-license.pdf | referral-company-license.pdf |
| PAN number | ABCDE1234F | PQRSX5678K |
| PAN upload | reseller-pan.pdf | referral-pan.pdf |
| GSTIN number | 19ABCDE1234F1Z5 | 19PQRSX5678K1Z7 |
| GSTIN upload | reseller-gstin.pdf | referral-gstin.pdf |

Use a different unused primary-contact email for each application that you can access (or receive through your local SMTP capture server). Enter a company email and a password of at least 12 characters. Website and phone can be left blank. PDFs do not create a partner on their own: enter the company/contact fields, choose the capability, enter each document number, and select the corresponding PDF in its own upload slot.

Submit via the public application form. A TCG admin assigns an active Legal reviewer in Onboarding review. The assigned reviewer approves the fictional documents for the test; the applicant receives and enters the six-digit activation OTP at `/onboarding` and then signs in. The OTP expires after ten minutes. The partner remains pending and its user inactive until activation completes.

ClamAV, private MinIO storage, configured SMTP and the mail worker must be available for the complete test. File checks were verified locally; these samples have not been submitted to the running portal or scanned by its ClamAV service.

## Unwanted / retired tables in the actual database

These are cleanup candidates based on current business behavior, not tables safe to drop immediately.

| Table | Actual row count | Finding |
| --- | ---: | --- |
| partner_commercial_terms | 3 | Retired capability-based percentage/commission configuration. No current service/API reads this model; the active resolver uses approved commercial_term_versions. |
| partner_price_overrides | 0 | Retired per-partner/SKU overrides. No current service/API reads this model; use scoped commercial_term_versions. |
| tier_pricing_adjustments | 3 | Retired tier discounts. Migration 0005 deactivates existing rows; no current pricing service reads this table. |
| partner_tiers | 3 | Retired tier catalog. Migration 0005 deactivates existing rows; active partner APIs omit tier selection and tier grants fail closed. ORM joins and foreign keys remain. |

Evidence: `backend/app/models/pricing.py`, `backend/app/models/partner.py`, `backend/app/services/pricing.py`, `backend/app/services/commercial.py`, `backend/app/domain/documents.py`, and `backend/alembic/versions/20260930_0005_commercial_model.py`.

Migration 0005 explicitly retains retired commercial rows for audit/review. Removing partner_tiers also requires handling partners.tier_id, documents.partner_tier_id and tier_pricing_adjustments.tier_id, plus Partner.tier ORM eager loading. Archive/review historical rows, remove obsolete code references, and use a new Alembic migration before removal. No DROP statements were executed or supplied as a ready-to-run cleanup.

Do not remove partner_types (active capability master), partner_capabilities, partner_countries, permissions, role_permissions, seed_records or alembic_version. Current authorization/seeding uses them. Shared documents/document_versions and onboarding_documents serve distinct workflows. organizations/customers/partners and all current agreement, commercial, ledger, history and event tables retain implementation references; empty tables alone are not evidence that they are unwanted.

The companion database-inventory.json records the actual public table names, migration revision and four candidate row counts. External applications or reporting dependencies were not audited.
