# TCG Partner Network UI

Implemented baseline: **30 September 2026**. Start the Vite development server using the [operations guide](Phase1-Implementation.md), then open [the public portal](http://localhost:5173).

## Public routes

- `/`: landing page, network illustration, TCG ecosystem, benefits, product/service switcher, partner paths, stories, and application CTA.
- `/partner-with-tcg`: partnership overview, benefits, ecosystem, onboarding steps, and FAQs.
- `/partner-levels`: **Partnership paths** with Referral, Reseller and System Integrator cards, eligibility, requirements and comparison. The URL is retained for compatibility; these are capabilities, not tiers.
- `/partner-stories`: accessible, manually controlled story carousel, expanded narratives, and links to published solution information.
- `/register?type=RESELLER`: three-step company/contact/review application, with optional partner-path preselection.

The existing login, admin registration, and protected workspace routes remain available. The system readiness query now runs only on the system page.

## Design and content

The public styles are scoped under `.portal` and use ivory, navy, and burnt orange with DM Sans/Manrope and serif accents. Globe, product, and story illustrations use local SVG/CSS. Layouts adapt from 320px mobile screens through desktop. Interactive elements include focus states and reduced-motion support.

Partner paths reflect the documented commercial model rather than introducing ranked tiers. No new prices, commissions, approval deadlines, or contractual benefits are enforced by this UI.

Testimonials explicitly use illustrative companies, names, and stories. Replace them with approved partner quotes, logos, and verified success metrics before publishing them as actual endorsements. Content is centralized in `frontend/src/features/portal/portalData.ts`.

Sources used to inform the information architecture and product descriptions:

- [Oracle partner information architecture](https://www.oracle.com/partner/)
- [TCG mcube](https://www.tcgdigital.com/tcg-mcube/)
- [LabVantage Analytics](https://www.labvantage.com/informatics/analytics/)
- [TCG life sciences ecosystem](https://www.tcgdigital.com/industries/life-sciences/)

## Registration

The form loads master data from `GET /api/v1/partners/registration-options` and submits company/contact details, `country_codes`, `capability_codes` and initial administrator credentials to `POST /api/v1/partners/register`. The primary partnership path and optional additional capability checkboxes are deduplicated into `capability_codes`. Registration options retain the `partner_types` catalog name but contain no tier options. It validates required fields, email/URL formats, a minimum 12-character password, matching confirmation, and application consent. Company/contact data remain in React state while moving between steps; passwords are not persisted to browser storage.

A confirmation appears only after a successful API response and displays the returned application reference. Loading failures and submission errors are recoverable. No production demo fallback or fake success response is used.

The configured application database was unreachable during implementation verification on 30 September 2026, so live registration acceptance remains unverified. Apply the current migration/seed procedure and verify real submission with the [operations guide](Phase1-Implementation.md). Browser verification uses mocked responses and does not prove live database readiness. Commercial approval, eligibility and calculation remain backend responsibilities.

## Verification

Run the normal project checks from `frontend`:

```powershell
npm.cmd run build
npm.cmd run lint
```

The browser smoke test uses Playwright and axe-core, with mocked registration responses so it creates no partner records:

```powershell
npm.cmd install --no-save --package-lock=false playwright @axe-core/playwright
node scripts/verify-portal.mjs
```

The script uses an installed Microsoft Edge browser and the local development server. Set `PORTAL_URL` to use another server. It checks routes, product tabs, comparison expansion, carousel behavior, mobile navigation, form validation, consent, submitted capability payload, server errors, retries, confirmation, horizontal overflow at 320/390/768/1024/1440px, and WCAG A/AA automated accessibility rules. Reports and screenshots are written to `frontend/node_modules/.cache/portal-checks`.


For the authenticated commercial workspace, access rules and remaining UI refinements, see [Design.md](Design.md) and [Commercial-Implementation.md](Commercial-Implementation.md).
