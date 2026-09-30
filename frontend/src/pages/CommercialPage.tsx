import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import {
  ApiError, addQuoteItem, changeMafStatus, changeOrderStatus, changeQuoteStatus,
  createMaf, createOrder, createQuote, getDeals, getMafs, getOrders, getProducts, getQuotes,
  reviseQuote, uploadMafAttachment, uploadOrderAttachment,
} from "../api/client";
import { useAuth } from "../features/auth/AuthContext";

type Tab = "quotes" | "maf" | "orders";

export function CommercialPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("quotes");
  const isTcg = Boolean(user?.is_superuser || user?.roles.some((role) => role.startsWith("TCG_")));
  const deals = useQuery({ queryKey: ["deals"], queryFn: getDeals });
  const products = useQuery({ queryKey: ["products"], queryFn: getProducts });
  const quotes = useQuery({ queryKey: ["quotes"], queryFn: getQuotes });
  const mafs = useQuery({ queryKey: ["mafs"], queryFn: getMafs });
  const orders = useQuery({ queryKey: ["orders"], queryFn: getOrders });
  const refresh = () => { void queryClient.invalidateQueries({ queryKey: ["quotes"] }); void queryClient.invalidateQueries({ queryKey: ["mafs"] }); return queryClient.invalidateQueries({ queryKey: ["orders"] }); };
  const action = useMutation({ mutationFn: (job: () => Promise<unknown>) => job(), onSuccess: refresh });

  function quoteSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    action.mutate(() => createQuote({ opportunity_id: form.get("opportunity_id"), contract_id: form.get("contract_id") || null, valid_until: form.get("valid_until") || null }));
  }
  function itemSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    action.mutate(() => addQuoteItem(String(form.get("quote_id")), { sku_id: form.get("sku_id"), quantity: form.get("quantity"), discount_percentage: "0" }));
  }
  function mafSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    action.mutate(() => createMaf({ opportunity_id: form.get("opportunity_id"), tender_reference: form.get("tender_reference"), tender_authority: form.get("tender_authority"), tender_due_date: form.get("tender_due_date"), tender_value: form.get("tender_value") || null }));
  }
  function orderSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    action.mutate(() => createOrder({ quote_id: form.get("quote_id"), billing_name: form.get("billing_name"), billing_email: form.get("billing_email"), billing_address: form.get("billing_address") }));
  }
  function upload(event: FormEvent<HTMLFormElement>, owner: "maf" | "order") {
    event.preventDefault(); const form = new FormData(event.currentTarget); const id = String(form.get("owner_id")); form.delete("owner_id");
    action.mutate(() => owner === "maf" ? uploadMafAttachment(id, form, String(form.get("kind") ?? "SUPPORTING")) : uploadOrderAttachment(id, form));
  }
  function reason(label: string) { return window.prompt(label) ?? undefined; }

  const error = action.error instanceof ApiError ? action.error.message : null;
  const approvedDeals = deals.data?.filter((deal) => deal.approval_status === "APPROVED") ?? [];
  const draftQuotes = quotes.data?.filter((quote) => quote.status === "DRAFT") ?? [];
  const acceptedQuotes = quotes.data?.filter((quote) => quote.status === "ACCEPTED") ?? [];
  return <div className="workspace-page">
    <header className="page-heading"><span className="eyebrow">Commercial operations</span><h1>Quote to order</h1><p>Immutable price snapshots, tender authorization, and controlled order confirmation.</p></header>
    <div className="section-tabs"><button className={tab === "quotes" ? "active" : "button-secondary"} onClick={() => setTab("quotes")}>Quotes</button><button className={tab === "maf" ? "active" : "button-secondary"} onClick={() => setTab("maf")}>MAF</button><button className={tab === "orders" ? "active" : "button-secondary"} onClick={() => setTab("orders")}>Orders</button></div>
    {error && <div className="form-alert form-alert--error">{error}</div>}
    {tab === "quotes" && <div className="operations-grid">
      <section className="content-card table-card"><div className="card-heading"><div><span className="status-kicker">Commercials</span><h2>Quotes</h2></div></div><div className="table-scroll"><table><thead><tr><th>Quote</th><th>Status</th><th>Revision</th><th>Total</th><th /></tr></thead><tbody>{quotes.data?.map((quote) => <tr key={quote.id}><td><strong>{quote.reference}</strong><small>{quote.items.length} item(s)</small></td><td><span className="status-pill">{quote.status}</span></td><td>v{quote.current_revision}</td><td>${Number(quote.total).toLocaleString()}</td><td><span className="inline-actions">{quote.status === "DRAFT" && isTcg && <button className="row-action" onClick={() => action.mutate(() => changeQuoteStatus(quote.id, "FINAL"))}>Finalize</button>}{quote.status === "FINAL" && (quote.commercial_model !== "RESELLER" || !isTcg) && <button className="row-action" onClick={() => action.mutate(() => changeQuoteStatus(quote.id, "ACCEPTED"))}>{quote.commercial_model === "RESELLER" ? "Accept wholesale quote" : "Record acceptance"}</button>}</span></td></tr>)}</tbody></table></div></section>
      <aside className="form-stack"><form className="content-card compact-form" onSubmit={quoteSubmit}><h2>Create quote</h2><label>Approved deal<select name="opportunity_id" required><option value="">Select deal</option>{approvedDeals.map((deal) => <option value={deal.id} key={deal.id}>{deal.reference} · {deal.name}</option>)}</select></label><label>Contract reference<input name="contract_id" placeholder="Required for SI; select in commercial model" /></label><small>Engagement model is inherited from the opportunity.</small><label>Valid until<input name="valid_until" type="date" /></label><button>Create</button></form>
      <form className="content-card compact-form" onSubmit={itemSubmit}><h2>Add priced item</h2><label>Draft quote<select name="quote_id" required><option value="">Select quote</option>{draftQuotes.map((quote) => <option value={quote.id} key={quote.id}>{quote.reference}</option>)}</select></label><label>SKU<select name="sku_id" required><option value="">Select SKU</option>{products.data?.flatMap((product) => product.skus.map((sku) => <option value={sku.id} key={sku.id}>{sku.code} · {sku.name}</option>))}</select></label><label>Quantity<input name="quantity" type="number" min="0.01" step="0.01" defaultValue="1" required /></label><p>Prices use approved terms. Configure discounts in the commercial model.</p><button>Add item</button></form></aside>
    </div>}
    {tab === "maf" && <div className="operations-grid"><section className="content-card table-card"><div className="card-heading"><h2>Marketing authorization</h2></div><div className="table-scroll"><table><thead><tr><th>Request</th><th>Tender</th><th>Due</th><th>Status</th><th /></tr></thead><tbody>{mafs.data?.map((maf) => <tr key={maf.id}><td><strong>{maf.reference}</strong><small>{maf.tender_authority}</small></td><td>{maf.tender_reference}</td><td>{maf.tender_due_date}</td><td><span className="status-pill">{maf.status.replaceAll("_", " ")}</span></td><td><span className="inline-actions">{["DRAFT", "RETURNED_FOR_CORRECTION"].includes(maf.status) && <button className="row-action" onClick={() => action.mutate(() => changeMafStatus(maf.id, "SUBMITTED"))}>Submit</button>}{isTcg && ["SUBMITTED", "UNDER_REVIEW"].includes(maf.status) && <><button className="row-action" onClick={() => action.mutate(() => changeMafStatus(maf.id, "APPROVED"))}>Approve</button><button className="row-action" onClick={() => action.mutate(() => changeMafStatus(maf.id, "RETURNED_FOR_CORRECTION", reason("Correction reason")))}>Return</button></>}</span></td></tr>)}</tbody></table></div></section><aside className="form-stack"><form className="content-card compact-form" onSubmit={mafSubmit}><h2>New MAF request</h2><label>Approved deal<select name="opportunity_id" required><option value="">Select deal</option>{approvedDeals.map((deal) => <option value={deal.id} key={deal.id}>{deal.reference} · {deal.name}</option>)}</select></label><label>Tender reference<input name="tender_reference" required /></label><label>Tender authority<input name="tender_authority" required /></label><label>Due date<input name="tender_due_date" type="date" required /></label><label>Value (USD)<input name="tender_value" type="number" min="0" step="0.01" /></label><button>Create request</button></form><form className="content-card compact-form" onSubmit={(event) => upload(event, "maf")}><h2>Attach MAF file</h2><label>Request<select name="owner_id" required>{mafs.data?.map((maf) => <option value={maf.id} key={maf.id}>{maf.reference}</option>)}</select></label><label>Type<select name="kind"><option value="SUPPORTING">Supporting</option>{isTcg && <option value="ISSUED_DOCUMENT">Issued document</option>}</select></label><label>File<input name="file" type="file" required /></label><button>Upload</button></form></aside></div>}
    {tab === "orders" && <div className="operations-grid"><section className="content-card table-card"><div className="card-heading"><h2>Orders</h2></div><div className="table-scroll"><table><thead><tr><th>Order</th><th>Status</th><th>Total</th><th>Billing</th><th /></tr></thead><tbody>{orders.data?.map((order) => <tr key={order.id}><td><strong>{order.reference}</strong><small>{order.quote_id.slice(0, 8)}</small></td><td><span className="status-pill">{order.status.replaceAll("_", " ")}</span></td><td>${Number(order.total).toLocaleString()}</td><td>{order.billing_name}</td><td><span className="inline-actions">{["DRAFT", "RETURNED_FOR_CORRECTION"].includes(order.status) && <button className="row-action" onClick={() => action.mutate(() => changeOrderStatus(order.id, "SUBMITTED"))}>Submit</button>}{isTcg && ["SUBMITTED", "UNDER_REVIEW"].includes(order.status) && <><button className="row-action" onClick={() => action.mutate(() => changeOrderStatus(order.id, "CONFIRMED"))}>Confirm</button><button className="row-action" onClick={() => action.mutate(() => changeOrderStatus(order.id, "RETURNED_FOR_CORRECTION", reason("Return reason")))}>Return</button></>}{isTcg && order.status === "CONFIRMED" && <button className="row-action" onClick={() => action.mutate(() => changeOrderStatus(order.id, "PROVISIONING"))}>Provision</button>}{isTcg && order.status === "PROVISIONING" && <button className="row-action" onClick={() => action.mutate(() => changeOrderStatus(order.id, "ACTIVE"))}>Activate</button>}</span></td></tr>)}</tbody></table></div></section><aside className="form-stack"><form className="content-card compact-form" onSubmit={orderSubmit}><h2>Create order</h2><label>Accepted quote<select name="quote_id" required><option value="">Select quote</option>{acceptedQuotes.map((quote) => <option value={quote.id} key={quote.id}>{quote.reference} · ${quote.total}</option>)}</select></label><label>Billing name<input name="billing_name" required /></label><label>Billing email<input name="billing_email" type="email" required /></label><label>Billing address<textarea name="billing_address" required /></label><button>Create order</button></form><form className="content-card compact-form" onSubmit={(event) => upload(event, "order")}><h2>Attach PO / contract</h2><label>Order<select name="owner_id" required>{orders.data?.filter((order) => ["DRAFT", "RETURNED_FOR_CORRECTION"].includes(order.status)).map((order) => <option value={order.id} key={order.id}>{order.reference}</option>)}</select></label><label>File<input name="file" type="file" required /></label><button>Upload</button></form></aside></div>}
    {tab === "quotes" && isTcg && quotes.data?.some((quote) => quote.status === "FINAL") && <form className="content-card compact-form issue-panel" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); action.mutate(() => reviseQuote(String(form.get("quote_id")))); }}><h2>Start quote revision</h2><label>Final quote<select name="quote_id" required>{quotes.data.filter((quote) => quote.status === "FINAL").map((quote) => <option key={quote.id} value={quote.id}>{quote.reference} · revision {quote.current_revision}</option>)}</select></label><button>Revise quote</button></form>}
    {tab === "maf" && isTcg && mafs.data?.some((maf) => maf.status === "APPROVED") && <form className="content-card compact-form issue-panel" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); action.mutate(() => changeMafStatus(String(form.get("maf_id")), "ISSUED")); }}><h2>Issue approved MAF</h2><label>Approved request<select name="maf_id" required>{mafs.data.filter((maf) => maf.status === "APPROVED").map((maf) => <option key={maf.id} value={maf.id}>{maf.reference}</option>)}</select></label><p className="notice">Upload the issued document above before issuing.</p><button>Issue MAF</button></form>}
  </div>;
}
