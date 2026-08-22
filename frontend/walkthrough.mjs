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

// ---- 2. Login flow (correct creds) ----
try {
  await page.fill('input[placeholder*="邮箱"]', "qa_e2e_test@test.com");
  await page.fill('input[placeholder*="密码"]', "test123456");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard", { timeout: 15000 });
  await page.waitForTimeout(1500);
  console.log("DASHBOARD URL:", page.url());
} catch (e) {
  console.log("LOGIN FAILED:", e.message);
  await shot(page, "02-login-after-submit");
  await browser.close();
  process.exit(1);
}

await shot(page, "02-dashboard");

// ---- 3. Navigation links inventory ----
const menuItems = await page.locator("aside .ant-menu-item, aside .ant-menu-submenu-title, nav a").allTextContents();
console.log("NAV ITEMS:", JSON.stringify(menuItems.map((s) => s.trim()).filter(Boolean).slice(0, 40)));

// ---- 4. Enterprise cockpit deep walk ----
// first enterprise id from list
await page.goto(`${BASE}/enterprises`, { waitUntil: "networkidle", timeout: 20000 });
await page.waitForTimeout(1000);
// click first row's 企业名称 link
const firstEnt = page.locator("table tbody tr").first();
const entHref = await firstEnt.locator("a").first().getAttribute("href");
const entText = (await firstEnt.locator("td").first().innerText()).trim();
console.log("FIRST ENTERPRISE:", entText, "HREF:", entHref);

try {
  await firstEnt.locator("a").first().click();
  await page.waitForLoadState("networkidle", { timeout: 20000 });
  await page.waitForTimeout(1500);
  console.log("COCKPIT URL:", page.url());
  await shot(page, "05-enterprise-cockpit");
} catch (e) {
  console.log("COCKPIT FAIL:", e.message);
}
const entId = page.url().match(/enterprises\/([a-f0-9-]+)/)?.[1] || null;
console.log("ENT ID:", entId);

// ---- 5. Plan module flow (核心：AI 生成预案) ----
try {
  await page.goto(`${BASE}/enterprises/${entId}/plans`, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForTimeout(1200);
  console.log("PLAN LIST URL:", page.url());
  await shot(page, "07-plan-list");
} catch (e) {
  console.log("PLAN LIST FAIL:", e.message);
}

// go to plan create
try {
  const newBtn = page.locator("button:has-text('新建预案'), button:has-text('新建'), a:has-text('新建预案')").first();
  if (await newBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await newBtn.click();
    await page.waitForLoadState("networkidle", { timeout: 20000 });
    await page.waitForTimeout(1200);
    console.log("PLAN CREATE URL:", page.url());
    await shot(page, "08-plan-create");
  } else {
    console.log("NO NEW PLAN BUTTON FOUND");
  }
} catch (e) {
  console.log("PLAN CREATE FAIL:", e.message);
}

console.log("CONSOLE ERRORS (" + consoleErrors.length + "):", consoleErrors.slice(0, 15));
console.log("FAILED REQUESTS (" + failed.length + "):", failed.slice(0, 15));

await browser.close();
