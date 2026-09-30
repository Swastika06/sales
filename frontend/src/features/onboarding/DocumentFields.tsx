import { documentKinds, type DocumentDrafts, type DocumentKind, type Application } from "./api";

export function DocumentFields({ value, onChange, required, existing = [], disabled = false }: {
  value: DocumentDrafts; onChange: (value: DocumentDrafts) => void; required: DocumentKind[];
  existing?: Application["documents"]; disabled?: boolean;
}) {
  return <div className="onboarding-documents">
    <p>Upload PDF, JPG or PNG files, up to 10 MB each. These documents are shared with authorized reviewers.</p>
    {documentKinds.filter(([kind]) => required.includes(kind)).map(([kind, label]) => {
      const saved = existing.find(document => document.kind === kind);
      const draft = value[kind];
      return <fieldset key={kind} disabled={disabled}>
        <legend>{label}</legend>
        <label>{label} number<input value={draft?.number ?? saved?.number ?? ""} required maxLength={100}
          pattern={kind === "PAN" ? "[A-Za-z]{5}[0-9]{4}[A-Za-z]" : kind === "GSTIN" ? "[0-9]{2}[A-Za-z]{5}[0-9]{4}[A-Za-z][1-9A-Za-z][Zz][0-9A-Za-z]" : undefined}
          readOnly={Boolean(saved && !draft?.file)}
          onChange={event => onChange({ ...value, [kind]: { ...draft, number: event.target.value.toUpperCase() } })} /></label>
        <label>{saved ? "Replace document" : "Upload document"}<input type="file" accept=".pdf,.png,.jpg,.jpeg" required={!saved && !draft?.file}
          onChange={event => {
            const file = event.target.files?.[0];
            const invalid = Boolean(file && (file.size > 10 * 1024 * 1024 || file.size === 0));
            event.target.setCustomValidity(invalid ? "Select a non-empty file up to 10 MB." : "");
            if (invalid) { event.target.reportValidity(); return; }
            onChange({ ...value, [kind]: { number: draft?.number ?? saved?.number ?? "", file } });
          }} /></label>
        {(draft?.file || saved) && <small>Selected: {draft?.file?.name ?? saved?.filename}</small>}
      </fieldset>;
    })}
  </div>;
}
