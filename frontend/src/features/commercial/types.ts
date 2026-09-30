import { apiRequest, type EngagementModel } from "../../api/client";
export interface Organization { id: string; legal_name: string; is_internal: boolean; }
export interface Participant { id?: string; organization_id: string; capability: string | null; access_level: string; active: boolean; }
export interface Role { participant_id?: string; organization_id?: string; role: string; scope: string; is_primary?: boolean; primary?: boolean; }
export interface Component { id?: string; name: string; product_id: string | null; sku_id: string | null; external_service: string | null; owner_organization_id: string; seller_organization_id: string; delivery_organization_id: string; billing_organization_id: string; amount: string; }
export interface Contract { id: string; seller_organization_id: string; buyer_organization_id: string; kind: string; status: string; }
export interface Engagement { opportunity_id: string; engagement_model: EngagementModel; commercial_version: number; migration_review_required: boolean; participants: Participant[]; roles: Role[]; components: Component[]; contracts: Contract[]; vendor_links: { id: string; amount: string; cost_treatment: string }[]; }
export interface Term { id: string; scope: string; status: string; version: number; engagement_model: string; effective_from: string; parameters: Record<string, unknown>; }
export interface Totals { customer_value: string | null; tcg_entitlement: string; partner_entitlement: string | null; vendor_cost: string; commission_expense: string; reseller_gross_margin: string | null; warnings: string[]; }
export interface Snapshot { id: string; revision: number; own_entitlement?: string | null; payload?: { result: Totals; request: { parameters: { eligibility?: Eligibility } } }; }
export interface Eligibility { component_ids: string[]; amount: string; discounts: string; taxes: string; vendor_charges: string; credits: string; refunds: string; }
export interface Commission { id: string; opportunity_id: string; amount: string; rate: string; eligible_amount: string; net_accrued: string; paid: string; outstanding: string; status: string; version: number; settlement_policy: string | null; }
export interface Agreements { partners: { id: string; partner_id: string; engagement_model: string }[]; vendors: { id: string; provider_organization_id: string; buyer_organization_id: string; charge_model: string }[]; }
export const commercial = <T,>(path: string) => apiRequest<T>(`/commercial${path}`);
export const saveCommercial = <T,>(path: string, body: unknown, method = "POST") => apiRequest<T>(`/commercial${path}`, { method, body: JSON.stringify(body) });
export const dollars = (value: string | null | undefined) => value == null ? "Undisclosed" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));
export const roles = ["CUSTOMER_RELATIONSHIP_OWNER", "BIDDER", "CONTRACTING_SELLER", "MCUBE_SELLER", "DELIVERY_LEAD", "REFERRER", "PRODUCT_OWNER", "TECHNOLOGY_PROVIDER", "BILL_TO"];
export const label = (value: string) => value.replaceAll("_", " ").toLowerCase().replace(/^./, c => c.toUpperCase());
