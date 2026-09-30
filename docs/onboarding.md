# Partner onboarding

Reseller and Referral applications now collect a company license, PAN document, and GSTIN certificate. This applies when either capability is selected, including an additional capability. The portal and standalone ezextend form share the same onboarding components.

## Workflow

1. The applicant completes company/contact details and selects three documents (PDF, PNG, or JPEG; maximum 10 MB each).
2. The server creates an inactive partner and an application draft. Documents go into the existing private MinIO bucket under an onboarding prefix. Failed uploads can be resumed at /onboarding with the applicant's email and password.
3. Submission checks document presence, number formats, and that the PAN embedded in the GSTIN matches the supplied PAN.
4. An admin opens **Onboarding review**, selects an application and assigns an active Legal reviewer.
5. The assigned reviewer downloads documents and approves, requests corrections, or rejects. Corrections reopen uploads; resubmission returns to admin routing. Older document versions are retained.
6. Legal approval queues an activation email. The primary applicant verifies its six-digit OTP at /onboarding, then signs in with the password created during registration.

Document review and email verification are separate from partner account status. A partner remains PENDING_APPROVAL until verification completes. Admin approval, status changes, and normal login cannot bypass an incomplete onboarding record. Existing active partners are preserved by the migration. Existing pending Reseller/Referral partners are moved into document collection.

## Local setup

From the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m pip install -e "./backend[dev]"
.\.venv\Scripts\python.exe -m alembic upgrade head
~~~

Start the backend/frontend using the existing development instructions. Sign in as a TCG admin and use **Onboarding review → Add legal reviewer** to provision a Legal account. The admin assigns that account to an application; the reviewer signs in separately. Legal accounts only see their assigned applications and do not receive general sales/document-library access.

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

The worker polls the PostgreSQL outbox, uses verified TLS by default, and retries transient failures up to six times. Queued message bodies are encrypted using a key derived from JWT_SECRET_KEY; OTPs and application tokens are never logged. Successful, cancelled, and permanently failed jobs have their message bodies removed. Retain the configured JWT secret while pending messages exist, or reissue messages after rotating it.

A missing SMTP host leaves emails queued; no delivery is simulated. The admin review screen shows the latest delivery state. OTPs expire after ten minutes; after a long delivery outage, the applicant can resume at /onboarding and request a new code. Resends have a 60-second cooldown and five-per-hour limit. Five incorrect guesses exhaust a code. Resending invalidates the previous code; activation consumes the code and revokes existing application tokens. Delivery is at least once: a worker crash after SMTP acceptance may deliver the same message twice, but the code still activates only once.

For local development, a local SMTP capture server may be configured on port 1025 with SMTP_STARTTLS=false. Real mail delivery requires your SMTP credentials and a running worker.

## Document access and scanning

Upload types are checked against their signatures and file extensions; supplied MIME headers are not trusted. Filenames and size are validated, storage keys are random, and downloads use authorized, expiring links. PAN/GSTIN documents are separate from the shared document library.

Set CLAMAV_HOST and CLAMAV_PORT (default 3310) to a ClamAV daemon supporting INSTREAM. Uploads fail closed when a configured scanner is unavailable or detects malware. Production uploads/reviews require scanning. Local development without a scanner records NOT_CONFIGURED, visible to reviewers; configure scanning and reupload before reviewing those documents in production.

## Standalone ezextend integration

Sign-in and the full authenticated workspace are now embedded as well. See [ezextend configuration and session handling](ezextend.md).

The existing apiBaseUrl config continues to point to /api/v1. The optional onboardingRequest(path, init) bridge must support every /onboarding endpoint, JSON requests, multipart FormData bodies, and X-Application-Token headers. The previous submitApplication registration bridge is superseded for onboarding. getRegistrationOptions remains supported.

Tracking and activation are available at the widget's /onboarding path. Set initialPath to /onboarding (optionally with #token=...) when hosting that page separately, and point PUBLIC_PORTAL_URL to the actual browser route that hosts it. The widget never changes the host's history.

After editing the shared onboarding UI:

~~~powershell
cd frontend
npm run sync:widget
~~~

## Verification

Backend tests use an isolated SQLite database, mock object storage, and mock email delivery. They cover permissions, missing documents, file validation, legal corrections/rejection, direct-activation bypasses, OTP expiry/attempts/replay, resuming applications, and mail retries.

~~~powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
~~~

Browser smoke checks intercept API requests; they do not create real accounts or send emails. Start Vite first. The script uses installed Microsoft Edge and checks desktop/mobile registration, the standalone widget, OTP activation, and admin routing.

~~~powershell
cd frontend
npm run build
npm run lint
node scripts/check-onboarding.mjs
~~~
