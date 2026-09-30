import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const base = process.env.PORTAL_URL || "http://localhost:5173";
const output = "node_modules/.cache/portal-checks";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
const page = await context.newPage();
const errors = [];
page.on("pageerror", error => errors.push(error.message));
const checks = [];
const options = { partner_types: [
  { id: "1", code: "REFERRAL", name: "Referral" },
  { id: "2", code: "RESELLER", name: "Reseller" },
  { id: "3", code: "SYSTEM_INTEGRATOR", name: "System Integrator" }
], countries: [{ id: "IN", code: "IN", name: "India" }, { id: "US", code: "US", name: "United States" }], partner_roles: [] };
try {
  await page.goto(base);
  await page.locator(".p-hero h1").waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: output + "/home-desktop.png", fullPage: true });
  await page.screenshot({ path: output + "/hero-desktop.jpg", type: "jpeg", quality: 65 });
checks.push("Public home renders without authentication");
  await page.getByRole("button", { name: "Services", exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: "Intelligence, applied." }).count(), 1);
  await page.getByRole("button", { name: "Platforms", exact: true }).click();
  await page.getByRole("button", { name: "Compare partnership paths" }).click();
  assert.equal(await page.locator(".p-comparison").count(), 1);
  await page.getByRole("button", { name: "Hide comparison" }).click();
  await page.getByRole("button", { name: "Next story", exact: true }).click();
  assert.equal(await page.getByText("Priya Shah", { exact: true }).count(), 1);
  await page.getByRole("button", { name: "Previous story", exact: true }).click();
  await page.getByRole("button", { name: "Explore the story", exact: true }).click();
  assert.equal(await page.locator(".p-story-detail").count(), 1);
  checks.push("Product tabs, comparison toggle, carousel, and story expansion work");
  const accessibility = [];
  for (const route of ["/", "/partner-with-tcg", "/partner-levels", "/partner-stories"]) {
    await page.goto(base + route);
    await page.locator("h1").waitFor();
    assert.equal(await page.locator("h1").count(), 1);
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    accessibility.push({ route, violations: result.violations.map(v => ({ id: v.id, impact: v.impact, description: v.description, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })) });
  }
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ["/", "/partner-with-tcg", "/partner-levels", "/partner-stories"]) {
      await page.goto(base + route);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      assert.equal(overflow, false, "Horizontal overflow on " + route + " at " + width);
    }
  }
  checks.push("Four public pages fit desktop, tablet, and mobile widths (320–1440px)");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base);
  await page.screenshot({ path: output + "/home-mobile.png", fullPage: true });
  await page.screenshot({ path: output + "/hero-mobile.jpg", type: "jpeg", quality: 65 });
  accessibility.push({ route: "/ (mobile)", violations: (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })) });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.locator(".p-nav").getByRole("link", { name: "Partnership paths" }).click();
  assert.equal(new URL(page.url()).pathname, "/partner-levels");
  assert.equal(await page.getByRole("button", { name: "Open navigation" }).count(), 1);
  checks.push("Mobile navigation opens and closes after navigation");
  await page.route("**/api/v1/partners/registration-options", route => route.fulfill({ json: options }));
  let body;
  let failSubmission = true;
  await page.route("**/api/v1/partners/register", async route => {
    body = route.request().postDataJSON();
    await route.fulfill(failSubmission
      ? { status: 409, json: { error: { message: "This company is already registered." } } }
      : { status: 201, json: { id: "test1234-abcd-efgh", status: "PENDING_APPROVAL" } });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base + "/register?type=RESELLER");
  await page.locator('select[name="country"]').selectOption("IN");
  assert.equal(await page.locator('select[name="partner_type_code"]').inputValue(), "RESELLER");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: "First, your company." }).count(), 1);
  await page.locator('input[name="company_name"]').fill("Portal Test Company");
  await page.locator('input[name="company_email"]').fill("company@example.com");
  await page.locator('input[name="website"]').fill("https://example.com");
  await page.screenshot({ path: output + "/application-desktop.png", fullPage: true });
  accessibility.push({ route: "/register", violations: (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })) });
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.locator('input[name="primary_contact_name"]').fill("Test Partner");
  await page.locator('input[name="primary_contact_email"]').fill("partner@example.com");
  await page.locator('input[name="password"]').fill("SamplePassword123!");
  await page.locator('input[name="confirm_password"]').fill("MismatchPassword123!");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: "Nice to meet you." }).count(), 1);
  await page.locator('input[name="confirm_password"]').fill("SamplePassword123!");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Submit application" }).click();
  assert.equal(body, undefined, "Consent is required before API submission");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Submit application" }).click();
  await page.getByRole("alert").waitFor();
  assert.equal(await page.getByText("This company is already registered.").count(), 1);
  failSubmission = false;
  await page.getByRole("button", { name: "Submit application" }).click();
  await page.getByRole("heading", { name: "You’re one step closer." }).waitFor();
  assert.deepEqual(body.capability_codes, ["RESELLER"]);
  assert.deepEqual(body.country_codes, ["IN"]);
  assert.equal(body.company_name, "Portal Test Company");
  assert.equal("confirm_password" in body, false);
  assert.equal(await page.getByText("TEST1234", { exact: true }).count(), 1);
  checks.push("Registration: preselection, required fields, password matching, consent, server error, retry, correct payload, and reference confirmation (mock API; no records created)");
  await page.unroute("**/api/v1/partners/registration-options");
  await page.route("**/api/v1/partners/registration-options", route => route.fulfill({ status: 503, json: { error: { message: "Unavailable" } } }));
  await page.goto(base + "/register");
  await page.getByRole("button", { name: "Retry loading options" }).waitFor({ timeout: 15000 });
  assert.equal(await page.getByRole("button", { name: "Continue", exact: true }).isDisabled(), true);
  await page.unroute("**/api/v1/partners/registration-options");
  await page.route("**/api/v1/partners/registration-options", route => route.fulfill({ json: options }));
  await page.getByRole("button", { name: "Retry loading options" }).click();
  await page.waitForFunction(() => !document.querySelector('select[name="country"]').disabled);
  checks.push("Unavailable options show a recoverable error and disable submission; retry restores the form");
  for (const width of [768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, "Registration overflow at " + width);
  }
  await writeFile(output + "/results.json", JSON.stringify({ checks, errors, accessibility }, null, 2));
  assert.deepEqual(errors, []);
  assert.equal(accessibility.reduce((sum, result) => sum + result.violations.length, 0), 0, "Accessibility violations remain; see results.json");
  console.log(JSON.stringify({ checks, runtimeErrors: errors, accessibility: accessibility.map(a => ({ route: a.route, violations: a.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length })) })), output }, null, 2));
} finally { await browser.close(); }



