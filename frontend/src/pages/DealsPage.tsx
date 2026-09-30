import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { Link } from "react-router-dom";
import { engagementModels, type EngagementModel, ApiError, approveDeal, changeDealStage, createDeal, getDeals, getPartners, getProducts, rejectDeal, submitDeal } from "../api/client";
import { commercial, type Organization } from "../features/commercial/types";
import { useAuth } from "../features/auth/AuthContext";

const stages = ["REGISTERED", "QUALIFIED", "DISCOVERY", "DEMO", "POC", "PROPOSAL", "NEGOTIATION", "WON", "LOST"];

export function DealsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isTcg = Boolean(user?.is_superuser || user?.roles.some((role) => role.startsWith("TCG_")));
  const [model, setModel] = useState<EngagementModel>(isTcg ? "DIRECT" : "REFERRAL");
  const deals = useQuery({ queryKey: ["deals"], queryFn: getDeals });
  const organizations = useQuery({ queryKey: ["commercial", "organizations"], queryFn: () => commercial<Organization[]>("/organizations"), enabled: isTcg });
  const products = useQuery({ queryKey: ["products"], queryFn: getProducts });
  const partners = useQuery({ queryKey: ["partners", "deal-picker"], queryFn: () => getPartners("status=ACTIVE&page_size=100"), enabled: isTcg });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["deals"] });
  const create = useMutation({ mutationFn: createDeal, onSuccess: refresh });
  const action = useMutation({ mutationFn: (job: () => Promise<unknown>) => job(), onSuccess: refresh });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      engagement_model: model,
      partner_id: isTcg ? form.get("partner_id") || null : undefined,
      product_id: form.get("product_id"), name: form.get("name"),
      estimated_value: form.get("estimated_value") || "0", expected_close_date: form.get("expected_close_date") || null,
      customer: { organization_id: form.get("organization_id") || null, name: form.get("customer_name"), country_code: String(form.get("country_code")).toUpperCase(), contact_email: form.get("contact_email") || null },
    });

  }

  function move(id: string, current: string) {
    const stage = window.prompt(`Pipeline stage (${stages.join(", ")})`, current)?.toUpperCase();
    if (!stage || stage === current) return;
    const body: Record<string, unknown> = { stage };
    if (stage === "WON") { body.actual_contract_value = window.prompt("Actual contract value (USD)"); body.actual_close_date = window.prompt("Close date (YYYY-MM-DD)"); }
    if (stage === "LOST") body.lost_reason = window.prompt("Lost reason");
    action.mutate(() => changeDealStage(id, body));
  }

  const error = (create.error ?? action.error) instanceof ApiError ? (create.error ?? action.error as ApiError).message : null;
  return <div className="workspace-page">
    <header className="page-heading"><span className="eyebrow">Registration & pipeline</span><h1>Deals</h1><p>Register protected opportunities, manage approvals, and retain a complete stage history.</p></header>
    {error && <div className="form-alert form-alert--error">{error}</div>}
    <div className="catalog-layout">
      <section className="content-card table-card"><div className="table-scroll"><table><thead><tr><th>Deal</th><th>Customer</th><th>Approval</th><th>Stage</th><th>Value</th><th /></tr></thead><tbody>
        {deals.data?.map((deal) => <tr key={deal.id}><td><strong>{deal.name}</strong><small>{deal.reference} · {deal.engagement_model?.replaceAll("_", " ") ?? "Needs classification"}</small>{isTcg && <Link to={`/commercial-model?deal=${deal.id}`}>{deal.migration_review_required ? "Review migration" : "Configure commercial model"}</Link>}</td><td>{deal.customer.name}</td><td><span className={`status-pill status-pill--${deal.approval_status.toLowerCase()}`}>{deal.approval_status.replaceAll("_", " ")}</span></td><td>{deal.stage}</td><td>${Number(deal.estimated_value).toLocaleString()}</td><td><span className="inline-actions">
          {(deal.approval_status === "DRAFT" || deal.approval_status === "REJECTED") && <button className="row-action" type="button" onClick={() => action.mutate(() => submitDeal(deal.id))}>Submit</button>}
          {isTcg && ["SUBMITTED", "UNDER_REVIEW"].includes(deal.approval_status) && <><button className="row-action" type="button" onClick={() => action.mutate(() => approveDeal(deal.id))}>Approve</button><button className="row-action" type="button" onClick={() => { const reason = window.prompt("Rejection reason"); if (reason) action.mutate(() => rejectDeal(deal.id, reason)); }}>Reject</button></>}
          {deal.approval_status === "APPROVED" && <button className="row-action" type="button" onClick={() => move(deal.id, deal.stage)}>Move</button>}
        </span></td></tr>)}
      </tbody></table></div>{!deals.isLoading && !deals.data?.length && <div className="empty-state"><h2>No deals yet</h2><p>Register the first customer opportunity.</p></div>}</section>
      <form className="content-card compact-form catalog-create" onSubmit={submit}><span className="status-kicker">New opportunity</span><h2>Register deal</h2>
        <label>Engagement model<select name="engagement_model" value={model} onChange={event => setModel(event.target.value as EngagementModel)}>{engagementModels.filter(item => isTcg || item !== "DIRECT").map(item => <option key={item}>{item}</option>)}</select></label>
        {isTcg && <label>Commercial partner<select name="partner_id" required={model !== "DIRECT"}><option value="">Select partner</option>{partners.data?.items.filter(partner => model === "DIRECT" || partner.capabilities.some(capability => capability.code === model)).map((partner) => <option key={partner.id} value={partner.id}>{partner.company_name}</option>)}</select></label>}
        <label>Product<select name="product_id" required><option value="">Select product</option>{products.data?.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label>
        <label>Deal name<input name="name" required /></label><label>Customer<input name="customer_name" required /></label>{isTcg && <label>Existing customer organization (optional)<select name="organization_id"><option value="">Create a new customer identity</option>{organizations.data?.map(org => <option key={org.id} value={org.id}>{org.legal_name}</option>)}</select></label>}<label>Country code<input name="country_code" required minLength={2} maxLength={2} placeholder="IN" /></label><label>Contact email<input name="contact_email" type="email" /></label><label>Estimated value (USD)<input name="estimated_value" type="number" min="0" step="0.01" /></label><label>Expected close<input name="expected_close_date" type="date" /></label><button type="submit" disabled={create.isPending}>Register deal</button>
      </form>
    </div>
  </div>;
}
