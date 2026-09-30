import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import {
  approvePartner,
  changePartnerStatus,
  getPartner,
  getRegistrationOptions,
  rejectPartner,
  updatePartner,
  type PartnerStatus,
} from "../api/client";
import { onboardingRequest } from "../features/onboarding/api";
import { useAuth } from "../features/auth/AuthContext";

export function PartnerDetailPage() {
  const { partnerId = "" } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const partner = useQuery({ queryKey: ["partner", partnerId], queryFn: () => getPartner(partnerId), enabled: Boolean(partnerId) });
  const options = useQuery({ queryKey: ["registration-options"], queryFn: getRegistrationOptions });
  const isAdmin = user?.roles.includes("TCG_ADMIN") || user?.is_superuser;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["partner", partnerId] });
  const startReview = useMutation({ mutationFn: () => onboardingRequest("/partners/" + partnerId + "/start", undefined, {}), onSuccess: refresh });
  const approve = useMutation({ mutationFn: () => approvePartner(partnerId), onSuccess: refresh });
  const reject = useMutation({ mutationFn: (reason: string) => rejectPartner(partnerId, reason), onSuccess: refresh });
  const statusMutation = useMutation({ mutationFn: (value: PartnerStatus) => changePartnerStatus(partnerId, value), onSuccess: refresh });
  const update = useMutation({ mutationFn: (body: Record<string, unknown>) => updatePartner(partnerId, body), onSuccess: refresh });

  if (partner.isLoading) return <div className="page-loader">Loading partner…</div>;
  if (!partner.data) return <div className="workspace-page"><div className="form-alert form-alert--error">Partner could not be loaded.</div></div>;
  const value = partner.data;
  const requiresReview = value.capabilities.some(c => ["RESELLER", "REFERRAL"].includes(c.code));
  const canEdit = Boolean(isAdmin || (user?.partner_id === partnerId && user.roles.includes("PARTNER_ADMIN")));

  function approveRegistration() { approve.mutate(); }

  function rejectRegistration() {
    const reason = window.prompt("Rejection reason");
    if (reason) reject.mutate(reason);
  }

  function updateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    update.mutate({
      company_name: form.get("company_name"), legal_name: form.get("legal_name") || null,
      company_email: form.get("company_email"), website: form.get("website") || null,
      phone: form.get("phone") || null, address: form.get("address") || null,
      primary_contact_name: form.get("primary_contact_name"),
      primary_contact_email: form.get("primary_contact_email"),
      primary_contact_phone: form.get("primary_contact_phone") || null,
      country_codes: form.getAll("country_codes"),
      ...(isAdmin ? { capability_codes: form.getAll("capability_codes") } : {}),
    });
  }

  return (
    <div className="workspace-page">
      <header className="page-heading page-heading--row">
        <div><Link className="back-link" to="/partners">← Partners</Link><span className="eyebrow">{value.code ?? "Pending registration"}</span><h1>{value.company_name}</h1><p>{value.capabilities.map(item => item.name).join(", ")} · {value.countries.map((country) => country.name).join(", ")}</p></div>
        <span className={`status-pill status-pill--${value.status.toLowerCase()}`}>{value.status.replaceAll("_", " ")}</span>
      </header>

      {(approve.error || update.error || statusMutation.error || reject.error) && <p role="alert" className="form-alert form-alert--error">{(approve.error || update.error || statusMutation.error || reject.error)?.message}</p>}
      {value.rejection_reason && <div className="form-alert form-alert--error"><strong>Rejection reason:</strong> {value.rejection_reason}</div>}
      {startReview.error && <p role="alert">{startReview.error.message}</p>}
      {isAdmin && <section className="action-bar">
        <Link className="button-link" to="/onboarding-review">Open onboarding review</Link>
        <button type="button" disabled={startReview.isPending} onClick={() => {
          if (value.status !== "ACTIVE" || window.confirm("Start a new legal review? Partner access will be paused until documents and email are verified again.")) startReview.mutate();
        }}>{value.status === "ACTIVE" ? "Start a new legal review" : "Request document submission"}</button>
        {value.status === "PENDING_APPROVAL" && !requiresReview && <><button type="button" onClick={approveRegistration}>Approve</button><button className="button-danger" type="button" onClick={rejectRegistration}>Reject</button></>}
        {value.status === "ACTIVE" && <button className="button-secondary" type="button" onClick={() => statusMutation.mutate("SUSPENDED")}>Suspend access</button>}
        {(value.status === "SUSPENDED" || value.status === "INACTIVE") && <button type="button" onClick={() => statusMutation.mutate("ACTIVE")}>Reactivate</button>}
      </section>}

      <div className="detail-grid">
        <section className="content-card detail-card"><span className="status-kicker">Company</span><h2>Profile</h2><dl>
          <div><dt>Legal name</dt><dd>{value.legal_name ?? "—"}</dd></div><div><dt>Company email</dt><dd>{value.company_email}</dd></div>
          <div><dt>Website</dt><dd>{value.website ? <a href={value.website}>{value.website}</a> : "—"}</dd></div><div><dt>Phone</dt><dd>{value.phone ?? "—"}</dd></div>
          <div className="field-wide"><dt>Address</dt><dd>{value.address ?? "—"}</dd></div>
        </dl></section>
        <section className="content-card detail-card"><span className="status-kicker">Program</span><h2>Classification</h2><dl>
          <div><dt>Capabilities</dt><dd>{value.capabilities.map(item => item.name).join(", ")}</dd></div>
          <div className="field-wide"><dt>Countries</dt><dd>{value.countries.map((country) => country.name).join(", ")}</dd></div>
        </dl></section>
        <section className="content-card detail-card"><span className="status-kicker">Primary contact</span><h2>{value.primary_contact_name}</h2><dl>
          <div><dt>Email</dt><dd>{value.primary_contact_email}</dd></div><div><dt>Phone</dt><dd>{value.primary_contact_phone ?? "—"}</dd></div>
        </dl><Link className="text-link" to={`/partners/${value.id}/users`}>Manage partner users →</Link></section>
      </div>
      {canEdit && <details className="content-card edit-panel"><summary>Edit partner profile</summary><form className="partner-form" onSubmit={updateProfile}><div className="form-grid">
        <label>Company name<input name="company_name" defaultValue={value.company_name} required /></label><label>Legal name<input name="legal_name" defaultValue={value.legal_name ?? ""} /></label>
        <label>Company email<input name="company_email" type="email" defaultValue={value.company_email} required /></label><label>Website<input name="website" type="url" defaultValue={value.website ?? ""} /></label>
        <label>Phone<input name="phone" defaultValue={value.phone ?? ""} /></label><label>Countries<select name="country_codes" multiple size={5} defaultValue={value.countries.map((country) => country.code)}>{options.data?.countries.map((country) => <option value={country.code} key={country.id}>{country.name}</option>)}</select></label>
        {isAdmin && <label>Capabilities<select name="capability_codes" multiple required size={3} defaultValue={value.capabilities.map(item => item.code)}>{options.data?.partner_types.map(item => <option value={item.code} key={item.id}>{item.name}</option>)}</select></label>}
        <label>Primary contact<input name="primary_contact_name" defaultValue={value.primary_contact_name} required /></label><label>Contact email<input name="primary_contact_email" type="email" defaultValue={value.primary_contact_email} required /></label>
        <label>Contact phone<input name="primary_contact_phone" defaultValue={value.primary_contact_phone ?? ""} /></label><label className="field-wide">Address<textarea name="address" rows={3} defaultValue={value.address ?? ""} /></label>
      </div><div className="form-actions"><button type="submit" disabled={update.isPending}>{update.isPending ? "Saving…" : "Save profile"}</button></div></form></details>}
    </div>
  );
}
