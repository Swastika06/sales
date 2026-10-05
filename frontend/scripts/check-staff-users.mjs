// Staff-user checks intercept all API requests; no accounts or emails are created.
import assert from "node:assert/strict";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import { chromium } from "playwright";

const base = process.env.PORTAL_TEST_URL || "http://localhost:5173";
const widget = fs.readFileSync(new URL("../ezextend/react-design.jsx", import.meta.url), "utf8");
const bundle = await build({ stdin: { contents: 'import React from "react"; import {createRoot} from "react-dom/client"; const render = value => createRoot(document.getElementById("widget")).render(value);\n' + widget, loader: "jsx", resolveDir: fileURLToPath(new URL("..", import.meta.url)) }, bundle: true, write: false, format: "iife" });
const browser = await chromium.launch({ channel: "msedge", headless: true });
const roles = [{ code: "TCG_ADMIN", name: "Admin" }, { code: "TCG_FINANCE", name: "Finance" }, { code: "TCG_SALES", name: "Sales" }, { code: "TCG_LEGAL", name: "Legal" }];
try {
  for (const embedded of [false, true]) {
    const page = await browser.newPage({ viewport: { width: embedded ? 375 : 1280, height: 900 } });
    page.setDefaultTimeout(10000);
    const errors = [];
    const accounts = [];
    let staffRequests = 0;
    let admin = true;
    page.on("pageerror", error => errors.push(error.message));
    await page.addInitScript(() => { localStorage.setItem("partner_portal_token", "admin-session"); localStorage.setItem("staff_test", "admin-session"); });
    await page.route("**/api/v1/**", async route => {
      const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
      let data;
      if (path === "/auth/me") data = { id: "admin", full_name: "Admin User", email: "admin@example.com", is_active: true, is_superuser: false, must_change_password: false, partner_id: null, roles: [admin ? "TCG_ADMIN" : "TCG_SALES"], permissions: [] };
      else if (path === "/staff-users/roles") { staffRequests++; data = roles; }
      else if (path === "/staff-users") {
        staffRequests++;
        if (route.request().method() === "POST") {
          const body = route.request().postDataJSON();
          assert.deepEqual(Object.keys(body).sort(), ["email", "full_name", "role_code"]);
          data = { id: body.email, ...body, roles: [body.role_code], is_active: true, must_change_password: true, mail_status: "PENDING" };
          accounts.push(data);
        } else data = accounts;
      } else if (path.startsWith("/staff-users/") && path.endsWith("/invitation")) {
        staffRequests++;
        data = accounts.find(account => account.id === decodeURIComponent(path.split("/")[2]));
        assert.ok(data);
        data.mail_status = "PENDING";
      } else throw new Error("Unexpected API request: " + path);
      await route.fulfill({ status: route.request().method() === "POST" ? 201 : 200, contentType: "application/json", body: JSON.stringify(data) });
    });
    async function mount() {
      await page.goto(base + "/staff-users");
      if (embedded) {
        await page.setContent('<div id="widget"></div>');
        await page.evaluate(({ api }) => { window.TCG_PARTNER_PORTAL_CONFIG = { apiBaseUrl: api, initialPath: "/staff-users", loadFonts: false, tokenStorageKey: "staff_test" }; }, { api: base + "/api/v1" });
        await page.addScriptTag({ content: bundle.outputFiles[0].text });
      }
    }
    await mount();
    await page.getByRole("heading", { name: "Staff users", exact: true }).waitFor();
    assert.equal(await page.locator('input[type="password"]').count(), 0);
    for (const role of roles) {
      await page.getByLabel("Full name", { exact: true }).fill(role.name + " User");
      await page.getByLabel("Email", { exact: true }).fill(role.code.toLowerCase() + "@example.com");
      await page.locator('select[name="role_code"]').selectOption(role.code);
      await page.getByRole("button", { name: "Create staff account", exact: true }).click();
      await page.getByRole("status").filter({ hasText: "Account created" }).waitFor();
      await page.locator(".user-row").filter({ hasText: role.name + " User" }).filter({ hasText: "First-login password change pending" }).waitFor();
    }
    assert.equal(accounts.length, 4);
    await page.locator(".user-row").filter({ hasText: "Finance User" }).getByRole("button", { name: "Send new invitation" }).click();
    await page.getByRole("status").filter({ hasText: "A new temporary password has been queued" }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    admin = false;
    const prior = staffRequests;
    await mount();
    await page.getByText("Administrator access is required to manage staff users.").waitFor();
    assert.equal(staffRequests, prior, "Non-admin cannot request staff management data");
    assert.deepEqual(errors, []);
    console.log((embedded ? "Embedded mobile" : "Main desktop") + " staff creation, all roles, invitation status, and admin restriction passed");
    await page.close();
  }
} finally { await browser.close(); }
