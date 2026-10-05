import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { saveAccessToken } from "./session";
import { useAuth } from "./AuthContext";

export function FirstLoginPassword() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    if (fields.get("new_password") !== fields.get("confirmation")) {
      setError("Your passwords do not match."); return;
    }
    setBusy(true); setError("");
    try {
      const result = await apiRequest<{ access_token: string }>("/auth/change-password", {
        method: "POST", body: JSON.stringify({ current_password: fields.get("current_password"), new_password: fields.get("new_password") })
      });
      queryClient.clear();
      saveAccessToken(result.access_token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to change password. Try again.");
    } finally { setBusy(false); }
  }
  return <section className="p-container onboarding-public">
    <h1>Set your workspace password.</h1>
    <p>Replace your emailed temporary password before accessing your workspace.</p>
    {error && <p className="p-form-error" role="alert">{error}</p>}
    <form className="onboarding-form" onSubmit={event => void submit(event)}>
      <label>Temporary password<input name="current_password" type="password" autoComplete="current-password" required maxLength={128} /></label>
      <label>New password<input name="new_password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} /></label>
      <p>Use at least 12 characters.</p>
      <label>Confirm new password<input name="confirmation" type="password" autoComplete="new-password" required minLength={12} maxLength={128} /></label>
      <button className="p-button" disabled={busy}>{busy ? "Saving..." : "Change password and continue"}</button>
      <button className="p-button p-button-outline" type="button" disabled={busy} onClick={auth.logout}>Sign out</button>
    </form>
  </section>;
}
