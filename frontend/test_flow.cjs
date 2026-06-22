const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const screenshotsDir = "C:/Users/55061/Documents/数字化预案自动生成 2/screenshots";

  try {
    // Step 1: Login
    await page.goto("http://localhost:5173/login", { waitUntil: "networkidle" });
    await page.fill('input[placeholder="邮箱"]', "admin@test.com");
    await page.fill('input[placeholder="密码"]', "admin123");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/dashboard", { timeout: 10000 });
    console.log("Login success, on dashboard");

    // Step 2: Go to plans cards page
    await page.goto("http://localhost:5173/plans", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: screenshotsDir + "/plan-cards.png", fullPage: true });
    console.log("Cards page screenshot saved");

    // Step 3: Check for enterprise cards
    const cardCount = await page.locator(".ant-card").count();
    console.log("Enterprise cards found:", cardCount);

    // Step 4: Click first card to enter enterprise plan list
    if (cardCount > 0) {
      await page.locator(".ant-card").first().click();
      await page.waitForTimeout(2000);
      console.log("After card click, URL:", page.url());
      await page.screenshot({ path: screenshotsDir + "/enterprise-plan-list.png", fullPage: true });
    }

    // Step 5: Go back to cards
    await page.goto("http://localhost:5173/plans", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);

    // Step 6: Click "新建预案" on the header (not on a card)
    const topNewBtn = page.locator('button:has-text("新建预案")').first();
    if (await topNewBtn.isVisible()) {
      await topNewBtn.click();
      await page.waitForTimeout(2000);
      console.log("Create page URL:", page.url());
      await page.screenshot({ path: screenshotsDir + "/plan-create.png", fullPage: true });
    }

    console.log("All checks passed");
  } catch (e) {
    console.error("Test failed:", e.message);
    await page.screenshot({ path: screenshotsDir + "/test-failure.png", fullPage: true });
    throw e;
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e.message); process.exit(1); });
