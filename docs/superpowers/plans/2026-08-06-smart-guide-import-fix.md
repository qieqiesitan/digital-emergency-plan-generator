# 智能引导导入 422 修复与生成去重 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修复 AI 智能引导导入 422（AI 对象误标风险点无坐标），让 AI 生成前参考现有分区避免重复，并在导入时跳过重名分区。

**架构：** 后端 `_normalize_smart_guide_hierarchy` 强制 AI 对象 `is_risk_point=False`；`smart-guide` 路由查库注入现有分区/对象清单到 prompt；前端 `RiskSmartGuideModal` 打开时拉现有分区名，导入前用纯函数 `buildImportPlan` 过滤重名分区并计数；`RiskManagementTab` 补传表单坐标字段。

**技术栈：** Python 3.12 + FastAPI + Pydantic v2 / React 18 + antd v6 + TanStack Query + Vitest + Playwright

---

## 文件结构

- `backend/app/services/risk_ai_service.py`（修改）：`_normalize_smart_guide_hierarchy` 强制 `is_risk_point=False`；`smart_guide` 增加 `existing_names` 参数与 prompt 去重约束。
- `backend/app/routers/risk_management.py`（修改）：`ai_smart_guide` 路由查库注入现有分区/对象名。
- `backend/tests/test_smart_guide_import.py`（新增）：normalize 强制与 prompt 注入测试。
- `frontend/src/utils/smartGuideImport.ts`（新增）：`buildImportPlan` 纯函数，过滤重名分区。
- `frontend/src/utils/smartGuideImport.test.ts`（新增）：重名过滤单测。
- `frontend/src/components/enterprise/RiskSmartGuideModal.tsx`（修改）：拉现有分区、导入去重、`is_risk_point:false`、成功消息含跳过数。
- `frontend/src/pages/Enterprise/RiskManagementTab.tsx`（修改）：object 分支补传坐标字段。
- `frontend/e2e/smart-guide-import.spec.ts`（新增）：智能引导导入 E2E。

---

### 任务 1：后端 normalize 强制 is_risk_point=False

**文件：**
- 创建：`backend/tests/test_smart_guide_import.py`
- 修改：`backend/app/services/risk_ai_service.py:83-130`

- [ ] **步骤 1：编写失败的测试**

```python
from app.services.risk_ai_service import _normalize_smart_guide_hierarchy

def test_normalize_smart_guide_forces_risk_point_false():
    data = {
        "zones": [
            {
                "name": "储罐区",
                "objects": [
                    {"name": "1号储罐", "is_risk_point": True, "units": [], "events": []},
                    {"name": "2号储罐", "units": [], "events": []},
                ],
            }
        ]
    }
    result = _normalize_smart_guide_hierarchy(data)
    objs = result["zones"][0]["objects"]
    assert objs[0]["is_risk_point"] is False
    assert objs[1]["is_risk_point"] is False
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_smart_guide_import.py -v`
预期：FAIL，`assert objs[0]["is_risk_point"] is False` 处 `True is False`。

- [ ] **步骤 3：编写最少实现代码**

在 `_normalize_smart_guide_hierarchy` 的对象循环内、处理 `units` 之前插入：

```python
            # AI 文本生成无画布坐标，不能产生合法风险点；一律作为普通分析对象导入
            obj["is_risk_point"] = False
```

- [ ] **步骤 4：运行测试验证通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_smart_guide_import.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/risk_ai_service.py backend/tests/test_smart_guide_import.py
git commit -m "fix(risk-ai): force smart guide objects to non-risk-point on normalize"
```

---

### 任务 2：后端 smart_guide 注入现有分区清单

**文件：**
- 修改：`backend/app/services/risk_ai_service.py:285-332`（`smart_guide`）
- 修改：`backend/app/routers/risk_management.py:764-772`（`ai_smart_guide`）
- 测试：`backend/tests/test_smart_guide_import.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
from unittest.mock import AsyncMock, patch
from app.services.risk_ai_service import smart_guide

@pytest.mark.asyncio
async def test_smart_guide_prompt_includes_existing_names():
    captured = {}

    async def fake_llm(messages, ai_config, timeout=120):
        captured["messages"] = messages
        return '{"zones": [], "summary": {}}'

    with patch("app.services.risk_ai_service.llm_text_completion", new=fake_llm):
        await smart_guide(
            "描述",
            {"name": "测试企业"},
            ai_config=object(),
            existing_names={"zones": ["储罐区"], "objects": ["1号储罐"]},
        )

    prompt = captured["messages"][-1]["content"]
    assert "储罐区" in prompt
    assert "1号储罐" in prompt
    assert "不得生成与现有分区" in prompt
```

说明：`smart_guide` 当前签名无 `existing_names` 参数，此测试先验证其存在与注入；若 monkeypatch 目标不对，以实际 import 方式为准（`risk_ai_service` 顶部 `from app.services.llm_client import llm_text_completion`）。

- [ ] **步骤 2：运行测试验证失败**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_smart_guide_import.py -v`
预期：FAIL，`TypeError: smart_guide() got an unexpected keyword argument 'existing_names'`。

- [ ] **步骤 3：编写实现代码**

修改 `smart_guide` 签名与 prompt：

```python
async def smart_guide(
    description: str,
    enterprise_info: dict,
    ai_config: AIConfig,
    existing_names: dict | None = None,
) -> dict:
    existing_names = existing_names or {}
    existing_zones = existing_names.get("zones") or []
    existing_objects = existing_names.get("objects") or []
    existing_summary = ""
    if existing_zones:
        existing_summary += "现有分区：" + "、".join(existing_zones) + "\n"
    if existing_objects:
        existing_summary += "现有对象：" + "、".join(existing_objects) + "\n"
    prompt = (
        f"用户描述了以下企业区域，请分析并生成完整的风险分级管控层级结构"
        f"（分区 → 对象 → 单元 → 事件 → 措施）。\n\n"
        f"用户描述：\n{description}\n\n"
        f"企业信息：\n{json.dumps(enterprise_info, ensure_ascii=False, indent=2)}\n\n"
    )
    if existing_summary:
        prompt += f"企业已有层级（请勿重复生成）：\n{existing_summary}\n"
    prompt += (
        f"要求：\n"
        f"1. 解析描述中的实体关系，生成到措施层级\n"
        f"2. 每个事件使用 LS 矩阵法评估（L: 1-5, S: 1-5），含 risk_level 和 risk_score\n"
        f"3. 每事件至少 2 条管控措施\n"
        f"4. 最多生成 5 个分区、50 个对象\n"
        f"5. 不得生成与现有分区名称相同或语义重复的分区；描述若已对应现有分区，"
        f"将该分区名写入 summary 的 duplicates 数组，而不是重复生成\n"
        f"6. 同一区域内多个同类设备用编号区分命名（如「1号储罐」「2号储罐」），避免对象名重复\n"
        f"7. 所有对象 is_risk_point 一律输出 false（风险点由用户在画布上手动标记）\n\n"
        f'输出 JSON 格式（完整层级）：\n'
        f'{{"zones": [{{"name": "...", "description": "...", '
        f'"objects": [{{"name": "...", "category": "...", '
        f'"is_risk_point": false, "units": [{{"name": "...", '
        f'"unit_type": "...", "events": [{{"accident_type": "...", '
        f'"risk_level": "重大|较大|一般|低", "risk_score": "R=XX", '
        f'"method_type": "LS", "method_params": {{"l": X, "s": X}}, '
        f'"measures": [...]}}]}}]}}]}}]}}\n'
        f"只输出 JSON，不要任何解释。"
    )
```

修改路由 `ai_smart_guide`，查库并传参：

```python
@router.post("/ai/smart-guide", response_model=ApiResponse[SmartGuideResponse])
async def ai_smart_guide(body: SmartGuideRequest, enterprise_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    ai_config = await _get_ai_config(current_user.id, db)
    ent = await _get_ent(enterprise_id, current_user.id, db)
    info = {"name":ent.name,"industry":ent.industry,"business_scope":ent.business_scope,"building_overview":ent.building_overview,"hazardous_chemicals":ent.hazardous_chemicals,"special_equipment":ent.special_equipment}
    zone_rows = (await db.execute(select(RiskZone.name).where(RiskZone.enterprise_id == enterprise_id))).scalars().all()
    object_rows = (await db.execute(select(RiskObject.name).where(RiskObject.enterprise_id == enterprise_id))).scalars().all()
    existing_names = {"zones": list(zone_rows), "objects": list(object_rows)}
    result = await smart_guide(body.description, info, ai_config, existing_names=existing_names)
    return ApiResponse(data=SmartGuideResponse(hierarchy=result.get("zones",[]), summary=result.get("summary",{})))
```

- [ ] **步骤 4：运行测试验证通过**

运行：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_smart_guide_import.py -v`
预期：PASS

- [ ] **步骤 5：回归运行后端全部风险相关测试**

运行：`backend/.venv/Scripts/python.exe -m pytest -q backend/tests/test_risk_mapping_service.py backend/tests/test_risk_mapping_workbench.py backend/tests/test_risk_mapping_cascade.py backend/tests/test_risk_hierarchy.py`
预期：全部 PASS

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/risk_ai_service.py backend/app/routers/risk_management.py backend/tests/test_smart_guide_import.py
git commit -m "feat(risk-ai): inject existing zones/objects into smart guide prompt"
```

---

### 任务 3：前端 buildImportPlan 纯函数 + 单测

**文件：**
- 创建：`frontend/src/utils/smartGuideImport.ts`
- 创建：`frontend/src/utils/smartGuideImport.test.ts`

- [ ] **步骤 1：编写失败的测试**

```ts
import { describe, expect, it } from "vitest";
import { buildImportPlan } from "./smartGuideImport";
import type { SmartGuideZone } from "@/types/riskManagement";

const hierarchy: SmartGuideZone[] = [
  { name: "储罐区", description: null, objects: [] },
  { name: "新车间", description: null, objects: [] },
  { name: "储罐区", description: "重名", objects: [] },
];

describe("buildImportPlan", () => {
  it("过滤与现有分区重名的分区并计数", () => {
    const { filteredHierarchy, skippedZones } = buildImportPlan(hierarchy, {}, new Set(["储罐区"]));
    expect(filteredHierarchy.map(z => z.name)).toEqual(["新车间"]);
    expect(skippedZones).toEqual(["储罐区", "储罐区"]);
  });

  it("nameOverrides 改名后的名称参与去重", () => {
    const { filteredHierarchy, skippedZones } = buildImportPlan(
      hierarchy,
      { "z-1": "储罐区" },
      new Set(["储罐区"]),
    );
    expect(filteredHierarchy.map(z => z.name)).toEqual(["储罐区", "新车间"].filter(n => n !== "储罐区"));
    expect(skippedZones).toContain("储罐区");
  });
});
```

说明：`nameOverrides` 的 key 为 `z-{index}`，与组件既有约定一致；第二个用例中 `z-1` 对应「新车间」被改名为「储罐区」，故被跳过。

- [ ] **步骤 2：运行测试验证失败**

运行：`npx vitest run src/utils/smartGuideImport.test.ts`
预期：FAIL，`Cannot find module './smartGuideImport'`。

- [ ] **步骤 3：编写实现代码**

```ts
import type { SmartGuideZone } from "@/types/riskManagement";

export interface ImportPlan {
  filteredHierarchy: SmartGuideZone[];
  skippedZones: string[];
}

/** 过滤与现有分区重名的分区；nameOverrides 以 z-{index} 为 key（与组件约定一致）。 */
export function buildImportPlan(
  hierarchy: SmartGuideZone[],
  nameOverrides: Record<string, string>,
  existingZoneNames: Set<string>,
): ImportPlan {
  const filteredHierarchy: SmartGuideZone[] = [];
  const skippedZones: string[] = [];
  hierarchy.forEach((zone, zi) => {
    const effectiveName = nameOverrides[`z-${zi}`] ?? zone.name;
    if (existingZoneNames.has(effectiveName)) {
      skippedZones.push(effectiveName);
      return;
    }
    filteredHierarchy.push(zone);
  });
  return { filteredHierarchy, skippedZones };
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`npx vitest run src/utils/smartGuideImport.test.ts`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/utils/smartGuideImport.ts frontend/src/utils/smartGuideImport.test.ts
git commit -m "feat(risk-ai): add buildImportPlan dedup pure function"
```

---

### 任务 4：RiskSmartGuideModal 接入现有分区与去重

**文件：**
- 修改：`frontend/src/components/enterprise/RiskSmartGuideModal.tsx`

- [ ] **步骤 1：引入依赖与查询**

在 import 区追加：

```ts
import { listZones } from "@/services/riskManagementService";
import { buildImportPlan } from "@/utils/smartGuideImport";
```

在组件内（`guideMut` 之前）追加：

```ts
const { data: existingZones = [] } = useQuery({
  queryKey: ["risk-zones", enterpriseId],
  queryFn: () => listZones(enterpriseId),
  enabled: open,
});
const existingZoneNames = useMemo(() => new Set(existingZones.map(z => z.name)), [existingZones]);
```

补充 import：`useQuery` 从 `@tanstack/react-query` 引入（当前仅 `useMutation`）。

- [ ] **步骤 2：改造导入逻辑**

在 `importMut.mutationFn` 开头，`keySet` 之后插入：

```ts
      const { filteredHierarchy, skippedZones } = buildImportPlan(hierarchy, nameOverrides, existingZoneNames);
```

将 `for (let zi = 0; zi < hierarchy.length; zi++) {` 改为遍历 `filteredHierarchy`，并同步调整索引映射：

```ts
      for (let zi = 0; zi < filteredHierarchy.length; zi++) {
        const zone = filteredHierarchy[zi];
        const zoneKey = "z-" + zi;
        if (!keySet.has(zoneKey)) continue;
```

说明：`filteredHierarchy` 是过滤后的数组，`z-{zi}` 索引与 treeData 的 key 不再一一对应，但 checkedKeys 以原始 `hierarchy` 生成；为避免错位，将 `treeData` 与导入遍历统一改为基于原始 `hierarchy` 过滤后的同一数组，并把组件内 `hierarchy` 状态在预览前替换为 `filteredHierarchy` 不可行（checkedKeys 已生成）。因此改为：`treeData` 与 `countChecked` 均保持原始 hierarchy；导入遍历使用 `filteredHierarchy` 时，`zoneKey` 用原始索引查找：

```ts
      for (let zi = 0; zi < filteredHierarchy.length; zi++) {
        const zone = filteredHierarchy[zi];
        const originalZi = hierarchy.indexOf(zone);
        const zoneKey = "z-" + originalZi;
        if (!keySet.has(zoneKey)) continue;
```

后续所有 `"z-" + zi` 引用改为 `"z-" + originalZi`（对象/单元/事件 key 前缀）。对象创建改为：

```ts
          const createdObj = await createObject(enterpriseId, {
            zone_id: createdZone.id,
            name: objName,
            category: obj.category || undefined,
            is_risk_point: false,
          });
```

`onSuccess` 改为：

```ts
    onSuccess: (count: number) => {
      const skipText = skippedZones.length > 0 ? `，跳过 ${skippedZones.length} 个重名分区` : "";
      antMessage.success(`成功导入 ${count} 条数据${skipText}`);
      onRefresh();
      onClose();
    },
```

`skippedZones` 需提升到 `importMut` 作用域：在组件顶层加 `const [lastSkipCount, setLastSkipCount] = useState(0);`，`mutationFn` 内 `setLastSkipCount(skippedZones.length)`，`onSuccess` 读取 `lastSkipCount`。由于 `onSuccess` 在 mutation 后执行且 state 已更新，直接读取 state 即可。

- [ ] **步骤 3：运行 tsc 验证**

运行：`npx tsc -b`
预期：exit 0

- [ ] **步骤 4：运行相关单测**

运行：`npx vitest run src/utils/smartGuideImport.test.ts`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/enterprise/RiskSmartGuideModal.tsx
git commit -m "fix(risk-ai): dedup smart guide zones on import and drop risk point flag"
```

---

### 任务 5：RiskManagementTab 表单坐标补传

**文件：**
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx:211-217`

- [ ] **步骤 1：修改 object 分支 payload**

```ts
        case "object":
          if (form.id) {
            await updateObject(enterpriseId, form.id, { name: values.name || "", category: values.category || "", description: values.description || "", location: values.location || null, location_x: values.location_x ?? null, location_y: values.location_y ?? null, is_risk_point: values.is_risk_point || false });
          } else {
            await createObject(enterpriseId, { zone_id: form.parentId, name: values.name || "", category: values.category || "", description: values.description || "", location: values.location || null, location_x: values.location_x ?? null, location_y: values.location_y ?? null, is_risk_point: values.is_risk_point || false });
          }
          break;
```

`ZoneFormValues` 接口补充 `location?: string; location_x?: number | null; location_y?: number | null;`。

- [ ] **步骤 2：运行 tsc 验证**

运行：`npx tsc -b`
预期：exit 0

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/pages/Enterprise/RiskManagementTab.tsx
git commit -m "fix(risk-management): pass form coordinates when saving risk object"
```

---

### 任务 6：智能引导导入 E2E

**文件：**
- 创建：`frontend/e2e/smart-guide-import.spec.ts`

- [ ] **步骤 1：编写 E2E**

```ts
import { test, expect, type Page, type Route } from "@playwright/test";

const ENTERPRISE_ID = "e2e-smart-guide-enterprise";
const EXISTING_ZONE = { id: "existing-zone-1", enterprise_id: ENTERPRISE_ID, floor_id: "f1", floor_name: "一层", name: "储罐区", description: null, sort_order: 0, floor_plan_polygon: null, max_risk_level: null, effective_color: null, object_count: 0, created_at: "2026-08-05T00:00:00+08:00", updated_at: "2026-08-05T00:00:00+08:00", objects: [] };
const AI_HIERARCHY = {
  zones: [
    { name: "储罐区", description: null, objects: [{ name: "1号储罐", category: "罐区", is_risk_point: true, units: [], events: [{ accident_type: "火灾爆炸", description: null, risk_level: "较大", risk_score: "R=16", method_type: "LS", method_params: { l: 4, s: 4 }, measures: [{ measure_category: "engineering", measure_type: null, description: "设置液位联锁", check_items: [] }] }] }] },
    { name: "原料库", description: null, objects: [{ name: "货架", category: "仓库", is_risk_point: false, units: [], events: [] }] },
  ],
  summary: {},
};

test("智能引导导入跳过重名分区且对象不标风险点", async ({ page }) => {
  const createdPayloads: unknown[] = [];
  await page.route("**/api/**", async (route: Route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();
    const json = (status: number, body: unknown) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/api/v1/auth/login" && method === "POST") return route.fulfill(json(200, { code: 0, message: "ok", data: { access_token: "t", refresh_token: "r", token_type: "bearer", expires_in: 7200 } }));
    if (path === "/api/v1/users/me" && method === "GET") return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "u", email: "qa_e2e_test@test.com", name: "测试", role: "admin" } }));
    if (path === "/api/v1/roles/my-menus" && method === "GET") return route.fulfill(json(200, { code: 0, message: "ok", data: [] }));
    if (path === "/api/v1/enterprises" && method === "GET" && url.searchParams.has("page")) return route.fulfill(json(200, { code: 0, message: "ok", data: { items: [{ id: ENTERPRISE_ID, name: "去重测试企业" }], total: 1, page: 1, page_size: 100 } }));
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/hierarchy` && method === "GET") return route.fulfill(json(200, { code: 0, message: "ok", data: [EXISTING_ZONE] }));
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/floors` && method === "GET") return route.fulfill(json(200, { code: 0, message: "ok", data: [] }));
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/zones` && method === "GET") return route.fulfill(json(200, { code: 0, message: "ok", data: [EXISTING_ZONE] }));
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/ai/smart-guide` && method === "POST") return route.fulfill(json(200, { code: 0, message: "ok", data: AI_HIERARCHY }));
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/zones` && method === "POST") {
      createdPayloads.push(req.postDataJSON());
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "new-zone-1", name: req.postDataJSON().name, floor_id: "f1", enterprise_id: ENTERPRISE_ID } }));
    }
    if (path === `/api/v1/enterprises/${ENTERPRISE_ID}/risk-management/objects` && method === "POST") {
      createdPayloads.push(req.postDataJSON());
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "new-obj-1", name: req.postDataJSON().name, is_risk_point: false, zone_id: req.postDataJSON().zone_id } }));
    }
    if (path.includes("/events/") && path.endsWith("/measures") && method === "POST") return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "m1", description: req.postDataJSON().description } }));
    return route.fulfill(json(404, { code: 404, message: "not found" }));
  });

  await page.goto("/login");
  await page.getByPlaceholder("邮箱").fill("qa_e2e_test@test.com");
  await page.getByPlaceholder("密码").fill("test123456");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/(dashboard|enterprises)/);
  await page.goto(`/enterprises/${ENTERPRISE_ID}/risk-management`);
  await page.getByRole("button", { name: /智能导引/ }).click();
  await page.getByPlaceholder(/储罐区/).fill("厂区有原料库和储罐");
  await page.getByRole("button", { name: /AI 分析/ }).click();
  await expect(page.getByText("AI 生成数据请核实后确认导入")).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: /确认并导入全部/ }).click();
  await expect(page.getByText(/成功导入/)).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/跳过 1 个重名分区/)).toBeVisible();
  const objectPayload = createdPayloads.find(p => (p as { name?: string }).name === "1号储罐") as { is_risk_point?: boolean } | undefined;
  expect(objectPayload?.is_risk_point).toBe(false);
});
```

说明：`createEvent` 需要 mock `POST /units/{id}/events` 或 `/objects/{id}/events`；上述 AI 层级事件挂在对象直下，需补充：

```ts
    if (path.includes("/objects/") && path.endsWith("/events") && method === "POST") return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "ev1", accident_type: req.postDataJSON().accident_type } }));
```

- [ ] **步骤 2：运行 E2E**

运行：`npx playwright test e2e/smart-guide-import.spec.ts --project=chromium`
预期：PASS（若 `getByPlaceholder(/储罐区/)` 不匹配，改用 `page.locator("textarea").first()`）

- [ ] **步骤 3：Commit**

```bash
git add frontend/e2e/smart-guide-import.spec.ts
git commit -m "test(risk-ai): e2e smart guide import dedup and non-risk-point objects"
```

---

### 任务 7：整体验证

- [ ] **步骤 1：后端全量测试**

运行：`backend/.venv/Scripts/python.exe -m pytest -q backend/tests --ignore backend/tests/test_autofill_research.py --ignore backend/tests/_docker_test.py`
预期：全部 PASS（新增测试 + 既有回归）

- [ ] **步骤 2：前端类型与单测**

运行：`npx tsc -b` 与 `npx vitest run`
预期：exit 0；vitest 全部 PASS

- [ ] **步骤 3：E2E 回归**

运行：`npx playwright test e2e/smart-guide-import.spec.ts e2e/risk-mapping-workbench.spec.ts -g "智能引导|总览" --project=chromium`
预期：全部 PASS

- [ ] **步骤 4：Commit 收尾**

```bash
git status --short
```

预期：仅 TASKS.md（未跟踪/未提交保持原样）与 backup SQL（未跟踪），无功能文件遗漏。

---

## 自检记录

- **规格覆盖度**：D1 → 任务 1；D2 → 任务 2；D3 → 任务 3+4；D4 → 任务 5；测试计划 → 任务 1/2/3/6；受影响文件 → 文件结构清单一致。
- **占位符扫描**：无「待定/TODO/类似任务 N」；每个任务含完整代码与命令。
- **类型一致性**：`existing_names`（dict，`{"zones": list[str], "objects": list[str]}`）贯穿路由 → `smart_guide`；`buildImportPlan(hierarchy, nameOverrides, existingZoneNames)` 在任务 3 定义、任务 4 调用；`z-{index}` key 约定一致。
