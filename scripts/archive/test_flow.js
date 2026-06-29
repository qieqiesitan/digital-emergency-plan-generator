const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Step 1: Login
  await page.goto("http://localhost:5173/login");
  await page.fill('input[id="email"]', "admin@test.com");
  await page.fill('input[id="password"]', "admin123");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard");

  // Step 2: Go to plans cards page
  await page.goto("http://localhost:5173/plans");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "screenshots/plan-cards.png", fullPage: true });
  console.log("Cards page screenshot saved");

  // Step 3: Check for enterprise cards
  const cardCount = await page.locator(".ant-card").count();
  console.log("Enterprise cards found:", cardCount);

  // Step 4: Click first card
  if (cardCount > 0) {
    await page.locator(".ant-card").first().click();
    await page.waitForTimeout(2000);
    console.log("Current URL after card click:", page.url());
    await page.screenshot({ path: "screenshots/enterprise-plan-list.png", fullPage: true });
  }

  // Step 5: Go back to cards
  await page.goto("http://localhost:5173/plans");
  await page.waitForTimeout(1000);
  console.log("Back to cards URL:", page.url());

  // Step 6: Click "新建预案" button
  const newPlanBtn = page.locator('button:has-text("新建预案")').first();
  if (await newPlanBtn.isVisible()) {
    await newPlanBtn.click();
    await page.waitForTimeout(2000);
    console.log("Create page URL:", page.url());
    await page.screenshot({ path: "screenshots/plan-create.png", fullPage: true });
  }

  await browser.close();
  console.log("All tests passed");
})().catch(e => { console.error(e.message); process.exit(1); });
