import { test } from "@playwright/test";
test("check resources tab", async ({ page }) => {
  await page.goto("http://localhost:5173/login");
  await page.fill('input[placeholder*="邮箱"]', "test@test.com");
  await page.fill('input[placeholder*="密码"]', "123456");
  await page.click('button[type="submit"]');
  await page.waitForURL("**/dashboard");
  await page.goto("http://localhost:5173/enterprises/94804158-cc33-464d-9aef-025ec90226be");
  await page.waitForSelector('.ant-tabs');
  await page.click('.ant-tabs-tab:has-text("应急资源")');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "screenshots/resources-tab.png", fullPage: false });
  
  const consoleLogs: string[] = [];
  page.on("console", msg => consoleLogs.push(msg.text()));
  const rows = await page.locator('.ant-table-row').count();
  console.log("Table rows:", rows);
  console.log("Console logs:", consoleLogs.slice(-5));
});
