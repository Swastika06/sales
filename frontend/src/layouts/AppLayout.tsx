import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { Icon, TcgLogo } from "../features/portal/Icons";

function WorkspaceLink({ to, icon, children }: { to: string; icon: string; children: string }) {
  return <NavLink className={({ isActive }) => isActive ? "active" : undefined} to={to}>
    <span className="sidebar-nav-icon"><Icon name={icon} size={17} /></span>
    <span>{children}</span>
  </NavLink>;
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const isTcg = user?.is_superuser || user?.roles.some(role => ["TCG_ADMIN", "TCG_SALES"].includes(role));
  const canReview = user?.is_superuser || user?.roles.some(role => ["TCG_ADMIN", "TCG_LEGAL"].includes(role));
  const legalOnly = user?.roles.includes("TCG_LEGAL") && !isTcg;

  return (
    <div className="workspace">
      <aside className="sidebar">
        <Link className="brand brand--sidebar" to="/dashboard" aria-label="TCG Digital partner workspace home">
          <TcgLogo />
          <span className="workspace-brand-symbol" aria-hidden="true">T</span>
          <span className="workspace-brand-copy"><strong>Partner</strong><small>Workspace</small></span>
        </Link>
        <span className="sidebar-section-label">Workspace</span>
        <nav aria-label="Primary navigation">
          {canReview && <WorkspaceLink to="/onboarding-review" icon="shield">Onboarding review</WorkspaceLink>}
          {!legalOnly && <>
            <WorkspaceLink to="/dashboard" icon="layers">Overview</WorkspaceLink>
            <WorkspaceLink to={isTcg ? "/partners" : `/partners/${user?.partner_id ?? ""}`} icon="people">
              {isTcg ? "Partners" : "Company profile"}
            </WorkspaceLink>
            {user?.partner_id && <WorkspaceLink to={`/partners/${user.partner_id}/users`} icon="people">Users</WorkspaceLink>}
            {isTcg && <WorkspaceLink to="/products" icon="spark">Products & SKUs</WorkspaceLink>}
            <WorkspaceLink to="/pricing" icon="growth">Pricing</WorkspaceLink>
            <WorkspaceLink to="/documents" icon="book">Documents</WorkspaceLink>
            <WorkspaceLink to="/deals" icon="briefcase">Deals & pipeline</WorkspaceLink>
            <WorkspaceLink to="/commercial-model" icon="network">{isTcg ? "Commercial model" : "My commissions"}</WorkspaceLink>
            <WorkspaceLink to="/commercial" icon="layers">Quote to order</WorkspaceLink>
            <WorkspaceLink to="/system" icon="globe">System status</WorkspaceLink>
          </>}
        </nav>
        <div className="sidebar-user">
          <span className="avatar">{user?.full_name.charAt(0).toUpperCase()}</span>
          <span><strong>{user?.full_name}</strong><small>{user?.roles[0]?.replaceAll("_", " ")}</small></span>
          <button className="button-quiet" type="button" onClick={logout}>Sign out <Icon name="diagonal" size={12} /></button>
        </div>
      </aside>
      <main className="workspace-main">
        <header className="workspace-topbar">
          <div><span>TCG Partner Network</span><strong>Partner workspace</strong></div>
          <span className="workspace-secure"><Icon name="lock" size={14} /> Secure workspace</span>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
