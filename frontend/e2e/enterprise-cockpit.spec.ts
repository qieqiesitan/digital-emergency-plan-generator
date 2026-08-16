import { test, expect, type Page } from "@playwright/test";

const json = (status: number, body: unknown) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

const SUMMARY = {
  code: 0,
  message: "ok",
  data: {
    risk_counts: { major: 2, larger: 4, general: 18, low: 10, total: 34 },
    zone_risks: [
      { zone_name: "生产车间", counts: { major: 1, larger: 2, general: 8, low: 2 }, total: 13 },
      { zone_name: "储罐区", counts: { major: 1, larger: 1, general: 2, low: 0 }, total: 4 },
    ],
    top_risks: [
      { name: "液氨储罐区", level: "重大", score: 82, responsible_unit: "生产部" },
    ],
    risk_index: 38,
    hazard_counts: { open: 3, due: 2, overdue: 0 },
    todos: [
      { priority: "high", title: "风险评估报告未生成", note: "建议本周完成 · AI 可辅助生成" },
    ],
    completion: { percent: 78, modules: [
      { key: "enterprise_info", label: "基本信息", done: true },
      { key: "reports", label: "报告", done: false },
    ] },
    recent_activities: [{ actor: "系统", action: "企业档案更新", time: "2026-08-16T10:32:00+08:00" }],
  },
};

async function mockApis(page: Page) {
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();
    if (path === "/api/v1/auth/login" && method === "POST") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { access_token: "t", refresh_token: "r", token_type: "bearer", expires_in: 7200 } }));
    }
    if (path === "/api/v1/users/me" && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "u", email: "qa_e2e_test@test.com", name: "t", role: "admin", created_at: "x" } }));
    }
    if (path === "/api/v1/roles/my-menus" && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: [] }));
    }
    if (path === "/api/v1/enterprises" && method === "GET" && url.searchParams.has("page_size")) {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { items: [
        { id: "ent-a", name: "企业A", address: null, industry: "危险化学品", created_at: "x", updated_at: "x" },
      ], total: 1, page: 1, page_size: 100 } }));
    }
    if (path === "/api/v1/enterprises/ent-a" && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "ent-a", name: "企业A", industry: "危险化学品", resources_count: 25, plans_count: 3, surrounding_info: {}, created_at: "x", updated_at: "x" } }));
    }
    if (path === "/api/v1/enterprises/ent-a/cockpit-summary" && method === "GET") {
      return route.fulfill(json(200, SUMMARY));
    }
    // 与 enterprise-switch.spec.ts 惯例一致：未匹配的 API 统一 404 fulfill，
    // 避免穿透到真实后端（401 会触发 axios 自动刷新链并清掉 mock 会话 token）。
    return route.fulfill(json(404, { code: 404, message: "not found" }));
  });
}

test("enterprise cockpit renders and navigates to risk module", async ({ page }) => {
  await mockApis(page);
  await page.goto("/login");
  await page.getByPlaceholder(/邮箱|账号/).fill("qa_e2e_test@test.com");
  await page.getByPlaceholder(/密码/).fill("password123");
  await page.getByRole("button", { name: /登\s*录/ }).click();
  // 登录为异步链路（POST → 存 token → 拉用户），等 SPA 跳到 /dashboard 后再整页跳转，
  // 避免整页导航中断登录请求导致 token 未落盘（与既有 e2e 惯例一致）。
  await page.waitForURL(/\/dashboard/, { timeout: 10000 });
  await page.goto("/enterprises/ent-a");
  await expect(page.getByText("企业驾驶舱")).toBeVisible();
  await expect(page.getByText("风险等级分布")).toBeVisible();
  await expect(page.getByText("风险雷达")).toBeVisible();
  await page.getByText("风险管控", { exact: true }).click();
  await expect(page).toHaveURL(/\/enterprises\/ent-a\/risk-management$/);
  await expect(page.getByText("返回企业驾驶舱")).toBeVisible();
  await expect(page.getByText("数据编辑")).toBeVisible();
  await page.getByText("返回企业驾驶舱").click();
  await expect(page).toHaveURL(/\/enterprises\/ent-a$/);
});
