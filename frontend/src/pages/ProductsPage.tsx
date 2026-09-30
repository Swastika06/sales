import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent } from "react";

import {
  ApiError,
  createProduct,
  createSku,
  getProductPrices,
  getProducts,
  setProductPrice,
  updateProduct,
  updateSku,
  type Sku,
} from "../api/client";
import { commercial, type Organization } from "../features/commercial/types";
import { useAuth } from "../features/auth/AuthContext";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function SkuRow({ sku, canManage }: { sku: Sku; canManage: boolean }) {
  const queryClient = useQueryClient();
  const prices = useQuery({
    queryKey: ["product-prices", sku.id],
    queryFn: () => getProductPrices(sku.id),
    enabled: canManage,
  });
  const priceMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => setProductPrice(sku.id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["resolved-pricing"] });
      return queryClient.invalidateQueries({ queryKey: ["product-prices", sku.id] });
    },
  });
  const skuMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => updateSku(sku.id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["resolved-pricing"] });
      return queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
  const currentPrice = prices.data?.find((price) => price.is_active) ?? prices.data?.[0];

  function configurePrice() {
    const amount = window.prompt("USD list price", currentPrice?.amount ?? "");
    if (amount === null || amount === "") return;
    const effectiveFrom = window.prompt("Effective from (YYYY-MM-DD)", today());
    if (!effectiveFrom) return;
    const effectiveUntil = window.prompt("Effective until (optional YYYY-MM-DD)", "");
    if (effectiveUntil !== null) {
      priceMutation.mutate({
        amount,
        effective_from: effectiveFrom,
        effective_until: effectiveUntil || null,
      });
    }
  }

  function editSku() {
    const name = window.prompt("SKU name", sku.name);
    if (!name) return;
    const unit = window.prompt("Unit", sku.unit);
    if (unit) skuMutation.mutate({ name, unit });
  }

  return <div className={`sku-row ${sku.is_active ? "" : "sku-row--inactive"}`}>
    <span><strong>{sku.name}</strong><small>{sku.code} · {sku.category.replaceAll("_", " ")} · per {sku.unit}</small></span>
    <span className="sku-price">{canManage ? currentPrice ? `$${Number(currentPrice.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "Price not set" : "Active SKU"}</span>
    {canManage && <span className="inline-actions"><button className="row-action" type="button" onClick={configurePrice}>Set price</button><button className="row-action" type="button" onClick={editSku}>Edit</button><button className="row-action" type="button" onClick={() => skuMutation.mutate({ is_active: !sku.is_active })}>{sku.is_active ? "Disable" : "Enable"}</button></span>}
  </div>;
}

export function ProductsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const canManage = Boolean(user?.is_superuser || user?.roles.includes("TCG_ADMIN"));
  const organizations = useQuery({ queryKey: ["commercial", "organizations"], queryFn: () => commercial<Organization[]>("/organizations"), enabled: canManage });
  const products = useQuery({ queryKey: ["products"], queryFn: getProducts });
  const productMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => createProduct(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
  const skuMutation = useMutation({
    mutationFn: ({ productId, body }: { productId: string; body: Record<string, unknown> }) => createSku(productId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
  const productStatus = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => updateProduct(id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });

  function addProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    productMutation.mutate({ owner_organization_id: form.get("owner_organization_id") || null, code: String(form.get("code")).toUpperCase(), name: form.get("name"), description: form.get("description") || null });
    event.currentTarget.reset();
  }

  function addSku(productId: string) {
    const code = window.prompt("SKU code (uppercase, digits, hyphen or underscore)");
    if (!code) return;
    const name = window.prompt("SKU name");
    if (!name) return;
    const category = window.prompt("Category: LICENSE, IMPLEMENTATION, SERVICE, or OTHER", "LICENSE");
    if (!category) return;
    const unit = window.prompt("Unit", category === "IMPLEMENTATION" ? "project" : "license");
    if (unit) skuMutation.mutate({ productId, body: { code: code.toUpperCase(), name, category: category.toUpperCase(), unit } });
  }

  function editProduct(id: string, currentName: string, currentDescription: string | null) {
    const name = window.prompt("Product name", currentName);
    if (!name) return;
    const description = window.prompt("Description", currentDescription ?? "");
    if (description !== null) productStatus.mutate({ id, body: { name, description: description || null } });
  }

  const error = productMutation.error instanceof ApiError ? productMutation.error.message : null;
  return <div className="workspace-page">
    <header className="page-heading page-heading--row"><div><span className="eyebrow">Product master</span><h1>Products & SKUs</h1><p>Maintain an extensible catalog and effective-dated USD list prices.</p></div></header>
    <div className="catalog-layout">
      <section className="catalog-list">
        {products.isLoading && <p className="notice">Loading catalog…</p>}
        {products.data?.map((product) => <article className={`content-card product-card ${product.is_active ? "" : "product-card--inactive"}`} key={product.id}>
          <header><div><span className="status-kicker">{product.code}</span><h2>{product.name}</h2><p>{product.description}</p></div>{canManage && <span className="inline-actions"><button className="button-secondary" type="button" onClick={() => addSku(product.id)}>Add SKU</button><button className="row-action" type="button" onClick={() => editProduct(product.id, product.name, product.description)}>Edit</button><button className="row-action" type="button" onClick={() => productStatus.mutate({ id: product.id, body: { is_active: !product.is_active } })}>{product.is_active ? "Disable" : "Enable"}</button></span>}</header>
          <div className="sku-list">{product.skus.length ? product.skus.map((sku) => <SkuRow key={sku.id} sku={sku} canManage={canManage} />) : <p className="notice">No SKUs configured.</p>}</div>
        </article>)}
      </section>
      {canManage && <form className="content-card compact-form catalog-create" onSubmit={addProduct}><span className="status-kicker">Catalog</span><h2>Add product</h2>{error && <div className="form-alert form-alert--error">{error}</div>}<label>Product code<input name="code" required pattern="[A-Z0-9][A-Z0-9_-]*" placeholder="PRODUCT-CODE" /></label><label>Name<input name="name" required /></label><label>Product owner<select name="owner_organization_id"><option value="">TCG Digital</option>{organizations.data?.map(org => <option key={org.id} value={org.id}>{org.legal_name}</option>)}</select></label><label>Description<textarea name="description" rows={4} /></label><button type="submit" disabled={productMutation.isPending}>Add product</button></form>}
    </div>
  </div>;
}
