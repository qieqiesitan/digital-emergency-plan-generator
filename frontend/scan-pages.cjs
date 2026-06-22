const { chromium } = require("@playwright/test");
const path = require("path");
const fs = require("fs");

const screenshotDir = "C:/Users/55061/Documents/数字化预案自动生成 2/screenshots";
if (!fs.existsSync(screenshotDir)) fs.mkdirSync(screenshotDir);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const log = (msg) => console.log("  " + msg);

  try {
    // Login first
    log("Logging in...");
    await page.goto("http://localhost:5173/login", { timeout: 15000 });
    await page.fill('input[placeholder*="邮箱"]', "test@test.com");
    await page.fill('input[type="password"]', "123456");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/dashboard", { timeout: 10000 });

    const pages = [
      { name: "01-dashboard", url: "http://localhost:5173/dashboard" },
      { name: "02-enterprises", url: "http://localhost:5173/enterprises" },
      { name: "03-enterprise-detail", url: "http://localhost:5173/enterprises/a1866bd9-5a30-43de-9c28-1853fd6164fa" },
      { name: "04-enterprise-edit", url: "http://localhost:5173/enterprises/a1866bd9-5a30-43de-9c28-1853fd6164fa/edit" },
      { name: "05-enterprise-new", url: "http://localhost:5173/enterprises/new" },
      { name: "06-plans", url: "http://localhost:5173/plans" },
      { name: "07-plans-new", url: "http://localhost:5173/plans/new" },
      { name: "08-ai-config", url: "http://localhost:5173/settings/ai-config" },
      { name: "09-profile", url: "http://localhost:5173/settings/profile" },
    ];

    for (const p of pages) {
      log(`Visiting ${p.name}...`);
      try {
        await page.goto(p.url, { timeout: 10000, waitUntil: "networkidle" });
        await page.waitForTimeout(800);
        // Check for question marks in visible text
        const bodyText = await page.textContent("body");
        const questionMarkCount = (bodyText.match(/\?/g) || []).length;
        // Check specifically for ???? patterns
        const garbledPattern = bodyText.match(/\?{3,}/g) || [];
        await page.screenshot({ path: path.join(screenshotDir, `${p.name}.png`), fullPage: true });
        if (garbledPattern.length > 0) {
          log(`  WARN: Found ${garbledPattern.length} garbled text areas (???+) on ${p.name}`);
          for (const g of garbledPattern) log(`    -> "${g}"`);
        } else if (questionMarkCount > 20) {
          log(`  WARN: ${questionMarkCount} question marks on ${p.name} (may be normal)`);
        } else {
          log(`  OK`);
        }
      } catch (e) {
        log(`  ERROR: ${e.message}`);
        await page.screenshot({ path: path.join(screenshotDir, `${p.name}-error.png`), fullPage: true });
      }
    }

    log("\nScreenshots saved to: " + screenshotDir);
  } finally {
    await browser.close();
  }
})();
