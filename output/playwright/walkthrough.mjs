import { chromium } from "playwright";
import fs from "fs";

const BASE = "http://localhost:5173";
const OUT = "output/playwright";
fs.mkdirSync(OUT, { recursive: true });

const shot = async (page, name) => {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`  [shot] ${name}`);
};

// capture console errors + failed requests
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const consoleErrors = [];
const failed = [];
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("pageerror", (e) => consoleErrors.push("PAGEERROR: " + e.message));
page.on("requestfailed", (r) => failed.push(r.url() + " :: " + (r.failure()?.errorText || "")));

// ---- 1. Login page ----
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
await shot(page, "01-login");
console.log("LOGIN URL:", page.url());
console.log("LOGIN TITLE:", await page.title());

// ---- 2. Login flow ----
try {
  await page.fill('input[placeholder*="邮箱"]', "test@test.com");
  await page.fill('input[placeholder*="密码"]', "123456");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 15000 });
  await page.waitForTimeout(1500);
  await shot(page, "02-dashboard");
  console.log("DASHBOARD URL:", page.url());
} catch (e) {
  console.log("LOGIN FAILED:", e.message);
  await shot(page, "02-login-after-submit");
}

// ---- 3. Navigation links inventory ----
const navLinks = await page.locator("a, .ant-menu-item, .ant-menu-submenu-title").allTextContents();
console.log("NAV ITEMS:", JSON.stringify(navLinks.map((s) => s.trim()).filter(Boolean)));

// ---- console/failed summary ----
console.log("CONSOLE ERRORS (" + consoleErrors.length + "):", consoleErrors.slice(0, 12));
console.log("FAILED REQUESTS (" + failed.length + "):", failed.slice(0, 12));

await browser.close();
