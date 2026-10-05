# Partner onboarding

Reseller and Referral applications now collect a company license, PAN document, and GSTIN certificate. Each company selects one partner type; documents are required for Reseller and Referral. The portal and standalone ezextend form share the same onboarding components.

## Workflow

1. The applicant completes company/contact details and selects three documents (PDF, PNG, or JPEG; maximum 10 MB each).
2. The server creates an inactive partner and an application draft. Documents go into the existing private MinIO bucket under an onboarding prefix. The primary contact receives an emailed temporary onboarding password, valid for five days from application creation. Failed uploads can be resumed at /onboarding with that work email and temporary password; registration does not ask the applicant to choose a password.
3. Submission checks document presence, number formats, and that the PAN embedded in the GSTIN matches the supplied PAN.
4. An admin opens **Onboarding review**, selects an application and assigns an active Legal reviewer.
5. The assigned reviewer downloads documents and approves, requests corrections, or rejects. Corrections reopen uploads; resubmission returns to admin routing. Older document versions are retained.
6. Legal approval activates the partner and emails a separate temporary Partner Portal password. Sign in at /login and replace it with a new password of at least 12 characters. The API blocks workspace access until this change succeeds and revokes temporary login sessions afterward.
7. Rejection emails the reason and leaves Partner Portal access disabled. Review is expected within five days; the system expires onboarding access after five days and does not automatically decide applications.

A partner remains PENDING_APPROVAL until the assigned Legal reviewer approves it. Admin approval, status changes, and normal login cannot bypass incomplete document review. Approval invalidates onboarding sessions and credentials. There is no onboarding password reset or self-service resend. Applicants with expired or lost credentials must contact the partner team.

Existing pending applications retain their original registration password for their original five-day window. Already-issued activation codes remain supported; verification now emails a temporary Partner Portal password with the same mandatory first-login change.

## Local setup

From the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pip install -e "./backend[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
~~~

Start the backend/frontend using the existing development instructions. Sign in as a TCG admin and use **Staff users** (select Legal) or **Onboarding review -> Add legal reviewer** to provision a Legal account. The admin assigns that account to an application; the reviewer signs in separately. Legal accounts only see their assigned applications and do not receive general sales/document-library access.

Admin-created Reseller/Referral partners also begin inactive and receive a draft continuation email. The admin's partner detail page includes **Request document submission** for existing pending registrations.

## Email delivery

Set the SMTP values in .env using .env.example as a reference:

- PUBLIC_PORTAL_URL: browser-facing portal origin, such as https://partners.example.com.
- SMTP_HOST, SMTP_PORT, SMTP_FROM.
- SMTP_USERNAME and SMTP_PASSWORD, if the SMTP server requires authentication.
- SMTP_STARTTLS=true for STARTTLS, or SMTP_SSL=true for implicit TLS.

Run the durable worker in its own process from backend:

~~~powershell
..\.venv\Scripts\python.exe -m app.services.onboarding_mail
~~~

The worker polls the PostgreSQL outbox, uses verified TLS by default, and retries transient failures up to six times. Queued message bodies are encrypted using a key derived from JWT_SECRET_KEY; Temporary passwords and application tokens are never logged. Successful, cancelled, and permanently failed jobs have their message bodies removed. Retain the configured JWT secret while pending messages exist, or reissue messages after rotating it.

A missing SMTP host leaves emails queued; no delivery is simulated. The admin review screen shows the latest delivery state. Expired or superseded onboarding-password emails are cancelled. Approval-password emails remain deliverable after the application is completed, and are cancelled if the password has already been changed or superseded. Delivery is at least once: a worker crash after SMTP acceptance may deliver the same message twice.

For local development, a local SMTP capture server may be configured on port 1025 with SMTP_STARTTLS=false. Real mail delivery requires your SMTP credentials and a running worker.

## Document access and scanning

Upload types are checked against their signatures and file extensions; supplied MIME headers are not trusted. Filenames and size are validated, storage keys are random, and downloads use authorized, expiring links. PAN/GSTIN documents are separate from the shared document library.

Set `CLAMAV_HOST` and `CLAMAV_PORT` (default 3310) to a ClamAV daemon supporting INSTREAM. ClamAV is mandatory in local development and production; local development uses `localhost:3310`. Uploads fail closed with HTTP 503 when the scanner is missing or unavailable, infected files are rejected, and an application cannot enter review unless every required document has a `CLEAN` scan result.

## Standalone ezextend integration

Sign-in and the full authenticated workspace are now embedded as well. See [ezextend configuration and session handling](ezextend.md).

The existing apiBaseUrl config continues to point to /api/v1. The optional onboardingRequest(path, init) bridge must support every /onboarding endpoint, JSON requests, multipart FormData bodies, and X-Application-Token headers. The previous submitApplication registration bridge is superseded for onboarding. getRegistrationOptions remains supported.

Tracking is available at the widget's /onboarding path. Set initialPath to /onboarding when hosting that page separately, and point PUBLIC_PORTAL_URL to the actual browser route that hosts it. The widget never changes the host's history.

After editing the shared onboarding UI:

~~~powershell
cd frontend
npm run sync:widget
~~~

## Verification

Backend tests use an isolated SQLite database, mock object storage, and mock email delivery. They cover permissions, missing documents, file validation, legal corrections/rejection, direct-activation bypasses, five-day onboarding expiry, restricted first-login sessions, temporary-password replacement/replay, legacy activation codes, resuming applications, and mail retries.

~~~powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
~~~

Browser smoke checks intercept API requests; they do not create real accounts or send emails. Start Vite first. The script uses installed Microsoft Edge and checks desktop/mobile registration, the standalone widget, mandatory first-login password changes, and admin routing.

~~~powershell
cd frontend
npm run build
npm run lint
node scripts/check-onboarding.mjs
~~~

## Internal staff accounts

Admins can use **Staff users** to create Finance, Sales, Legal, or Admin accounts. Enter a name, email, and role; there is no password field. The existing Legal reviewer shortcut uses the same invitation flow. Duplicate emails are rejected and partner roles cannot be selected here.

The encrypted outbox sends the user a temporary login password and the `/login` link. The user must replace it on first login; workspace APIs remain blocked until then. Superseded or already-consumed invitation emails are cancelled. Before the first password change, admins can use **Send new invitation** to recover a failed delivery; this replaces the old temporary password. Invitations cannot reset an established password. The same `app.services.onboarding_mail` worker delivers staff invitations and onboarding mail.

Finance receives view permissions for partner, catalog, pricing, sales, and document data, and is not an administrator. Admin-only actions remain restricted. Existing staff accounts are unchanged.

Run `npm run check:staff` from `frontend` to check staff creation and admin restrictions in the main portal and embedded widget using intercepted APIs.
