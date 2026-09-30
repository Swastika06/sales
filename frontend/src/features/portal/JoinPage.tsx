import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, getRegistrationOptions } from "../../api/client";
import { Icon } from "./Icons";
import { partnerPaths } from "./portalData";
import { DocumentFields } from "../onboarding/DocumentFields";
import { documentKinds, requiresDocuments, submitOnboarding, type DocumentDrafts, type ApplicationSession } from "../onboarding/api";

export function JoinPage() {
  const [documents, setDocuments] = useState<DocumentDrafts>({});
  const draft = useRef<ApplicationSession | null>(null);
  const [additional, setAdditional] = useState<string[]>([]);
  const [params] = useSearchParams();
  const initialType = partnerPaths.some(p => p.code === params.get("type")) ? params.get("type")! : "";
  const [step, setStep] = useState(0);
  const [values, setValues] = useState({ company_name: "", company_email: "", website: "", country: "", partner_type_code: initialType, primary_contact_name: "", primary_contact_email: "", primary_contact_phone: "", password: "", confirm_password: "" });
  const [consent, setConsent] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const confirmation = useRef<HTMLInputElement>(null);
  useEffect(() => {
    confirmation.current?.setCustomValidity(values.confirm_password === values.password ? "" : "Your passwords do not match.");
  }, [values.password, values.confirm_password, step]);
  const options = useQuery({ queryKey: ["registration-options"], queryFn: getRegistrationOptions, retry: 1 });
  const requiredDocuments = requiresDocuments([values.partner_type_code, ...additional]) ? documentKinds.map(([kind]) => kind) : [];
  const mutation = useMutation({ mutationFn: (payload: unknown) => submitOnboarding(payload, documents, draft.current, session => { draft.current = session; }) });
  useEffect(() => { if (mutation.isSuccess) setValues(previous => ({ ...previous, password: "", confirm_password: "" })); }, [mutation.isSuccess]);
  const update = (name: keyof typeof values, value: string) => setValues(v => ({ ...v, [name]: value }));
  useEffect(() => { if (step > 0) heading.current?.focus(); }, [step]);
  useEffect(() => { if (mutation.isSuccess) heading.current?.focus(); }, [mutation.isSuccess]);
  function next(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (step < 3) { setStep(step + 1); return; }
    if (!consent || mutation.isPending || !options.data) return;
    mutation.mutate({
      company_name: values.company_name.trim(),
      company_email: values.company_email.trim(),
      website: values.website.trim() || null,
      capability_codes: [...new Set([values.partner_type_code, ...additional])],
      country_codes: [values.country],
      primary_contact_name: values.primary_contact_name.trim(),
      primary_contact_email: values.primary_contact_email.trim(),
      primary_contact_phone: values.primary_contact_phone.trim() || null,
      password: values.password,
    });
  }
  if (mutation.isSuccess) return <section className="p-container p-join-success"><div className="p-success-icon"><Icon name="check" size={34} /></div><span className="p-eyebrow">YOUR NEXT CHAPTER IS UNDERWAY</span><h1 tabIndex={-1} ref={heading}>You’re one step closer.</h1><p>Thank you, {values.primary_contact_name}. We’ve received the application for <strong>{values.company_name}</strong>.</p><div className="p-reference"><span>APPLICATION REFERENCE</span><strong>{mutation.data.id.slice(0, 8).toUpperCase()}</strong><span className="p-pending-badge">Pending review</span></div><div className="p-next-steps"><h2>What happens next?</h2><ol><li><strong>We review your application.</strong><span>Our team checks your company details and partnership interests.</span></li><li><strong>Legal verifies your documents.</strong><span>An assigned legal reviewer checks your submission and may request corrections.</span></li><li><strong>Your partnership begins.</strong><span>After legal approval, an activation code is emailed to you. Verify it to access your workspace.</span></li></ol></div><div className="p-hero-buttons"><Link to="/" className="p-button p-button-outline">Back to home</Link><Link to="/onboarding" className="p-button">Track application <Icon size={17} /></Link></div></section>;

  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? "We couldn’t submit your application. Please try again. Your details are still here." : null;
  return <section className="p-join-page p-container">
    <div className="p-join-intro"><Link className="p-breadcrumb" to="/">Partner Network <span>/ Join now</span></Link><span className="p-eyebrow">LET’S GROW TOGETHER</span><h1>Great things start<br />with a hello.</h1><p>Tell us a little about your business.<br />We’ll explore what we can achieve together.</p><div className="p-join-promise"><span className="p-icon-tile"><Icon name="people" /></span><div><strong>A partnership built around you</strong><p>Our team reviews every application to find the right fit for your business.</p></div></div><div className="p-join-promise"><span className="p-icon-tile"><Icon name="shield" /></span><div><strong>A clear path forward</strong><p>Apply, connect with TCG, and get access to your workspace after approval.</p></div></div><div className="p-join-help">Already part of the network?<Link className="p-text-link" to="/login">Sign in to your workspace <Icon size={15} /></Link></div><span className="p-join-decoration" aria-hidden="true">together.</span></div>
    <div className="p-application">
      <ol className="p-form-progress" aria-label="Application progress">{["Company", "Your details", "Documents", "Review"].map((label, i) => <li key={label} className={i <= step ? "is-active" : ""}><button disabled={i > step || mutation.isPending || Boolean(draft.current)} onClick={() => setStep(i)} aria-current={step === i ? "step" : undefined}><span>{i < step ? <Icon name="check" size={14} /> : i + 1}</span>{label}</button></li>)}</ol>
      <form className="p-join-form" onSubmit={next}>
        <span className="p-mini-label">STEP 0{step + 1} OF 04</span><h2 ref={heading} tabIndex={-1}>{["First, your company.", "Nice to meet you.", "Company documents.", "Ready for what’s next?"][step]}</h2><p className="p-form-description">{["Introduce us to your business and choose your partnership path.", "You’ll be the primary contact and administrator for your company.", "Upload documents for legal verification.", "Check your details before sending your application to TCG."][step]}</p>
        {options.isError && <div className="p-form-error" role="alert">We couldn’t load the available partnership types and countries. Please try again.<button type="button" onClick={() => void options.refetch()} disabled={options.isFetching}>{options.isFetching ? "Retrying…" : "Retry loading options"}</button></div>}
        {step === 0 && <div className="p-form-fields">
          <label>Company name <span>*</span><input name="company_name" autoComplete="organization" placeholder="Your company name" required minLength={2} maxLength={200} value={values.company_name} onChange={e => update("company_name", e.target.value)} /></label>
          <label>Company email <span>*</span><input name="company_email" type="email" autoComplete="email" placeholder="hello@company.com" required value={values.company_email} onChange={e => update("company_email", e.target.value)} /></label>
          <label>Company website <small>Optional</small><input name="website" type="url" placeholder="https://yourcompany.com" value={values.website} onChange={e => update("website", e.target.value)} /></label>
          <label>Country / region <span>*</span><select name="country" autoComplete="country" value={values.country} onChange={e => update("country", e.target.value)} required disabled={!options.data}><option value="">{options.isLoading ? "Loading countries…" : "Select your country"}</option>{options.data?.countries.map(country => <option key={country.code} value={country.code}>{country.name}</option>)}</select></label>
          <label className="p-field-wide">How would you like to partner? <span>*</span><select name="partner_type_code" required value={values.partner_type_code} onChange={e => update("partner_type_code", e.target.value)} disabled={!options.data}><option value="">Select a partnership path</option>{options.data?.partner_types.map(type => <option key={type.code} value={type.code}>{type.name}</option>)}</select><small>Not sure? <Link to="/partner-levels" target="_blank" rel="noreferrer">Compare the partnership paths <Icon name="diagonal" size={11} /></Link></small></label>
        </div>}
        {step === 0 && <fieldset><legend>Additional capabilities (optional)</legend>{options.data?.partner_types.filter(item => item.code !== values.partner_type_code).map(item => <label className="p-consent" key={item.id}><input type="checkbox" checked={additional.includes(item.code)} onChange={e => setAdditional(e.target.checked ? [...additional, item.code] : additional.filter(code => code !== item.code))} />{item.name}</label>)}</fieldset>}
        {step === 1 && <div className="p-form-fields">
          <label className="p-field-wide">Full name <span>*</span><input name="primary_contact_name" autoComplete="name" placeholder="First and last name" required minLength={2} maxLength={200} value={values.primary_contact_name} onChange={e => update("primary_contact_name", e.target.value)} /></label>
          <label className="p-field-wide">Work email <span>*</span><input name="primary_contact_email" type="email" autoComplete="username" placeholder="you@company.com" required value={values.primary_contact_email} onChange={e => update("primary_contact_email", e.target.value)} /><small>You’ll use this email to sign in after approval.</small></label>
          <label className="p-field-wide">Phone number <small>Optional</small><input name="primary_contact_phone" type="tel" autoComplete="tel" placeholder="+1 555 000 0000" maxLength={50} value={values.primary_contact_phone} onChange={e => update("primary_contact_phone", e.target.value)} /></label>
          <label className="p-field-wide">Create a password <span>*</span><span className="p-password-field"><input name="password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={12} maxLength={128} value={values.password} onChange={e => update("password", e.target.value)} aria-describedby="password-help" /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword(!showPassword)}>{showPassword ? "Hide" : "Show"}</button></span><small id="password-help">Use at least 12 characters.</small></label>
          <label className="p-field-wide">Confirm password <span>*</span><input ref={confirmation} name="confirm_password" type="password" autoComplete="new-password" required value={values.confirm_password} onChange={e => { update("confirm_password", e.target.value); e.target.setCustomValidity(e.target.value === values.password ? "" : "Your passwords don’t match."); }} onFocus={e => e.target.setCustomValidity(e.target.value === values.password ? "" : "Your passwords don’t match.")} /></label>
        </div>}
        {step === 2 && (requiredDocuments.length ? <DocumentFields value={documents} onChange={setDocuments} required={requiredDocuments} disabled={mutation.isPending} /> : <p>No documents are required for the selected capabilities.</p>)}
        {step === 3 && <div className="p-review"><div className="p-review-heading"><h3>Company information</h3><button type="button" disabled={Boolean(draft.current)} onClick={() => setStep(0)}>Edit</button></div><dl><dt>Company</dt><dd>{values.company_name}</dd><dt>Company email</dt><dd>{values.company_email}</dd><dt>Country / region</dt><dd>{options.data?.countries.find(c => c.code === values.country)?.name}</dd><dt>Partnership</dt><dd>{options.data?.partner_types.filter(t => t.code === values.partner_type_code || additional.includes(t.code)).map(t => t.name).join(", ")}</dd>{values.website && <><dt>Website</dt><dd>{values.website}</dd></>}</dl><div className="p-review-heading"><h3>Primary contact</h3><button type="button" disabled={Boolean(draft.current)} onClick={() => setStep(1)}>Edit</button></div><dl><dt>Name</dt><dd>{values.primary_contact_name}</dd><dt>Email</dt><dd>{values.primary_contact_email}</dd>{values.primary_contact_phone && <><dt>Phone</dt><dd>{values.primary_contact_phone}</dd></>}</dl>{requiredDocuments.length > 0 && <><div className="p-review-heading"><h3>Documents</h3><button type="button" disabled={Boolean(draft.current)} onClick={() => setStep(2)}>Edit</button></div><dl>{requiredDocuments.map(kind => <div key={kind}><dt>{kind.replaceAll("_", " ")}</dt><dd>{documents[kind]?.file?.name ?? "Missing document"}</dd></div>)}</dl></>}<label className="p-consent"><input type="checkbox" required checked={consent} onChange={e => setConsent(e.target.checked)} /><span>I am authorized to apply on behalf of my company and agree that TCG may contact me about this application.</span></label></div>}
        {error && <div className="p-form-error" role="alert">{error}<p><Link to="/onboarding">Resume an existing application</Link></p></div>}
        <div className="p-form-actions">{step > 0 && !draft.current && <button type="button" className="p-button p-button-outline" onClick={() => setStep(step - 1)} disabled={mutation.isPending}><Icon size={16} style={{ transform: "rotate(180deg)" }} />Back</button>}<button type="submit" className="p-button" disabled={mutation.isPending || !options.data || options.isError}>{mutation.isPending ? "Submitting application…" : step === 3 ? "Submit application" : "Continue"}<Icon size={17} /></button></div>
        <p className="p-form-footnote"><Icon name="lock" size={13} />Your details are used to review your partner application.</p>
      </form>
    </div>
  </section>;
}


