// Browser smoke checks use intercepted API responses; no real applications or emails are created.
import assert from "node:assert/strict";
import fs from "node:fs";
import { build } from "esbuild";
import { chromium } from "playwright";

const base = process.env.PORTAL_TEST_URL || "http://localhost:5173";
const browser = await chromium.launch({ channel: "msedge", headless: true });
const pdf = Buffer.from("%PDF-1.7\n1 0 obj <<>> endobj\n%%EOF");
const kinds = ["COMPANY_LICENSE", "PAN", "GSTIN"];
const numbers = ["COMPANY-123", "ABCDE1234F", "27ABCDE1234F1Z5"];
const options = {
  partner_types: [{ id: "1", code: "RESELLER", name: "Reseller" }, { id: "2", code: "REFERRAL", name: "Referral" }, { id: "3", code: "SYSTEM_INTEGRATOR", name: "System integrator" }],
  countries: [{ code: "IN", name: "India" }], partner_roles: []
};

async function setup(page) {
  page.setDefaultTimeout(10000);
  let application = { id: "11111111-1111-1111-1111-111111111111", partner_id: "partner", company_name: "Example Company", email: "applicant@example.com", status: "DRAFT", revision: 1, assigned_to_id: null, review_comment: null, capabilities: ["RESELLER"], required_documents: kinds, documents: [], mail_status: "PENDING" };
  const uploaded = [];
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    const method = route.request().method();
    let data;
    if (path === "/partners/registration-options") data = options;
    else if (path === "/onboarding/applications" && method === "POST") data = { token: "test-application", application };
    else if (path === "/onboarding/me" || path === "/onboarding/me/submit") {
      if (path.endsWith("/submit")) application.status = "PENDING_ADMIN_REVIEW";
      data = application;
    } else if (path === "/onboarding/me/documents") {
      const body = route.request().postDataBuffer().toString();
      const kind = kinds.find(value => body.includes(value));
      assert.ok(kind, "Document kind supplied");
      uploaded.push(kind); application.revision++;
      application.documents.push({ id: kind, kind, number: numbers[kinds.indexOf(kind)], filename: "document.pdf", size: pdf.length, revision: application.revision, scan_status: "CLEAN" });
      data = application;
    } else if (path === "/onboarding/me/verify") {
      assert.equal(route.request().postDataJSON().code, "123456");
      data = { message: "Account activated" };
    } else if (path === "/onboarding/access") data = { token: "test-application", application };
    else if (path === "/auth/me") data = { id: "admin", full_name: "Test Admin", email: "admin@example.com", is_active: true, is_superuser: true, partner_id: null, roles: ["TCG_ADMIN"], permissions: [] };
    else if (path === "/onboarding/applications" && method === "GET") data = [application];
    else if (path === "/onboarding/reviewers") data = [{ id: "legal", name: "Legal Reviewer", email: "legal@example.com" }];
    else if (path.endsWith("/assign-legal")) { application.status = "LEGAL_REVIEW"; application.assigned_to_id = "legal"; data = application; }
    else if (path === "/onboarding/me/resend") data = { message: "Queued" };
    else throw new Error("Unexpected API request: " + method + " " + path);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
  });
  return { uploaded, errors, approve: () => { application.status = "PENDING_EMAIL_VERIFICATION"; } };
}
async function fillRegistration(page) {
  await page.locator('[name="company_name"]').fill("Example Company");
  await page.locator('[name="company_email"]').fill("company@example.com");
  await page.locator('[name="country"]').selectOption("IN");
  await page.locator('[name="partner_type_code"]').selectOption("RESELLER");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator('[name="primary_contact_name"]').fill("Applicant User");
  await page.locator('[name="primary_contact_email"]').fill("applicant@example.com");
  await page.locator('[name="password"]').fill("Onboarding-test-password-123");
  await page.locator('[name="confirm_password"]').fill("Onboarding-test-password-123");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("heading", { name: "Company documents." }).waitFor();
  const fields = page.locator(".onboarding-documents fieldset");
  assert.equal(await fields.count(), 3);
  for (let index = 0; index < 3; index++) {
    await fields.nth(index).locator('input:not([type="file"])').fill(numbers[index]);
    await fields.nth(index).locator('input[type="file"]').setInputFiles({ name: "document.pdf", mimeType: "application/pdf", buffer: pdf });
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator(".p-consent input").check();
  await page.getByRole("button", { name: "Submit application", exact: true }).click();
  await page.getByRole("link", { name: "Track application" }).waitFor();
}
try {
  for (const width of [1280, 375]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const state = await setup(page);
    await page.goto(base + "/register");
    await fillRegistration(page);
    assert.deepEqual(state.uploaded, kinds);
    state.approve();
    await page.goto(base + "/onboarding#token=test-application");
    await page.getByLabel("Activation code").fill("123456");
    await page.getByRole("button", { name: "Verify and activate" }).click();
    await page.getByRole("heading", { name: "Your account is ready." }).waitFor();
    assert.deepEqual(state.errors, []);
    console.log("Main portal registration and activation passed at width " + width);
    await page.close();
  }
  const page = await browser.newPage({ viewport: { width: 375, height: 900 } });
  const state = await setup(page);
  await page.goto(base);
  const widget = fs.readFileSync(new URL("../ezextend/react-design.jsx", import.meta.url), "utf8");
  const bundle = await build({
    stdin: { contents: 'import React from "react"; import {createRoot} from "react-dom/client"; const render = value => createRoot(document.getElementById("widget")).render(value);\n' + widget,
      loader: "jsx", resolveDir: new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1") },
    bundle: true, write: false, format: "iife"
  });
  await page.setContent('<div id="widget"></div>');
  await page.evaluate(({ api }) => { window.TCG_PARTNER_PORTAL_CONFIG = { apiBaseUrl: api, initialPath: "/register", loadFonts: false }; }, { api: base + "/api/v1" });
  await page.addScriptTag({ content: bundle.outputFiles[0].text });
  await fillRegistration(page);
  assert.deepEqual(state.uploaded, kinds);
  state.approve();
  await page.getByRole("link", { name: "Track application" }).click();
  await page.getByLabel("Work email").fill("applicant@example.com");
  await page.getByLabel("Password", { exact: true }).fill("Onboarding-test-password-123");
  await page.getByRole("button", { name: "Continue application" }).click();
  await page.getByLabel("Activation code").fill("123456");
  await page.getByRole("button", { name: "Verify and activate" }).click();
  await page.getByRole("heading", { name: "Your account is ready." }).waitFor();
  assert.deepEqual(state.errors, []);
  console.log("Standalone widget registration and activation passed");
  await page.close();
  const admin = await browser.newPage();
  const adminState = await setup(admin);
  await admin.addInitScript(() => localStorage.setItem("partner_portal_token", "test-admin"));
  await admin.goto(base + "/register");
  await fillRegistration(admin);
  await admin.goto(base + "/onboarding-review");
  await admin.getByRole("button", { name: /Example Company/ }).click();
  await admin.getByLabel("Assign legal reviewer").selectOption("legal");
  await admin.getByRole("button", { name: "Send to Legal" }).click();
  await admin.getByRole("button", { name: /Example Company.*LEGAL REVIEW/ }).waitFor();
  assert.deepEqual(adminState.errors, []);
  console.log("Admin legal routing passed");
  await admin.close();
} finally {
  await browser.close();
}
