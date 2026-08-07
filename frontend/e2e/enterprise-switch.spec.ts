import { test, expect, type Page } from "@playwright/test";

const json = (status: number, body: unknown) => ({
  status,
  contentType: "application/json",
  body: JSON.stringify(body),
});

function makeFloor(id: string, eid: string, name: string) {
  return {
    id,
    enterprise_id: eid,
    name,
    sort_order: 0,
    floor_plan_url: null,
    description: null,
    canvas_width: 1200,
    canvas_height: 900,
    canvas_texts: [],
    is_default: true,
    zone_count: 1,
    risk_point_count: 0,
    created_at: "2026-08-07T00:00:00+08:00",
    updated_at: "2026-08-07T00:00:00+08:00",
  };
}

function makeZone(id: string, eid: string, floorId: string, name: string) {
  return {
    id,
    enterprise_id: eid,
    floor_id: floorId,
    floor_name: name === "A分区" ? "A一层" : "B一层",
    name,
    description: null,
    sort_order: 0,
    floor_plan_polygon: null,
    max_risk_level: null,
    effective_color: null,
    object_count: 0,
    created_at: "2026-08-07T00:00:00+08:00",
    updated_at: "2026-08-07T00:00:00+08:00",
  };
}

const FLOOR_A = makeFloor("floor-a", "ent-a", "A一层");
const FLOOR_B = makeFloor("floor-b", "ent-b", "B一层");

async function mockApis(page: Page) {
  await page.route("**/api/**", async route => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();
    if (path === "/api/v1/auth/login" && method === "POST") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { access_token: "t", refresh_token: "r", token_type: "bearer", expires_in: 7200 } }));
    }
    if (path === "/api/v1/users/me" && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "u", email: "qa_e2e_test@test.com", name: "t", role: "admin", created_at: "2026-08-07T00:00:00+08:00" } }));
    }
    if (path === "/api/v1/roles/my-menus" && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: [] }));
    }
    if (path === "/api/v1/enterprises" && method === "GET" && url.searchParams.has("page")) {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { items: [
        { id: "ent-a", name: "企业A", address: null, industry: null, created_at: "x", updated_at: "x" },
        { id: "ent-b", name: "企业B", address: null, industry: null, created_at: "x", updated_at: "x" },
      ], total: 2, page: 1, page_size: 100 } }));
    }
    const m = path.match(/\/enterprises\/(ent-a|ent-b)\/risk-management\/workbench$/);
    if (m && method === "GET") {
      const eid = m[1];
      const isA = eid === "ent-a";
      const floor = isA ? FLOOR_A : FLOOR_B;
      const requestedFloor = url.searchParams.get("floor_id");
      // 复现旧 bug 的失败路径：带着别的企业的楼层 id 请求 → 404
      if (requestedFloor && requestedFloor !== floor.id) {
        return route.fulfill(json(404, { code: 404, message: "楼层不存在" }));
      }
      return route.fulfill(json(200, { code: 0, message: "ok", data: {
        floors: [floor],
        current_floor_id: floor.id,
        zones: [makeZone(isA ? "zone-a" : "zone-b", eid, floor.id, isA ? "A分区" : "B分区")],
        risk_points: [],
        texts: [],
      } }));
    }
    const fm = path.match(/\/enterprises\/(ent-a|ent-b)\/risk-management\/floors$/);
    if (fm && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: [fm[1] === "ent-a" ? FLOOR_A : FLOOR_B] }));
    }
    return route.fulfill(json(404, { code: 404, message: "not found" }));
  });
}

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("邮箱").fill("qa_e2e_test@test.com");
  await page.getByPlaceholder("密码").fill("test123456");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(dashboard|enterprises)/, { timeout: 10000 });
}

test.describe("四色分布图工作台企业切换", () => {
  test("切换企业后显示新企业数据，楼层选择器不串台", async ({ page }) => {
    await mockApis(page);
    await login(page);

    await page.goto("/enterprises/ent-a/risk-mapping-workbench");
    await expect(page.locator('[data-testid="workbench-canvas"] canvas').first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("A分区", { exact: true })).toBeVisible();
    await expect(page.getByText("A一层", { exact: true }).first()).toBeVisible();

    // SPA 内导航（模拟"退出后进入另一个企业"：不刷新页面，store 会保留）
    await page.evaluate(() => {
      window.history.pushState({}, "", "/enterprises/ent-b/risk-mapping-workbench");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    await page.waitForURL(/\/enterprises\/ent-b\/risk-mapping-workbench/);
    await expect(page.locator('[data-testid="workbench-canvas"] canvas').first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("B分区", { exact: true })).toBeVisible();
    await expect(page.getByText("A分区", { exact: true })).toHaveCount(0);
    await expect(page.getByText("B一层", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("A一层", { exact: true })).toHaveCount(0);
    // 楼层选择器不应显示原始 id
    await expect(page.getByText("floor-a", { exact: true })).toHaveCount(0);
  });
});
