// 计划 7 冒烟：单元详情页（风险点关联 / 平面图落点 / 品种台账关联）。
// 运行位置：emergency-plan-frontend 容器（/tmp），截图输出 /tmp。
import { chromium } from "/app/node_modules/playwright/index.mjs";

const BASE = "http://localhost:5173";
const EID = "94804158-cc33-464d-9aef-025ec90226be";
const UNIT = "37451eb8-3e22-4be1-87fd-c7a0b9e9c24e";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
const errors = [];
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text().slice(0, 200));
});
page.on("pageerror", (e) => errors.push("PAGEERROR: " + e.message.slice(0, 200)));

const log = (...args) => console.log("[smoke]", ...args);
const shot = async (name) => {
  await page.screenshot({ path: `/tmp/${name}.png`, fullPage: true });
  log("shot", name);
};

// 1. 登录
await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
await page.fill('input[placeholder*="邮箱"]', "test@test.com");
await page.fill('input[placeholder*="密码"]', "123456");
await page.click('button[type="submit"]');
await page.waitForURL("**/dashboard", { timeout: 20000 });
log("登录成功", page.url());

// 2. 单元详情页
await page.goto(`${BASE}/enterprises/${EID}/major-hazard/units/${UNIT}`, {
  waitUntil: "networkidle",
});
await page.waitForTimeout(1500);
log("单元页标题:", (await page.locator("h1").first().textContent()) ?? "(无)");
await shot("linkage-01-unit-basic");

// 3. 关联风险点
const riskCard = page.locator(".ant-card").filter({ hasText: "关联风险点" }).first();
await riskCard.locator(".ant-select").click();
await page.waitForTimeout(500);
await shot("linkage-02-risk-dropdown");
await page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option").first().click();
await page.waitForTimeout(1200);
log("风险点已选:", (await riskCard.locator(".ant-select-selection-item").textContent()) ?? "(空)");

// 4. 品种与存量 → 台账关联 + 设计最大量建议
await page.getByRole("tab", { name: "品种与存量" }).click();
await page.waitForTimeout(600);
await page.getByRole("button", { name: /添加品种/ }).click();
await page.waitForTimeout(400);
await page.locator("tbody tr").first().locator(".ant-select").click();
await page.waitForTimeout(500);
await shot("linkage-03-ledger-dropdown");
await page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option").first().click();
await page.waitForTimeout(1500);
const hasSuggestion = await page
  .getByText("台账建议")
  .first()
  .isVisible()
  .catch(() => false);
log("台账建议可见:", hasSuggestion);
if (hasSuggestion) {
  await page.getByRole("button", { name: "采用" }).first().click();
  await page.waitForTimeout(400);
  const qValue = await page.locator("tbody tr").first().locator("input").first().inputValue();
  log("采用后台账建议已写入设计最大量:", qValue);
}
await shot("linkage-04-ledger-suggestion");

// 5. 平面图落点：选楼层 → 绘制 → 保存 → 刷新验证
await page.getByRole("tab", { name: "基本信息" }).click();
await page.waitForTimeout(400);
const polyCard = page.locator(".ant-card").filter({ hasText: "平面图落点" }).first();
await polyCard.locator(".ant-select").click();
await page.waitForTimeout(500);
await page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option").first().click();
await page.waitForTimeout(700);
await polyCard.getByRole("button", { name: /绘制边界/ }).click();
await page.waitForTimeout(300);
const svg = polyCard.locator('svg[viewBox="0 0 100 100"]');
const box = await svg.boundingBox();
if (!box) throw new Error("画布未渲染");
for (const [rx, ry] of [
  [0.25, 0.25],
  [0.75, 0.25],
  [0.75, 0.75],
  [0.25, 0.75],
]) {
  await page.mouse.click(box.x + box.width * rx, box.y + box.height * ry);
  await page.waitForTimeout(180);
}
await shot("linkage-05-polygon-drawn");
await polyCard.getByRole("button", { name: /保存落点/ }).click();
await page.waitForTimeout(1500);
await shot("linkage-06-polygon-saved");

await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const polyAfterReload = await polyCard.locator("svg polygon").count();
log("刷新后多边形数量:", polyAfterReload);
await shot("linkage-07-after-reload");

// 6. 清空落点 → 刷新验证消失
await polyCard.getByRole("button", { name: /清空落点/ }).click();
await page.waitForTimeout(1500);
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const polyAfterClear = await polyCard.locator("svg polygon").count();
log("清空后多边形数量:", polyAfterClear);
await shot("linkage-08-after-clear");

log("控制台错误数:", errors.length);
if (errors.length) log("错误样本:", JSON.stringify(errors.slice(0, 5)));
await browser.close();
