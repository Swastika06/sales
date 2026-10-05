import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { apiRequest, type CurrentUser } from "../api/client";
import { useAuth } from "../features/auth/AuthContext";

type StaffUser = CurrentUser & { created_at: string; mail_status: string | null };
type StaffRole = { code: string; name: string };

export function StaffUsersPage() {
  const { user } = useAuth();
  const admin = Boolean(user?.is_superuser || user?.roles.includes("TCG_ADMIN"));
  const cache = useQueryClient();
  const [message, setMessage] = useState("");
  const users = useQuery({ queryKey: ["staff-users"], queryFn: () => apiRequest<StaffUser[]>("/staff-users"), enabled: admin });
  const roles = useQuery({ queryKey: ["staff-roles"], queryFn: () => apiRequest<StaffRole[]>("/staff-users/roles"), enabled: admin });
  const create = useMutation({ mutationFn: (body: unknown) => apiRequest<StaffUser>("/staff-users", { method: "POST", body: JSON.stringify(body) }), onSuccess: async () => { await cache.invalidateQueries({ queryKey: ["staff-users"] }); } });
  const resend = useMutation({
    mutationFn: (id: string) => apiRequest<StaffUser>(`/staff-users/${id}/invitation`, { method: "POST" }),
    onSuccess: async (account) => {
      setMessage("A new temporary password has been queued for " + account.email + ". The previous temporary password is no longer valid.");
      await cache.invalidateQueries({ queryKey: ["staff-users"] });
    },
  });
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setMessage("");
    try {
      const account = await create.mutateAsync(Object.fromEntries(new FormData(form)));
      form.reset();
      setMessage("Account created for " + account.email + ". A temporary login password has been queued for email delivery.");
    } catch { /* The mutation error is shown below. */ }
  }
  if (!admin) return <div className="workspace-page"><p>Administrator access is required to manage staff users.</p></div>;
  const error = create.error ?? resend.error ?? users.error ?? roles.error;
  return <div className="workspace-page">
    <header className="page-heading"><span className="eyebrow">Access management</span><h1>Staff users</h1><p>Add internal users and assign their workspace role.</p></header>
    {error && <p className="form-alert form-alert--error" role="alert">{error.message}</p>}
    {message && <p className="notice" role="status">{message}</p>}
    <div className="users-layout">
      <section className="content-card table-card"><div className="card-heading"><h2>Internal team</h2><button className="button-secondary" disabled={users.isFetching} onClick={() => void users.refetch()}>Refresh users</button></div>
        {users.isLoading && <p role="status">Loading staff users...</p>}
        {users.data?.length === 0 && <p>No staff users yet.</p>}
        {users.data?.map(member => <div className="user-row" key={member.id}><span className="avatar">{member.full_name.charAt(0)}</span><span><strong>{member.full_name}</strong><small>{member.email}</small><small>{member.roles.map(role => roles.data?.find(item => item.code === role)?.name ?? role.replaceAll("_", " ")).join(", ")}</small><small>{member.must_change_password ? "First-login password change pending" : "Password set"}{member.mail_status ? " - Email: " + member.mail_status : ""}</small></span><span className="status-pill">{member.is_active ? "Active" : "Inactive"}</span>{member.is_active && member.must_change_password && <button className="button-secondary" disabled={resend.isPending} onClick={() => { setMessage(""); resend.mutate(member.id); }}>Send new invitation</button>}</div>)}
      </section>
      <form className="content-card compact-form" onSubmit={event => void submit(event)}>
        <h2>Add staff user</h2><p>We will email a temporary password. The user must change it on first login before accessing the workspace.</p>
        <label>Full name<input name="full_name" autoComplete="off" required minLength={2} maxLength={200} /></label>
        <label>Email<input name="email" type="email" autoComplete="off" required /></label>
        <label>Role<select name="role_code" required defaultValue="" disabled={!roles.data}><option value="" disabled>Select a role</option>{roles.data?.map(role => <option key={role.code} value={role.code}>{role.name}</option>)}</select></label>
        <button disabled={create.isPending || !roles.data}>{create.isPending ? "Creating account..." : "Create staff account"}</button>
      </form>
    </div>
  </div>;
}
