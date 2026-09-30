import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getPartners, type PartnerStatus } from "../api/client";
import { useAuth } from "../features/auth/AuthContext";

const statusLabels: Record<PartnerStatus, string> = {
  PENDING_APPROVAL: "Pending approval",
  ACTIVE: "Active",
  REJECTED: "Rejected",
  SUSPENDED: "Suspended",
  INACTIVE: "Inactive",
};

export function PartnersPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  const partners = useQuery({
    queryKey: ["partners", search, status],
    queryFn: () => getPartners(params.toString()),
  });

  return (
    <div className="workspace-page">
      <header className="page-heading page-heading--row">
        <div><span className="eyebrow">Partner network</span><h1>Partners</h1><p>{partners.data?.total ?? 0} organizations in the current view</p></div>
        {(user?.is_superuser || user?.roles.includes("TCG_ADMIN")) && <Link className="button-link" to="/partners/new">Create partner</Link>}
      </header>
      <section className="content-card table-card">
        <div className="table-toolbar">
          <label className="search-field"><span className="sr-only">Search partners</span><input type="search" placeholder="Search name or code" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
        {partners.isLoading && <p className="notice">Loading partners…</p>}
        {partners.isError && <p className="notice notice--error">Could not load partners.</p>}
        {partners.data && partners.data.items.length === 0 && <div className="empty-state"><h2>No partners found</h2><p>Try changing the filters or create the first partner.</p></div>}
        {partners.data && partners.data.items.length > 0 && (
          <div className="table-scroll"><table><thead><tr><th>Partner</th><th>Capabilities</th><th>Territory</th><th>Status</th><th aria-label="Open" /></tr></thead><tbody>
            {partners.data.items.map((partner) => <tr key={partner.id}>
              <td><strong>{partner.company_name}</strong><small>{partner.code ?? "Awaiting approval"}</small></td>
              <td>{partner.capabilities.map(item => item.name).join(", ")}</td>
              <td>{partner.countries.map((country) => country.code).join(", ")}</td>
              <td><span className={`status-pill status-pill--${partner.status.toLowerCase()}`}>{statusLabels[partner.status]}</span></td>
              <td><Link className="row-link" to={`/partners/${partner.id}`} aria-label={`Open ${partner.company_name}`}>→</Link></td>
            </tr>)}
          </tbody></table></div>
        )}
      </section>
    </div>
  );
}
