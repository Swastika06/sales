import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { DocumentFields } from "./DocumentFields";
import { onboardingRequest, saveDocuments, type Application, type ApplicationSession, type DocumentDrafts } from "./api";

export function ApplicationPage() {
  const [token, setToken] = useState(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token");
    return value ?? "";
  });
  const [application, setApplication] = useState<Application | null>(null);
  const [documents, setDocuments] = useState<DocumentDrafts>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activated, setActivated] = useState(false);
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    onboardingRequest<Application>("/me", token).then(data => { if (!cancelled) setApplication(data); })
      .catch(reason => { if (!cancelled) { setError(reason.message); setToken(""); } });
    return () => { cancelled = true; };
  }, [token]);
  async function run(task: () => Promise<void>) {
    setBusy(true); setError(""); setMessage("");
    try { await task(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Request failed. Try again."); }
    finally { setBusy(false); }
  }
  function resume(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void run(async () => {
      const session = await onboardingRequest<ApplicationSession>("/access", undefined, { email: data.get("email"), password: data.get("password") });
      setApplication(session.application); setToken(session.token);
    });
  }
  function resubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(async () => {
      await saveDocuments(token, documents);
      setApplication(await onboardingRequest<Application>("/me/submit", token, {}));
      setDocuments({}); setMessage("Your application has been sent to the admin team.");
    });
  }
  function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = new FormData(event.currentTarget).get("code");
    void run(async () => {
      await onboardingRequest("/me/verify", token, { code });
      setActivated(true); setToken("");
    });
  }
  return <section className="p-container onboarding-public">
    <span className="p-eyebrow">PARTNER APPLICATION</span><h1>{activated ? "Your account is ready." : "Track your application."}</h1>
    {error && <p role="alert" className="p-form-error">{error}</p>}
    {message && <p role="status">{message}</p>}
    {activated ? <><p>Your email has been verified and your workspace is active.</p><Link className="p-button" to="/login">Sign in</Link></> : !token ?
      <form onSubmit={resume} className="onboarding-form">
        <p>Use the work email and password from your application to resume uploads or enter your activation code.</p>
        <label>Work email<input name="email" type="email" autoComplete="username" required /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
        <button className="p-button" disabled={busy}>{busy ? "Checking…" : "Continue application"}</button>
      </form> : !application ? <p role="status">Loading application…</p> :
      <div className="onboarding-form">
        <h2>{application.company_name}</h2><p><strong>Status:</strong> {application.status.replaceAll("_", " ")}</p>
        <p>Application reference: {application.id.slice(0, 8).toUpperCase()}</p>
        <button className="p-button p-button-outline" disabled={busy} onClick={() => void run(async () => {
          setApplication(await onboardingRequest<Application>("/me", token));
        })}>Refresh status</button>
        {application.documents.length > 0 && <details><summary>Uploaded documents</summary><div className="onboarding-document-list">
          {application.documents.map(document => <article key={document.id}><strong>{document.kind.replaceAll("_", " ")}</strong><span>{document.filename}</span>
            <button type="button" className="p-button p-button-outline" disabled={busy} onClick={() => void run(async () => {
              const result = await onboardingRequest<{ url: string }>("/me/documents/" + document.id + "/download", token);
              window.location.assign(result.url);
            })}>Download</button></article>)}
        </div></details>}
        {application.review_comment && <p className="onboarding-note"><strong>Legal feedback:</strong> {application.review_comment}</p>}
        {["DRAFT", "CHANGES_REQUESTED"].includes(application.status) &&
          <form onSubmit={resubmit}><DocumentFields value={documents} onChange={setDocuments} required={application.required_documents} existing={application.documents} disabled={busy} />
            <button className="p-button" disabled={busy}>{busy ? "Submitting…" : "Submit for review"}</button></form>}
        {["PENDING_ADMIN_REVIEW", "LEGAL_REVIEW"].includes(application.status) &&
          <p>Your application is being reviewed. We will email you if changes are needed, or send an activation code after legal approval.</p>}
        {application.status === "PENDING_EMAIL_VERIFICATION" && <>
          <p>Legal has approved your documents. Enter the six-digit code emailed to {application.email}. Codes expire after 10 minutes.</p>
          <form onSubmit={verify}><label>Activation code<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required /></label>
            <button className="p-button" disabled={busy}>Verify and activate</button></form>
          <button className="p-button p-button-outline" disabled={busy} onClick={() => void run(async () => {
            await onboardingRequest("/me/resend", token, {}); setMessage("A new code has been queued for email delivery. Allow a moment before checking your inbox.");
          })}>Send a new code</button>
        </>}
        {application.status === "REJECTED" && <p>Your application was declined. Contact the partner team about the feedback above.</p>}
        {application.status === "COMPLETED" && <Link className="p-button" to="/login">Sign in to your workspace</Link>}
      </div>}
  </section>;
}
