import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  ApiError,
  createPartner,
  getRegistrationOptions,
  registerPartner,
  type Partner,
} from "../api/client";

export function RegisterPage({ admin = false }: { admin?: boolean }) {
  const navigate = useNavigate();
  const options = useQuery({ queryKey: ["registration-options"], queryFn: getRegistrationOptions });
  const [created, setCreated] = useState<Partner | null>(null);
  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => admin ? createPartner(body) : registerPartner(body),
    onSuccess: (partner) => {
      if (admin) navigate(`/partners/${partner.id}`);
      else setCreated(partner);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    mutation.mutate({
      company_name: form.get("company_name"),
      legal_name: form.get("legal_name") || null,
      capability_codes: form.getAll("capability_codes"),
      country_codes: form.getAll("country_codes"),
      website: form.get("website") || null,
      company_email: form.get("company_email"),
      phone: form.get("phone") || null,
      address: form.get("address") || null,
      primary_contact_name: form.get("primary_contact_name"),
      primary_contact_email: form.get("primary_contact_email"),
      primary_contact_phone: form.get("primary_contact_phone") || null,
      password: form.get("password"),
    });
  }

  if (created) {
    return (
      <div className="public-form-page">
        <section className="success-card"><span className="success-mark">✓</span><h1>Registration submitted</h1><p>TCG will review your application. Your reference is <strong>{created.id.slice(0, 8).toUpperCase()}</strong>.</p><Link className="button-link" to="/login">Return to sign in</Link></section>
      </div>
    );
  }

  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? "Unable to save partner" : null;
  return (
    <div className={admin ? "workspace-page" : "public-form-page"}>
      <header className="page-heading form-page-heading">
        <div><span className="eyebrow">{admin ? "Partner management" : "Join the network"}</span><h1>{admin ? "Create a partner" : "Register your company"}</h1><p>{admin ? "Create an active partner and its first administrator." : "Tell us about your company. Access begins after TCG approval."}</p></div>
        {!admin && <Link to="/login">Already registered? Sign in</Link>}
      </header>
      <form className="content-card partner-form" onSubmit={submit}>
        {error && <div className="form-alert form-alert--error">{error}</div>}
        <fieldset><legend>Company</legend><div className="form-grid">
          <label>Company name<input name="company_name" required minLength={2} /></label>
          <label>Legal name<input name="legal_name" /></label>
          <label>Capabilities<select name="capability_codes" required multiple size={3}>{options.data?.partner_types.map((item) => <option key={item.id} value={item.code}>{item.name}</option>)}</select></label>
          <label>Countries<select name="country_codes" required multiple size={5}>{options.data?.countries.map((item) => <option key={item.id} value={item.code}>{item.name}</option>)}</select><small>Use Ctrl/Cmd to select more than one.</small></label>
          <label>Website<input name="website" type="url" placeholder="https://" /></label>
          <label>Company email<input name="company_email" type="email" required /></label>
          <label>Company phone<input name="phone" /></label>
          <label className="field-wide">Address<textarea name="address" rows={3} /></label>
        </div></fieldset>
        <fieldset><legend>Primary administrator</legend><div className="form-grid">
          <label>Full name<input name="primary_contact_name" required minLength={2} /></label>
          <label>Email<input name="primary_contact_email" type="email" required /></label>
          <label>Phone<input name="primary_contact_phone" /></label>
          <label>Temporary password<input name="password" type="password" required minLength={12} autoComplete="new-password" /><small>At least 12 characters.</small></label>
        </div></fieldset>
        <div className="form-actions"><button type="submit" disabled={mutation.isPending || options.isLoading}>{mutation.isPending ? "Submitting…" : admin ? "Create active partner" : "Submit registration"}</button></div>
      </form>
    </div>
  );
}

