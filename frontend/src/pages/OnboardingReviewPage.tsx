import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../features/auth/AuthContext";
import { onboardingRequest, type Application } from "../features/onboarding/api";

type Reviewer = { id: string; name: string; email: string };
export function OnboardingReviewPage() {
  const { user } = useAuth();
  const admin = Boolean(user?.is_superuser || user?.roles.includes("TCG_ADMIN"));
  const legal = Boolean(user?.roles.includes("TCG_LEGAL"));
  const [items, setItems] = useState<Application[]>([]);
  const [reviewers, setReviewers] = useState<Reviewer[]>([]);
  const [selected, setSelected] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [comment, setComment] = useState("");
  const [decision, setDecision] = useState("APPROVE");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const item = items.find(value => value.id === selected);
  async function refresh() {
    const [applications, people] = await Promise.all([
      onboardingRequest<Application[]>("/applications"),
      admin ? onboardingRequest<Reviewer[]>("/reviewers") : Promise.resolve([]),
    ]);
    setItems(applications); setReviewers(people); setLoading(false);
  }
  useEffect(() => { if (admin || legal) void refresh().catch(reason => { setError(reason.message); setLoading(false); }); }, [admin, legal]); // eslint-disable-line react-hooks/exhaustive-deps
  async function run(task: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await task(); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Request failed"); }
    finally { setBusy(false); }
  }
  function createReviewer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    void run(async () => { await onboardingRequest("/reviewers", undefined, data); form.reset(); });
  }
  if (!admin && !legal) return <div className="workspace-page"><p>You do not have access to onboarding review.</p></div>;
  return <div className="workspace-page">
    <header className="page-heading"><span className="eyebrow">Partner onboarding</span><h1>{admin ? "Applications & legal routing" : "Legal verification"}</h1><p>Review submitted company documents and record a decision for each application.</p></header>
    {error && <p role="alert" className="form-alert form-alert--error">{error}</p>}
    <button className="button-secondary" disabled={busy} onClick={() => void run(async () => undefined)}>Refresh</button>
    <div className="onboarding-review-grid">
      <section className="content-card onboarding-queue" aria-label="Applications">
        {loading ? <p role="status">Loading applications…</p> : !items.length ? <p>No applications available.</p> : items.map(application =>
          <button key={application.id} className={selected === application.id ? "is-selected" : ""} onClick={() => { setSelected(application.id); setReviewer(application.assigned_to_id ?? ""); setComment(""); }}>
            <strong>{application.company_name}</strong><small>{application.capabilities.join(", ")}</small><span>{application.status.replaceAll("_", " ")}</span>
          </button>)}
      </section>
      <section className="content-card detail-card">
        {!item ? <p>Select an application to review.</p> : <>
          <h2>{item.company_name}</h2><p>{item.email} · Version {item.revision}</p>
          <p><strong>Status:</strong> {item.status.replaceAll("_", " ")}</p>
          {item.review_comment && <p className="onboarding-note">{item.review_comment}</p>}
          <div className="onboarding-document-list">{item.documents.map(doc => <article key={doc.id}>
            <strong>{doc.kind.replaceAll("_", " ")}</strong><span>{doc.number}</span><small>{doc.filename} · {Math.ceil(doc.size / 1024)} KB · Scan: {doc.scan_status.replaceAll("_", " ")}</small>
            <button className="button-secondary" disabled={busy} onClick={() => void run(async () => {
              const result = await onboardingRequest<{ url: string }>(`/applications/${item.id}/documents/${doc.id}/download`);
              window.location.assign(result.url);
            })}>Download</button>
          </article>)}</div>
          {!item.documents.length && <p>No documents uploaded yet.</p>}
          {admin && ["PENDING_ADMIN_REVIEW", "LEGAL_REVIEW"].includes(item.status) &&
            <form className="onboarding-form" onSubmit={event => { event.preventDefault(); void run(() => onboardingRequest(`/applications/${item.id}/assign-legal`, undefined, { reviewer_id: reviewer })); }}>
              <label>Assign legal reviewer<select value={reviewer} onChange={event => setReviewer(event.target.value)} required><option value="">Select reviewer</option>{reviewers.map(person => <option key={person.id} value={person.id}>{person.name} ({person.email})</option>)}</select></label>
              {!reviewers.length && <p>Create a legal reviewer below to route this application.</p>}
              <button disabled={busy || !reviewer}>Send to Legal</button>
            </form>}
          {legal && item.assigned_to_id === user?.id && item.status === "LEGAL_REVIEW" &&
            <form className="onboarding-form" onSubmit={event => { event.preventDefault(); void run(() => onboardingRequest(`/applications/${item.id}/decision`, undefined, { decision, comment, revision: item.revision })); }}>
              <label>Decision<select value={decision} onChange={event => setDecision(event.target.value)}><option value="APPROVE">Approve and email activation code</option><option value="REQUEST_CHANGES">Request document corrections</option><option value="REJECT">Reject application</option></select></label>
              <label>Feedback<textarea value={comment} onChange={event => setComment(event.target.value)} required={decision !== "APPROVE"} minLength={decision !== "APPROVE" ? 3 : undefined} maxLength={2000} /></label>
              <button disabled={busy}>Record decision</button>
            </form>}
          {admin && item.mail_status && <p>Email delivery: {item.mail_status}{item.mail_error ? ` (${item.mail_error})` : ""}</p>}
        </>}
      </section>
    </div>
    {admin && <details className="content-card edit-panel"><summary>Add legal reviewer</summary><form className="compact-form" onSubmit={createReviewer}>
      <p>Create an internal Legal account. Share credentials through your usual secure channel.</p>
      <label>Full name<input name="full_name" required minLength={2} maxLength={200} /></label>
      <label>Email<input name="email" type="email" required /></label>
      <label>Password<input name="password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} /></label>
      <button disabled={busy}>Create legal account</button>
    </form></details>}
  </div>;
}
