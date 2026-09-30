import { useQuery } from "@tanstack/react-query";
import { commercial, dollars } from "../features/commercial/types";
import { Link } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

export function DashboardPage() {
  const { user } = useAuth();
  const internal = Boolean(user?.is_superuser || user?.roles.some(r => r.startsWith("TCG_")));
  const summary = useQuery({ queryKey: ["commercial", "summary"], queryFn: () => commercial<{ basis: string; opportunities: number; totals: Record<string, string>; undisclosed: Record<string, number> }>("/summary"), enabled: internal });
  const isTcgAdmin = user?.roles.includes("TCG_ADMIN");
  return (
    <div className="workspace-page">
      <header className="page-heading">
        <div><span className="eyebrow">Overview</span><h1>Good to see you, {user?.full_name.split(" ")[0]}.</h1></div>
      </header>
      <div className="summary-grid">
        <article><span>Access</span><strong>{user?.roles[0]?.replaceAll("_", " ")}</strong><p>Your active workspace role</p></article>
        <article><span>Organization</span><strong>{user?.partner_id ? "Partner" : "TCG Digital"}</strong><p>Current data scope</p></article>
        <article><span>Account</span><strong>Active</strong><p>{user?.email}</p></article>
      </div>
      {summary.data && <section><h2>Commercial overview</h2><p>{summary.data.basis} · {summary.data.opportunities} opportunities</p><div className="commercial-totals">{[["customer_value", "Customer value"], ["tcg_entitlement", "TCG entitlement"], ["partner_entitlement", "Partner benefit"], ["vendor_cost", "Vendor obligations"], ["commission_expense", "Forecast commission"]].map(([key, title]) => <div key={key}><small>{title}</small><strong>{dollars(summary.data.totals[key!])}</strong>{Boolean(summary.data.undisclosed[key!]) && <small>{summary.data.undisclosed[key!]} undisclosed; excluded from total</small>}</div>)}</div></section>}
      {summary.error && <p role="alert">{summary.error.message}</p>}
      <section className="content-card welcome-card">
        <div><span className="status-kicker">Partner network</span><h2>Partner Access & Management</h2><p>Review registrations, maintain partner profiles, and control team access from one governed workspace.</p></div>
        <Link className="button-link" to={user?.partner_id ? `/partners/${user.partner_id}` : "/partners"}>
          {isTcgAdmin ? "Manage partners" : "View company"}
        </Link>
      </section>
      <div className="quick-links"><Link to="/commercial-model">{internal ? "Manage commercial models" : "View my forecasts and commissions"} →</Link><Link to="/pricing">View pricing →</Link>{!user?.partner_id && <Link to="/products">Manage product catalog →</Link>}</div>
    </div>
  );
}
