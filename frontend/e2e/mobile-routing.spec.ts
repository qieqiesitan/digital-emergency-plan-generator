import { test, expect } from "@playwright/test";

test("mobile /m/login should render mobile login screen", async ({ page }) => {
  // 直接访问移动端登录页（全新页面加载）
  await page.goto("http://localhost:5173/m/login", { waitUntil: "networkidle" });

  // 等待页面渲染
  await page.waitForTimeout(2000);

  // 检查是否有移动端特有的元素
  const html = await page.content();

  // 移动端登录页应该包含移动端特征的文本
  const hasMobileContent =
    html.includes("移动端") ||
    html.includes("mobile") ||
    html.includes("MobileApp") ||
    html.includes("m/login") ||
    html.includes("数字化应急预案");

  console.log("Page title:", await page.title());
  console.log("Has mobile marker:", hasMobileContent);

  // 截图
  await page.screenshot({ path: "test-results/mobile-login-test.png", fullPage: true });

  expect(hasMobileContent).toBeTruthy();
});

test("desktop /login should render desktop login", async ({ page }) => {
  await page.goto("http://localhost:5173/login", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const html = await page.content();

  const hasAntDesign = html.includes("ant-") || html.includes("antd");
  console.log("Desktop has Ant Design:", hasAntDesign);
  await page.screenshot({ path: "test-results/desktop-login-test.png", fullPage: true });

  expect(hasAntDesign).toBeTruthy();
});
