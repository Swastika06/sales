import { apiConfig } from "./config";
import { clearAccessToken, getAccessToken } from "../features/auth/session";

export interface DependencyStatus {
  status: "ok" | "error";
  detail: string | null;
}

export interface ReadyResponse {
  status: "ok" | "degraded";
  services: Record<string, DependencyStatus>;
}

export interface CurrentUser {
  must_change_password: boolean;
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  partner_id: string | null;
  roles: string[];
  permissions: string[];
}

export interface MasterDataItem {
  id: string;
  code: string;
  name: string;
}

export interface RegistrationOptions {
  partner_types: MasterDataItem[];
  countries: MasterDataItem[];
  partner_roles: MasterDataItem[];
}

export type PartnerStatus =
  | "PENDING_APPROVAL"
  | "ACTIVE"
  | "REJECTED"
  | "SUSPENDED"
  | "INACTIVE";

export interface Partner {
  id: string;
  code: string | null;
  company_name: string;
  legal_name: string | null;
  company_email: string;
  website: string | null;
  phone: string | null;
  address: string | null;
  primary_contact_name: string;
  primary_contact_email: string;
  primary_contact_phone: string | null;
  status: PartnerStatus;
  rejection_reason: string | null;
  approved_at: string | null;
  partner_type: MasterDataItem;
  capabilities: MasterDataItem[];
  organization_id: string | null;
  countries: MasterDataItem[];
  created_at: string;
  updated_at: string;
}

export interface PartnerList {
  items: Partner[];
  total: number;
  page: number;
  page_size: number;
}

export interface PartnerUser {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: string[];
  created_at: string;
}

export interface Sku {
  id: string;
  product_id: string;
  code: string;
  name: string;
  description: string | null;
  category: "LICENSE" | "IMPLEMENTATION" | "SERVICE" | "OTHER";
  unit: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Product {
  owner_organization_id: string | null;
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  skus: Sku[];
  created_at: string;
  updated_at: string;
}

export interface ProductPrice {
  id: string;
  sku_id: string;
  amount: string;
  currency: "USD";
  effective_from: string;
  effective_until: string | null;
  is_active: boolean;
}

export type EngagementModel = "DIRECT" | "RESELLER" | "REFERRAL" | "SYSTEM_INTEGRATOR";
export const engagementModels: EngagementModel[] = ["DIRECT", "RESELLER", "REFERRAL", "SYSTEM_INTEGRATOR"];
export interface PriceBreakdown { list_price: string | null; sources: Record<string, string>; }

export interface ResolvedPrice {
  product_id: string;
  product_code: string;
  product_name: string;
  sku_id: string;
  sku_code: string;
  sku_name: string;
  sku_description: string | null;
  unit: string;
  currency: "USD";
  final_price: string;
  effective_from: string;
  effective_until: string | null;
  commercial_model: EngagementModel;
  commission_percentage: string | null;
  breakdown: PriceBreakdown | null;
}

export interface PartnerPricing {
  partner_id: string;
  partner_name: string;
  as_of: string;
  currency: "USD";
  items: ResolvedPrice[];
}

async function fetchApi(path: string, init: RequestInit = {}) {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (init.signal?.aborted) cancel();
  init.signal?.addEventListener("abort", cancel, { once: true });
  const timer = setTimeout(cancel, apiConfig.requestTimeoutMs);
  try {
    return await fetch(apiConfig.apiBaseUrl.replace(/\/+$/, "") + path, { ...init, signal: controller.signal });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(controller.signal.aborted ? "The request timed out. Please try again." : "Unable to reach the portal. Check your connection and try again.", 0);
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener("abort", cancel);
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
  ) {
    super(message);
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const isFormData = init?.body instanceof FormData;
  const response = await fetchApi(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const authorization = new Headers(init?.headers).get("Authorization") ?? (token ? `Bearer ${token}` : null);
    if (response.status === 401 && token && authorization === `Bearer ${token}`) clearAccessToken(token);
    const body = (await response.json().catch(() => null)) as
      | { error?: { message?: string; request_id?: string } }
      | null;
    throw new ApiError(
      body?.error?.message ?? `Request failed with status ${response.status}`,
      response.status,
      body?.error?.request_id,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetchApi("/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const payload = (await response.json().catch(() => null)) as
    | { access_token: string }
    | { error?: { message?: string; request_id?: string } }
    | null;
  if (!response.ok || !payload || !("access_token" in payload) || typeof payload.access_token !== "string" || !payload.access_token) {
    const error = payload && "error" in payload ? payload.error : undefined;
    throw new ApiError(error?.message ?? "Sign in failed", response.status, error?.request_id);
  }
  return payload.access_token;
}

export const getCurrentUser = (token?: string) => apiRequest<CurrentUser>("/auth/me", token ? { headers: { Authorization: `Bearer ${token}` } } : undefined);
export const getRegistrationOptions = () =>
  apiRequest<RegistrationOptions>("/partners/registration-options");
export const registerPartner = (body: unknown) =>
  apiRequest<Partner>("/partners/register", { method: "POST", body: JSON.stringify(body) });
export const createPartner = (body: unknown) =>
  apiRequest<Partner>("/partners", { method: "POST", body: JSON.stringify(body) });
export const getPartners = (query = "") =>
  apiRequest<PartnerList>(`/partners${query ? `?${query}` : ""}`);
export const getPartner = (id: string) => apiRequest<Partner>(`/partners/${id}`);
export const updatePartner = (id: string, body: unknown) =>
  apiRequest<Partner>(`/partners/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const getPartnerUsers = (id: string) =>
  apiRequest<PartnerUser[]>(`/partners/${id}/users`);
export const approvePartner = (id: string) =>
  apiRequest<Partner>(`/partners/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({}),
  });
export const rejectPartner = (id: string, reason: string) =>
  apiRequest<Partner>(`/partners/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
export const changePartnerStatus = (id: string, status: PartnerStatus) =>
  apiRequest<Partner>(`/partners/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
export const createPartnerUser = (id: string, body: unknown) =>
  apiRequest<PartnerUser>(`/partners/${id}/users`, {
    method: "POST",
    body: JSON.stringify(body),
  });
export const updatePartnerUser = (partnerId: string, userId: string, body: unknown) =>
  apiRequest<PartnerUser>(`/partners/${partnerId}/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
export const getProducts = () => apiRequest<Product[]>("/products");
export const createProduct = (body: unknown) =>
  apiRequest<Product>("/products", { method: "POST", body: JSON.stringify(body) });
export const updateProduct = (id: string, body: unknown) =>
  apiRequest<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const createSku = (productId: string, body: unknown) =>
  apiRequest<Sku>(`/products/${productId}/skus`, {
    method: "POST",
    body: JSON.stringify(body),
  });
export const updateSku = (id: string, body: unknown) =>
  apiRequest<Sku>(`/products/skus/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const getProductPrices = (skuId: string) =>
  apiRequest<ProductPrice[]>(`/products/skus/${skuId}/prices`);
export const setProductPrice = (skuId: string, body: unknown) =>
  apiRequest<ProductPrice>(`/products/skus/${skuId}/prices`, {
    method: "POST",
    body: JSON.stringify(body),
  });
export const getResolvedPricing = (model: EngagementModel, partnerId?: string, asOf?: string) => {
  const query = new URLSearchParams();
  query.set("engagement_model", model);
  if (partnerId) query.set("partner_id", partnerId);
  if (asOf) query.set("as_of", asOf);
  return apiRequest<PartnerPricing>(`/pricing/resolved?${query.toString()}`);
};
export interface DocumentVersion {
  id: string; version_number: number; file_name: string; content_type: string;
  size_bytes: number; checksum_sha256: string; change_note: string | null; created_at: string;
}
export interface PortalDocument {
  id: string; title: string; description: string | null; category: string; visibility: string;
  product_id: string | null; partner_type_id: string | null;
  partner_id: string | null; is_active: boolean; versions: DocumentVersion[];
  created_at: string; updated_at: string;
}
export interface Customer { id: string; name: string; country_code: string; created_at: string; }
export interface StageHistory { id: string; from_stage: string | null; to_stage: string; note: string | null; changed_at: string; }
export interface Deal {
  id: string; reference: string; partner_id: string | null; engagement_model: EngagementModel | null; commercial_version: number; migration_review_required: boolean; responsible_user_id: string | null; customer_id: string; product_id: string;
  name: string; description: string | null; estimated_value: string; currency: string;
  expected_close_date: string | null; approval_status: string; stage: string;
  review_reason: string | null; protection_expires_at: string | null;
  actual_contract_value: string | null; actual_close_date: string | null; lost_reason: string | null;
  customer: Customer; stage_history: StageHistory[]; created_at: string; updated_at: string;
}
export interface QuoteItem { id: string; sku_id: string; sku_code: string; sku_name: string; quantity: string; unit_price: string; discount_percentage: string; line_total: string; }
export interface Quote { id: string; reference: string; opportunity_id: string; partner_id: string | null; contract_id: string | null; status: string; commercial_model: string; valid_until: string | null; currency: string; subtotal: string; discount_total: string; total: string; current_revision: number; notes: string | null; items: QuoteItem[]; created_at: string; updated_at: string; }
export interface Maf { id: string; reference: string; opportunity_id: string; partner_id: string; status: string; tender_reference: string; tender_authority: string; tender_due_date: string; tender_value: string | null; details: string | null; review_reason: string | null; expires_at: string | null; created_at: string; updated_at: string; }
export interface OrderHistory { id: string; from_status: string | null; to_status: string; note: string | null; changed_at: string; }
export interface Order { id: string; reference: string; quote_id: string; partner_id: string | null; status: string; billing_name: string; billing_address: string; billing_email: string; currency: string; total: string; review_reason: string | null; confirmed_at: string | null; status_history: OrderHistory[]; created_at: string; updated_at: string; }

export const getDocuments = (query = "") => apiRequest<PortalDocument[]>(`/documents${query ? `?${query}` : ""}`);
export const uploadDocument = (body: FormData) => apiRequest<PortalDocument>("/documents", { method: "POST", body });
export const addDocumentVersion = (id: string, body: FormData) => apiRequest<PortalDocument>(`/documents/${id}/versions`, { method: "POST", body });
export const downloadDocument = (id: string, version?: number) => apiRequest<{ url: string }>(`/documents/${id}/download${version ? `?version=${version}` : ""}`);
export const getCustomers = () => apiRequest<Customer[]>("/deals/customers");
export const getDeals = () => apiRequest<Deal[]>("/deals");
export const createDeal = (body: unknown) => apiRequest<Deal>("/deals", { method: "POST", body: JSON.stringify(body) });
export const submitDeal = (id: string) => apiRequest<Deal>(`/deals/${id}/submit`, { method: "POST" });
export const approveDeal = (id: string) => apiRequest<Deal>(`/deals/${id}/approve`, { method: "POST" });
export const rejectDeal = (id: string, reason: string) => apiRequest<Deal>(`/deals/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) });
export const changeDealStage = (id: string, body: unknown) => apiRequest<Deal>(`/deals/${id}/stage`, { method: "POST", body: JSON.stringify(body) });
export const getQuotes = () => apiRequest<Quote[]>("/quotes");
export const createQuote = (body: unknown) => apiRequest<Quote>("/quotes", { method: "POST", body: JSON.stringify(body) });
export const addQuoteItem = (id: string, body: unknown) => apiRequest<Quote>(`/quotes/${id}/items`, { method: "POST", body: JSON.stringify(body) });
export const changeQuoteStatus = (id: string, status: string, reason?: string) => apiRequest<Quote>(`/quotes/${id}/status`, { method: "POST", body: JSON.stringify({ status, reason }) });
export const reviseQuote = (id: string) => apiRequest<Quote>(`/quotes/${id}/revise`, { method: "POST" });
export const getMafs = () => apiRequest<Maf[]>("/maf");
export const createMaf = (body: unknown) => apiRequest<Maf>("/maf", { method: "POST", body: JSON.stringify(body) });
export const changeMafStatus = (id: string, status: string, reason?: string) => apiRequest<Maf>(`/maf/${id}/status`, { method: "POST", body: JSON.stringify({ status, reason }) });
export const uploadMafAttachment = (id: string, body: FormData, kind = "SUPPORTING") => apiRequest(`/maf/${id}/attachments?kind=${kind}`, { method: "POST", body });
export const getOrders = () => apiRequest<Order[]>("/orders");
export const createOrder = (body: unknown) => apiRequest<Order>("/orders", { method: "POST", body: JSON.stringify(body) });
export const changeOrderStatus = (id: string, status: string, reason?: string) => apiRequest<Order>(`/orders/${id}/status`, { method: "POST", body: JSON.stringify({ status, reason }) });
export const uploadOrderAttachment = (id: string, body: FormData) => apiRequest(`/orders/${id}/attachments`, { method: "POST", body });

export function getReadiness(): Promise<ReadyResponse> {
  return fetchApi("/health/ready", {
    headers: { Accept: "application/json" },
  }).then(async (response) => {
    const body = (await response.json()) as ReadyResponse;
    if (response.status === 503 && body.status === "degraded") return body;
    if (!response.ok) throw new ApiError("Could not check service readiness", response.status);
    return body;
  });
}
