import { type FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../features/auth/AuthContext";

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (auth.isLoading) return <div className="page-loader" role="status">Loading your workspace...</div>;
  if (auth.isAuthenticated) return <Navigate to="/dashboard" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await auth.login(email, password);
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      navigate(from ?? "/dashboard", { replace: true });
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-copy">
        <span className="eyebrow">Partner workspace</span>
        <h1>One place to grow every partnership.</h1>
        <p>Manage partner access, opportunities, pricing, and delivery with TCG Digital.</p>
      </section>
      <form className="auth-card" onSubmit={(event) => void submit(event)}>
        <div><span className="status-kicker">Welcome back</span><h2>Sign in</h2></div>
        {error && <div className="form-alert form-alert--error" role="alert">{error}</div>}
        <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="username" /></label>
        <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" /></label>
        <button type="submit" disabled={submitting}>{submitting ? "Signing in…" : "Sign in"}</button>
        <p className="form-footnote"><Link to="/onboarding">Track application or activate account</Link></p>
        <p className="form-footnote">New partner? <Link to="/register">Register your company</Link></p>
      </form>
    </div>
  );
}

