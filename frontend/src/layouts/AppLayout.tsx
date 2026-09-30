import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

export function AppLayout() {
  const { user, logout } = useAuth();
  const isTcg = user?.is_superuser || user?.roles.some(role => ["TCG_ADMIN", "TCG_SALES"].includes(role));
  const canReview = user?.is_superuser || user?.roles.some(role => ["TCG_ADMIN", "TCG_LEGAL"].includes(role));
  const legalOnly = user?.roles.includes("TCG_LEGAL") && !isTcg;

  return (
    <div className="workspace">
      <aside className="sidebar">
        <NavLink className="brand brand--sidebar" to="/dashboard">
          <span className="brand-mark" aria-hidden="true">T</span>
          <span><strong>TCG Digital</strong><small>Partner Portal</small></span>
        </NavLink>
        <nav aria-label="Primary navigation">
          {canReview && <NavLink to="/onboarding-review">Onboarding review</NavLink>}
          {!legalOnly && <><NavLink to="/dashboard">Overview</NavLink>
          <NavLink to={isTcg ? "/partners" : `/partners/${user?.partner_id ?? ""}`}>
            {isTcg ? "Partners" : "Company profile"}
          </NavLink>
          {user?.partner_id && <NavLink to={`/partners/${user.partner_id}/users`}>Users</NavLink>}
          {isTcg && <NavLink to="/products">Products & SKUs</NavLink>}
          <NavLink to="/pricing">Pricing</NavLink>
          <NavLink to="/documents">Documents</NavLink>
          <NavLink to="/deals">Deals & pipeline</NavLink>
          <NavLink to="/commercial-model">{isTcg ? "Commercial model" : "My commissions"}</NavLink>
          <NavLink to="/commercial">Quote to order</NavLink>
          <NavLink to="/system">System status</NavLink></>}
        </nav>
        <div className="sidebar-user">
          <span className="avatar">{user?.full_name.charAt(0).toUpperCase()}</span>
          <span><strong>{user?.full_name}</strong><small>{user?.roles[0]?.replaceAll("_", " ")}</small></span>
          <button className="button-quiet" type="button" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="workspace-main"><Outlet /></main>
    </div>
  );
}
