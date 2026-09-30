# Standalone ezextend portal

`frontend/ezextend/react-design.jsx` includes the public portal, registration and application tracking, sign-in, and the complete authenticated workspace. Partner Login opens the sign-in form inside the widget. Successful sign-in opens the dashboard; legal-only users enter legal verification. Partner, admin, sales, and legal navigation uses the same components and role checks as the local app. Backend authorization continues to enforce access.

The host must supply React 18+ and its existing `render()` function. The file has no package imports and does not download a second React instance or a workspace script. Router and query dependencies are bundled into the file. Workspace styles are scoped to `[data-tcg-workspace]`; navigation uses an in-memory router and leaves the host URL/history unchanged.

## Configuration

Set this before mounting, or pass these settings through `<EzComponent config={...} />`:

```js
window.TCG_PARTNER_PORTAL_CONFIG = {
  // Full API prefix. Use an absolute URL when the backend is on another origin.
  apiBaseUrl: "https://your-backend.example.com/api/v1",
  initialPath: "/",          // Or /login, /dashboard, /partners/<id>/users, etc.
  loadFonts: true,
  requestTimeoutMs: 15000,
  // Optional: override the default session key scoped to the API URL.
  // tokenStorageKey: "my_partner_widget_session",
};
```

`workspaceUrl` is no longer used. The widget does not read the server's `.env` file. The local Vite app continues to use `VITE_API_URL` and its development proxy; ezextend uses `apiBaseUrl`. Configure the backend's existing `CORS_ORIGINS` setting to allow the ezextend page's origin when they differ. Serve the backend over HTTPS when the host page uses HTTPS.

The existing `getRegistrationOptions` and `onboardingRequest` bridges still apply to public registration/application tracking. Authenticated workspace requests use the configured REST API.

## Authentication

- The shared login submits URL-encoded `username` and `password` to `POST /auth/token`, then verifies the returned token with `GET /auth/me`.
- The token is stored only after user lookup succeeds. Pending, rejected, invalid, or unavailable sign-ins display an error.
- Protected calls include the bearer token. Sessions survive reloads; a protected deep link returns to its requested page after sign-in.
- Widget tokens use a storage key scoped to the API URL by default, separate from the local portal's `partner_portal_token`. Passwords are never stored. When browser storage is unavailable, the session remains in memory for the mounted widget.
- Sign-out clears the token and cached account data. A 401 response clears the matching session and returns to sign-in. A late response from an older session cannot clear a newer token.

Company profile, users, pricing, documents, deals, commercial models/commissions, quote-to-order, system status, and the admin/legal pages are embedded from the local source.

## Keeping the file synchronized

Edit the shared components under `frontend/src`, then regenerate the standalone file:

```powershell
npm.cmd --prefix frontend run sync:widget
```

This synchronizes onboarding plus the login/workspace bundle and styles. Do not hand-edit the generated workspace block in `react-design.jsx`.

The workspace entry is `frontend/src/embedded/Workspace.tsx`; shared routes are in `frontend/src/app/WorkspaceRoutes.tsx`. The generator substitutes the widget's API/session configuration while retaining the shared API client, authentication, protected routes, and pages.

## Verification

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run check:widget
# With the local Vite server running:
npm.cmd --prefix frontend run check:onboarding
```

Browser checks use installed Microsoft Edge and intercepted API responses. They verify desktop/mobile login and workspace navigation, an authenticated profile update, restored and expired sessions, logout, protected deep links, rejected sign-ins, admin/legal navigation, public form links, and style/history isolation. They do not create real accounts or prove live backend/CORS availability.
