// Layout fixtures intercept API requests; no accounts or records are changed.
import assert from "node:assert/strict";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const base = process.env.PORTAL_TEST_URL || "http://localhost:5173";
const output = new URL("../../output/layout-review/", import.meta.url);
fs.mkdirSync(output, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true });
const user = { id: "admin", email: "admin@example.com", full_name: "TCG Administrator", is_active: true, is_superuser: true, partner_id: null, roles: ["TCG_ADMIN"], permissions: [], must_change_password: false };
const application = { id: "application-1", partner_id: "partner-1", company_name: "Sample Reseller Technologies Private Limited", email: "applicant@example.com", status: "PENDING_ADMIN_REVIEW", revision: 1, assigned_to_id: null, review_comment: null, capabilities: ["RESELLER"], required_documents: [], documents: [], mail_status: "SENT" };
try {
  for (const [width, height] of [[1362, 594], [1362, 420], [800, 594], [375, 594]]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.addInitScript(() => localStorage.setItem("partner_portal_token", "layout-test-admin"));
    await page.route("**/api/v1/**", async route => {
      const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
      let data;
      if (path === "/auth/me") data = user;
      else if (path === "/onboarding/applications") data = [application];
      else if (path === "/onboarding/reviewers") data = [];
      else if (path === "/commercial/summary") data = { basis: "Forecast", opportunities: 0, totals: {}, undisclosed: {} };
      else throw new Error("Unexpected request: " + path);
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data) });
    });
    await page.goto(base + "/onboarding-review");
    await page.getByRole("heading", { name: "Applications & legal routing" }).waitFor();
    const queue = page.locator(".onboarding-queue button");
    assert.equal(await queue.evaluate(element => getComputedStyle(element).backgroundColor), "rgb(255, 255, 255)", "Unselected queue card stays white");
    await queue.hover();
    assert.equal(await queue.evaluate(element => getComputedStyle(element).transform), "none", "Queue hover does not shift the card");
    await queue.click();
    await page.waitForFunction(() => getComputedStyle(document.querySelector(".onboarding-queue button")).backgroundColor === "rgb(231, 241, 255)");
    await page.getByText("Add legal reviewer", { exact: true }).click();
    await page.locator('.edit-panel input[name="full_name"]').waitFor();
    if (width > 640) {
      const layout = await page.evaluate(() => {
        const sidebar = document.querySelector(".sidebar").getBoundingClientRect();
        const nav = document.querySelector(".sidebar nav");
        const user = document.querySelector(".sidebar-user").getBoundingClientRect();
        return { sidebarBottom: sidebar.bottom, sidebarTop: sidebar.top, userBottom: user.bottom, navBottom: nav.getBoundingClientRect().bottom, userTop: user.top, navHeight: nav.clientHeight, navScrollHeight: nav.scrollHeight };
      });
      assert.equal(layout.sidebarTop, 0);
      assert.ok(Math.abs(layout.sidebarBottom - height) < 1, "Sidebar fills the viewport");
      assert.ok(layout.userBottom <= height, "Account controls fit inside the sidebar");
      assert.ok(layout.navBottom <= layout.userTop + 1, "Navigation stays above account controls");
      assert.ok(layout.navScrollHeight > layout.navHeight, "Short viewport uses a scrollable menu");
      await page.evaluate(() => { const nav = document.querySelector(".sidebar nav"); nav.scrollTop = nav.scrollHeight; window.scrollTo(0, 200); });
      await page.waitForFunction(() => document.querySelector(".sidebar nav").scrollTop > 0);
      assert.ok(Math.abs(await page.locator(".sidebar").evaluate(element => element.getBoundingClientRect().top)) < 1, "Sidebar stays pinned while the page scrolls");
      assert.ok(await page.getByRole("button", { name: "Sign out", exact: true }).evaluate(element => element.getBoundingClientRect().bottom <= innerHeight), "Sign out stays visible");
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, "Page fits viewport width");
    await page.evaluate(() => {
      window.scrollTo(0, 0);
      const nav = document.querySelector(".sidebar nav");
      nav.scrollTop = 0; nav.scrollLeft = 0;
    });
    await page.screenshot({ path: fileURLToPath(new URL(`onboarding-review-${width}x${height}.png`, output)) });
    await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Overview", exact: true }).click();
    await page.getByRole("heading", { name: "Good to see you, TCG." }).waitFor();
    await page.waitForFunction(() => scrollY === 0);
    assert.ok(await page.locator(".page-heading").evaluate(element => element.getBoundingClientRect().top > 0), "Route change starts with heading visible");
    assert.deepEqual(errors, []);
    console.log(`PASS sidebar scrolling, queue styles, and navigation at ${width}x${height}`);
    await page.close();
  }
  for (const width of [1362, 375]) {
    const page = await browser.newPage({ viewport: { width, height: 594 } });
    await page.goto(base + "/login");
    await page.getByRole("heading", { name: "Sign in", exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, "Login fits viewport width");
    await page.screenshot({ path: fileURLToPath(new URL(`partner-login-${width}.png`, output)) });
    await page.close();
  }
} finally { await browser.close(); }
