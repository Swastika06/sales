// Isolated browser fixtures intercept every API call. No real users or records are changed.
import assert from "node:assert/strict";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { chromium } from "playwright";

const base = process.env.PORTAL_TEST_URL || "http://localhost:5173";
const api = "https://widget-api.example.test/api/v1";
const defaultKey = "tcg_partner_widget_token:" + api;
const password = "Widget-test-password&+123";
const widget = fs.readFileSync(new URL("../ezextend/react-design.jsx", import.meta.url), "utf8");
const bundle = await build({
  stdin: {
    contents: 'import React from "react"; import {createRoot} from "react-dom/client"; const root = createRoot(document.getElementById("widget")); const render = value => root.render(value);\n' + widget,
    loader: "jsx", resolveDir: fileURLToPath(new URL("..", import.meta.url)),
  },
  bundle: true, write: false, format: "iife",
});
const browser = await chromium.launch({ channel: "msedge", headless: true });
const company = {
  id: "partner-1", company_name: "Widget Company", code: "TCG-001",
  legal_name: "Widget Company Ltd", company_email: "company@example.test",
  primary_contact_name: "Partner User", primary_contact_email: "partner@example.test",
  partner_type: { id: "reseller", code: "RESELLER", name: "Reseller" },
  capabilities: [{ id: "reseller", code: "RESELLER", name: "Reseller" }],
  countries: [{ id: "in", code: "IN", name: "India" }],
  status: "ACTIVE", created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
};
const options = { partner_types: company.capabilities, countries: company.countries, partner_roles: [{ id: "admin", code: "PARTNER_ADMIN", name: "Partner Admin" }] };
const users = {
  partner: { id: "partner-user", full_name: "Partner User", email: "partner@example.test", is_active: true, is_superuser: false, partner_id: company.id, roles: ["PARTNER_ADMIN"], permissions: [] },
  admin: { id: "admin-user", full_name: "Admin User", email: "admin@example.test", is_active: true, is_superuser: true, partner_id: null, roles: ["TCG_ADMIN"], permissions: [] },
  legal: { id: "legal-user", full_name: "Legal User", email: "legal@example.test", is_active: true, is_superuser: false, partner_id: null, roles: ["TCG_LEGAL"], permissions: [] },
};

async function fixture(width = 1280, config = {}) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  page.setDefaultTimeout(10000);
  const state = { mode: "success", role: "partner", expired: false, calls: [], errors: [], unexpected: [], profileWrites: 0 };
  page.on("pageerror", error => state.errors.push(error.message));
  await page.route(base + "/widget-host", route => route.fulfill({
    contentType: "text/html",
    body: '<!doctype html><html><head><style>body{margin:0;background:rgb(240,241,242)}#host-button{background:rgb(201,22,99)}</style></head><body><button id="host-button">Host control</button><div id="widget"></div></body></html>',
  }));
  await page.route("**/api/v1/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname.replace("/api/v1", "");
    state.calls.push({ path: pathname, method: request.method(), authorization: request.headers().authorization });
    const reply = (data, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify(data) });
    if (!request.url().startsWith(api + "/")) {
      state.unexpected.push("Wrong API base: " + request.url());
      return reply({ error: { message: "Wrong API base" } }, 500);
    }
    if (pathname === "/auth/token") {
      assert.equal(request.method(), "POST");
      assert.match(request.headers()["content-type"], /application\/x-www-form-urlencoded/);
      const body = new URLSearchParams(request.postData());
      assert.equal(body.get("username"), users[state.role].email);
      assert.equal(body.get("password"), password);
      assert.equal(request.headers().authorization, undefined);
      if (state.mode === "network") return route.abort("failed");
      if (state.mode === "timeout") {
        await new Promise(resolve => setTimeout(resolve, 300));
        return reply({ access_token: "test-token-" + state.role });
      }
      if (state.mode === "invalid-json") return route.fulfill({ status: 502, contentType: "text/html", body: "Bad gateway" });
      if (state.mode === "invalid") return reply({ error: { message: "Incorrect email or password" } }, 401);
      if (state.mode === "pending") return reply({ error: { message: "Partner account is pending approval" } }, 403);
      return reply({ access_token: "test-token-" + state.role, token_type: "bearer" });
    }
    if (pathname === "/partners/registration-options") return reply(options);
    if (state.expired || (pathname === "/auth/me" && state.mode === "me-fails")) return reply({ error: { message: "Session expired. Please sign in again." } }, 401);
    if (pathname !== "/health/ready") assert.equal(request.headers().authorization, "Bearer test-token-" + state.role, pathname + " requires the session token");
    if (pathname === "/auth/me") return reply(users[state.role]);
    if (pathname === "/partners/partner-1") {
      if (request.method() === "PATCH") { state.profileWrites++; Object.assign(company, request.postDataJSON()); }
      return reply(company);
    }
    if (pathname === "/partners") return reply({ items: [company], total: 1, page: 1, page_size: 20 });
    if (pathname === "/partners/partner-1/users") return reply([]);
    if (pathname === "/pricing/resolved") return reply({ partner_id: company.id, partner_name: company.company_name, items: [], currency: "USD" });
    if (pathname === "/commercial/summary") return reply({ basis: "Forecast", opportunities: 0, totals: {}, undisclosed: {} });
    if (pathname === "/commercial/agreements") return reply({ partners: [], vendors: [] });
    if (pathname === "/health/ready") return reply({ status: "ok", services: {} });
    if (["/documents", "/deals", "/products", "/quotes", "/maf", "/orders", "/commercial/organizations", "/commercial/commissions", "/commercial/migration-review", "/onboarding/applications", "/onboarding/reviewers"].includes(pathname)) return reply([]);
    state.unexpected.push(request.method() + " " + pathname);
    return reply({ error: { message: "Unexpected fixture request" } }, 500);
  });
  async function mount(next = {}) {
    await page.goto(base + "/widget-host");
    await page.evaluate(settings => {
      window.TCG_PARTNER_PORTAL_CONFIG = settings;
      localStorage.setItem("partner_portal_token", "unrelated-host-token");
    }, { apiBaseUrl: api, loadFonts: false, initialPath: "/login", ...config, ...next });
    await page.addScriptTag({ content: bundle.outputFiles[0].text });
  }
  await mount();
  return { page, state, mount };
}
async function login(page, role = "partner") {
  await page.getByLabel("Email", { exact: true }).fill(users[role].email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}
async function clean(f) {
  assert.deepEqual(f.state.errors, [], "No browser exceptions");
  assert.deepEqual(f.state.unexpected, [], "No unexpected API calls");
  assert.equal(await f.page.evaluate(() => getComputedStyle(document.getElementById("host-button")).backgroundColor), "rgb(201, 22, 99)", "Styles remain scoped");
  assert.equal(await f.page.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(240, 241, 242)", "Host body styles unchanged");
  assert.equal(f.page.url(), base + "/widget-host", "Host URL stays unchanged");
  await f.page.close();
}

try {
  for (const width of [1280, 375]) {
    const f = await fixture(width, { initialPath: "/" });
    if (width < 768) await f.page.getByRole("button", { name: "Open navigation" }).click();
    await f.page.getByRole("link", { name: "Partner login", exact: true }).click();
    await login(f.page);
    await f.page.getByRole("heading", { name: "Good to see you, Partner." }).waitFor();
    assert.equal(await f.page.getByRole("link", { name: "Products & SKUs" }).count(), 0);
    assert.equal(await f.page.getByRole("link", { name: "Onboarding review", exact: true }).count(), 0);
    assert.equal(await f.page.evaluate(key => localStorage.getItem(key), defaultKey), "test-token-partner");
    assert.equal(await f.page.evaluate(() => localStorage.getItem("partner_portal_token")), "unrelated-host-token");
    assert.equal(await f.page.evaluate(value => JSON.stringify({ ...localStorage, ...sessionStorage }).includes(value), password), false, "Password is never persisted");
    const nav = f.page.getByRole("navigation", { name: "Primary navigation" });
    const entries = [
      ["Company profile", "Widget Company"], ["Users", "Partner users"],
      ["Pricing", "Pricing by engagement"], ["Documents", "Documents"],
      ["Deals & pipeline", null], ["My commissions", null], ["Quote to order", null], ["System status", null],
    ];
    for (const [name, heading] of entries) {
      await nav.getByRole("link", { name, exact: true }).click();
      await f.page.locator(".workspace-main h1").waitFor();
      if (heading) await f.page.getByRole("heading", { name: heading, exact: true }).waitFor();
      await f.page.waitForLoadState("networkidle");
      assert.equal(await f.page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, name + " fits viewport " + width);
    }
    await nav.getByRole("link", { name: "Company profile", exact: true }).click();
    await f.page.getByText("Edit partner profile", { exact: true }).click();
    await f.page.locator('[name="legal_name"]').fill("Updated Widget Company Ltd");
    await f.page.getByRole("button", { name: "Save profile" }).click();
    await f.page.getByText("Updated Widget Company Ltd", { exact: true }).waitFor();
    assert.equal(f.state.profileWrites, 1, "Profile save uses the shared authenticated API");
    await f.mount({ initialPath: "/login" });
    await f.page.getByRole("heading", { name: "Good to see you, Partner." }).waitFor();
    assert.equal(f.state.calls.filter(call => call.path === "/auth/token").length, 1, "Session restored without resubmitting credentials");
    await f.page.getByRole("button", { name: "Sign out", exact: true }).click();
    await f.page.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
    assert.equal(await f.page.evaluate(key => localStorage.getItem(key), defaultKey), null);
    await f.mount({ initialPath: "/partners/partner-1/users" });
    await f.page.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
    await login(f.page);
    await f.page.getByRole("heading", { name: "Partner users", exact: true }).waitFor();
    f.state.expired = true;
    await f.page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Documents", exact: true }).click();
    await f.page.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
    assert.equal(await f.page.evaluate(key => localStorage.getItem(key), defaultKey), null);
    await clean(f);
    console.log("PASS partner login, every workspace section, profile save, restoration, logout, protected return, expiry at " + width + "px");
  }

  const failures = await fixture();
  for (const [mode, message] of [
    ["invalid", "Incorrect email or password"],
    ["pending", "Partner account is pending approval"],
    ["me-fails", "Session expired. Please sign in again."],
    ["invalid-json", "Sign in failed"],
    ["network", "Unable to reach the portal. Check your connection and try again."],
  ]) {
    failures.state.mode = mode;
    await login(failures.page);
    await failures.page.getByRole("alert").filter({ hasText: message }).waitFor();
    assert.equal(await failures.page.locator(".workspace").count(), 0);
    assert.equal(await failures.page.evaluate(key => localStorage.getItem(key), defaultKey), null, "Rejected login leaves no token");
  }
  failures.state.mode = "timeout";
  await failures.mount({ requestTimeoutMs: 75 });
  await login(failures.page);
  await failures.page.getByRole("alert").filter({ hasText: "The request timed out" }).waitFor();
  await clean(failures);
  console.log("PASS incorrect credentials, pending account, failed user lookup, malformed response, network failure, timeout");

  for (const role of ["admin", "legal"]) {
    const f = await fixture(1280, { tokenStorageKey: "widget-session-test" });
    f.state.role = role;
    await login(f.page, role);
    await f.page.getByRole("navigation", { name: "Primary navigation" }).waitFor();
    if (role === "admin") {
      const nav = f.page.getByRole("navigation", { name: "Primary navigation" });
      for (const name of ["Partners", "Products & SKUs", "Commercial model", "Onboarding review"]) {
        await nav.getByRole("link", { name, exact: true }).click();
        await f.page.locator(".workspace-main h1").waitFor();
        await f.page.waitForLoadState("networkidle");
      }
      await f.page.getByRole("heading", { name: "Applications & legal routing" }).waitFor();
    } else {
      await f.page.getByRole("heading", { name: "Legal verification" }).waitFor();
      assert.equal(await f.page.getByRole("link", { name: "Partners", exact: true }).count(), 0);
      assert.equal(await f.page.getByRole("link", { name: "Pricing", exact: true }).count(), 0);
    }
    assert.equal(await f.page.evaluate(() => localStorage.getItem("widget-session-test")), "test-token-" + role);
    await clean(f);
    console.log("PASS " + role + " role navigation and custom session key");
  }

  const links = await fixture();
  await links.page.getByRole("link", { name: "Register your company" }).click();
  await links.page.locator('[name="company_name"]').waitFor();
  assert.equal(links.page.url(), base + "/widget-host");
  await links.mount();
  await links.page.getByRole("link", { name: "Track application or activate account" }).click();
  await links.page.getByRole("button", { name: "Continue application" }).waitFor();
  await clean(links);
  console.log("PASS sign-in links return to embedded registration and application tracking");
} finally {
  await browser.close();
}
