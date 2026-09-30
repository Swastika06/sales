import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { engagementModels, getPartners, getResolvedPricing, type EngagementModel } from "../api/client";
import { useAuth } from "../features/auth/AuthContext";

export function PricingPage() {
  const { user } = useAuth();
  const internal = Boolean(user?.is_superuser || user?.roles.some(role => role.startsWith("TCG_")));
  const [model, setModel] = useState<EngagementModel>(internal ? "DIRECT" : "RESELLER");
  const [partner, setPartner] = useState(user?.partner_id ?? "");
  const partners = useQuery({ queryKey: ["partners", "pricing"], queryFn: () => getPartners("status=ACTIVE&page_size=100"), enabled: internal });
  const prices = useQuery({ queryKey: ["pricing", model, partner], queryFn: () => getResolvedPricing(model, partner || undefined), enabled: model === "DIRECT" || Boolean(partner) });
  return <div className="workspace-page"><header className="page-heading"><span className="eyebrow">Commercial catalog</span><h1>Pricing by engagement</h1><p>Catalog and approved agreement prices. Opportunity and contract terms resolve when a quote is created.</p></header>
    <section className="content-card compact-form"><div className="form-grid"><label>Engagement model<select value={model} onChange={e => setModel(e.target.value as EngagementModel)}>{engagementModels.filter(m => internal || ["RESELLER", "SYSTEM_INTEGRATOR"].includes(m)).map(m => <option key={m}>{m}</option>)}</select></label>{internal && <label>Partner<select value={partner} onChange={e => setPartner(e.target.value)}><option value="">No commercial partner</option>{partners.data?.items.filter(p => model === "DIRECT" || p.capabilities.some(c => c.code === model)).map(p => <option key={p.id} value={p.id}>{p.company_name}</option>)}</select></label>}</div>{internal && <Link to="/commercial-model">Manage versioned commercial terms →</Link>}</section>
    {prices.error && <p role="alert" className="form-alert form-alert--error">{prices.error.message}</p>}
    <section className="content-card table-card"><div className="table-scroll"><table><thead><tr><th>Product / SKU</th><th>Unit</th><th>Price (USD)</th><th>Resolved sources</th></tr></thead><tbody>{prices.data?.items.map(item => <tr key={item.sku_id}><td><strong>{item.product_name}</strong><small>{item.sku_code} · {item.sku_name}</small></td><td>{item.unit}</td><td>${item.final_price}</td><td>{item.breakdown ? Object.keys(item.breakdown.sources).join(", ") : "Shared price"}</td></tr>)}</tbody></table></div>{!prices.data?.items.length && <p className="empty-state">{prices.isFetching ? "Loading prices…" : "Select an eligible engagement and partner to view available prices."}</p>}</section>
  </div>;
}
