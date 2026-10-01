import { type FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../features/auth/AuthContext";
import { Icon } from "../features/portal/Icons";

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
    <div className="auth-page p-login-page">
      <section className="auth-copy p-login-intro">
        <span className="p-eyebrow"><span className="p-eyebrow-line" />Partner workspace</span>
        <h1>Welcome back to the <em>network.</em></h1>
        <p>Continue building opportunities, managing pricing, and delivering outcomes with TCG Digital.</p>
        <div className="p-login-benefits" aria-label="Workspace capabilities">
          <span><Icon name="people" size={18} />Partner access</span>
          <span><Icon name="growth" size={18} />Opportunities</span>
          <span><Icon name="briefcase" size={18} />Delivery</span>
        </div>
        <div className="p-login-network" aria-hidden="true">
          <span className="p-login-orbit p-login-orbit-one" />
          <span className="p-login-orbit p-login-orbit-two" />
          <span className="p-login-node p-login-node-one" />
          <span className="p-login-node p-login-node-two" />
          <span className="p-login-node p-login-node-three" />
          <Icon name="network" size={48} />
        </div>
      </section>
      <form className="auth-card p-login-card" onSubmit={(event) => void submit(event)}>
        <div className="p-login-card-heading">
          <span className="status-kicker">Welcome back</span>
          <h2>Sign in</h2>
          <p>Use the credentials linked to your partner organization.</p>
        </div>
        {error && <div className="form-alert form-alert--error" role="alert">{error}</div>}
        <div className="p-login-fields">
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="username" placeholder="you@company.com" /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="current-password" placeholder="Enter your password" /></label>
        </div>
        <button className="p-button p-login-submit" type="submit" disabled={submitting}>
          <span>{submitting ? "Signing in..." : "Sign in"}</span><Icon size={17} />
        </button>
        <div className="p-login-links">
          <p className="form-footnote"><Link to="/onboarding">Track application or activate account</Link></p>
          <p className="form-footnote">New partner? <Link to="/register">Register your company</Link></p>
        </div>
      </form>
    </div>
  );
}

