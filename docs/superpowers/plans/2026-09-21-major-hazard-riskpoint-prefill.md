# 重大危险源单元：从风险点带出填写项 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在重大危险源单元详情页选中风险点的那一刻，把风险点上已有的位置、责任部门、责任人、联系电话填进单元表单的空白项；并先修掉"保存基本信息会清空风险点关联与平面图落点"的 P0 缺陷。

**架构：** 不新增表、不新增端点。后端只做两件事——把 `update_unit` 改成 `exclude_unset` 语义、给 `GET /major-hazard/linkable/risk-objects` 的返回补 4 个字段；前端把"哪些字段该填"写成纯函数，由 `RiskObjectPicker` 的成功回调触发，填完在字段 label 上挂「来自风险点」标记，用户改动后标记消失。带出是一次性的：只填空项、只改表单显示值，落库仍由用户点保存。

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x / pytest；React 18 / antd 5 / TypeScript / vitest；Playwright（浏览器实测）。

**规格来源：** `docs/superpowers/specs/2026-09-21-major-hazard-riskpoint-prefill-design.md`

**任务数说明：** 规格 §7 估 4 个任务，本计划拆成 5 个——把浏览器探针独立成一个任务，因为它自带一套夹具数据与构建搬运步骤，混在页面接线任务里会让那一步无法单独验证。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/app/routers/major_hazard.py`（修改） | P0 修复：`update_unit` 改 `exclude_unset`；新增同企业校验调用 |
| `backend/app/services/major_hazard_linkage.py`（修改） | 新增 `ensure_risk_object_in_enterprise`（被 `link_risk_object` 与路由复用）；`list_linkable_risk_objects` 补 4 字段 |
| `backend/tests/test_major_hazard_api.py`（修改） | P0 回归（PUT 不清空）+ 跨企业 422 |
| `backend/tests/test_major_hazard_linkage.py`（修改） | 可关联列表返回 4 字段 |
| `frontend/src/types/majorHazard.ts`（修改） | `LinkableRiskObject` 补 4 个可选字段 |
| `frontend/src/components/enterprise/majorHazard/riskObjectPrefill.ts`（新建） | 纯函数：哪些字段该填、标记何时显示；字段中文名常量 |
| `frontend/src/components/enterprise/majorHazard/riskObjectPrefill.test.ts`（新建） | 上述纯函数的单测 |
| `frontend/src/components/enterprise/majorHazard/RiskObjectPicker.tsx`（修改） | 加 `onLinked` 回调 |
| `frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx`（修改） | 接回调、填表单、渲染来源标记 |
| `output/playwright/e2e-20260921/scripts/_major_hazard_prefill_probe.py`（新建） | 浏览器实测：带出 → 改动 → 保存 → 重载仍存在 |

**既有约定（动手前必读）**

- pytest **必须从仓库根目录**跑：`backend\.venv\Scripts\python.exe -m pytest backend/tests -q`
- 前端门禁**在容器里**跑：宿主机 `frontend/node_modules/.bin` 是 0 字节占位，直接执行会失败
- 后端容器**无 --reload**：改完 `backend/app` 必须 `docker restart emergency-plan-backend`
- 前端测试环境**没有 @testing-library**：纯函数单测是首选；组件测试用 `renderToStaticMarkup`
- 组件文件**只能导出组件**（`react-refresh/only-export-components`），常量与纯函数必须单独成文件
- `TASKS.md` 永不 commit；工作区有他人未提交改动（`docker-compose.yml`、`.graphifyignore`、`ChapterTree.tsx`、`output/_*.txt`），不要动

---

## 任务 1：修复保存基本信息误清空关联与落点（P0）

**文件：**

- 修改：`backend/app/routers/major_hazard.py:120-128`
- 测试：`backend/tests/test_major_hazard_api.py`（追加）

- [ ] **步骤 1：编写失败的测试**

追加到 `backend/tests/test_major_hazard_api.py` 末尾（该文件顶部已有 `_Scalars` / `_Result` / `_client` 辅助）：

```python
# --- 保存基本信息不得清空关联与落点（规格 §0）---------------------------------

def _unit_for_update():
    """字段全部显式赋值：UnitOut 校验严格，MagicMock 的自动属性过不了 pydantic。"""
    unit = MagicMock()
    unit.id = "u1"
    unit.enterprise_id = "e1"
    unit.name = "罐区A"
    unit.unit_type = "storage"
    unit.address = None
    unit.department = None
    unit.responsible_person = None
    unit.responsible_phone = None
    unit.risk_object_id = "o1"
    unit.floor_id = "f1"
    unit.polygon = {"version": 1, "points": [{"x": 0, "y": 0}]}
    unit.is_active = True
    unit.created_at = None
    return unit


def _update_handler(unit):
    async def handler(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit])
        if "enterprises" in text:
            ent = MagicMock()
            ent.id = "e1"
            ent.user_id = "user1"
            return _Result([ent])
        return _Result([])

    return handler


def test_update_unit_keeps_untouched_fields():
    """前端只提交 6 个文本框，未传的字段一律不许动。"""
    unit = _unit_for_update()
    client = _client(_update_handler(unit))
    resp = client.put(
        "/api/v1/major-hazard/units/u1",
        json={"name": "罐区A2", "unit_type": "storage"},
    )
    assert resp.status_code == 200
    assert unit.name == "罐区A2"
    assert unit.risk_object_id == "o1"
    assert unit.floor_id == "f1"
    assert unit.polygon == {"version": 1, "points": [{"x": 0, "y": 0}]}


def test_update_unit_still_allows_explicit_clearing():
    """显式传 null 仍要能清空——不然用户没法解除关联。"""
    unit = _unit_for_update()
    client = _client(_update_handler(unit))
    resp = client.put(
        "/api/v1/major-hazard/units/u1",
        json={"name": "罐区A", "unit_type": "storage", "risk_object_id": None},
    )
    assert resp.status_code == 200
    assert unit.risk_object_id is None
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_major_hazard_api.py -q`

预期：`test_update_unit_keeps_untouched_fields` FAIL（`assert None == 'o1'`），`test_update_unit_still_allows_explicit_clearing` PASS。

- [ ] **步骤 3：编写最少实现代码**

把 `backend/app/routers/major_hazard.py:126` 一行改为：

```python
    unit = await ensure_major_hazard_unit_owned(db, user, unit_id)
    # exclude_unset：前端只提交表单里的 6 个字段，未传的（风险点关联、楼层、落点）
    # 一律不许动；显式传 null 仍可清空。与 enterprises.py 的编辑接口同一约定。
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, key, value)
    await db.commit()
```

- [ ] **步骤 4：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_major_hazard_api.py -q`

预期：全绿。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/major_hazard.py backend/tests/test_major_hazard_api.py
git commit -m "fix(major-hazard): 保存单元基本信息不再清空风险点关联与平面图落点"
```

---

## 任务 2：可关联风险点返回带出字段 + 单元写入的同企业校验

**文件：**

- 修改：`backend/app/services/major_hazard_linkage.py`（`list_linkable_risk_objects`、`link_risk_object`）
- 修改：`backend/app/routers/major_hazard.py`（`create_unit`、`update_unit`）
- 测试：`backend/tests/test_major_hazard_linkage.py`、`backend/tests/test_major_hazard_api.py`

- [ ] **步骤 1：编写失败的测试（服务层）**

追加到 `backend/tests/test_major_hazard_linkage.py` 的"任务 1"区块末尾：

```python
@pytest.mark.asyncio
async def test_list_linkable_objects_returns_prefill_fields():
    """带出用得到 4 个字段；缺了它们前端只能填空气。"""
    o = _obj()
    o.location = "厂区北侧罐区东侧"
    o.responsible_unit = "生产运行部"
    o.responsible_person = "张峰"
    o.contact_phone = "13800000000"
    db = _db(objects=[o])
    out = await list_linkable_risk_objects(db, enterprise_id="e1")
    assert out[0]["location"] == "厂区北侧罐区东侧"
    assert out[0]["responsible_unit"] == "生产运行部"
    assert out[0]["responsible_person"] == "张峰"
    assert out[0]["contact_phone"] == "13800000000"


@pytest.mark.asyncio
async def test_ensure_risk_object_in_enterprise_rejects_cross_enterprise():
    from app.services.major_hazard_linkage import ensure_risk_object_in_enterprise

    db = _db(objects=[_obj(oid="o2", ent="e2")])
    with pytest.raises(LinkageError) as ei:
        await ensure_risk_object_in_enterprise(db, enterprise_id="e1", risk_object_id="o2")
    assert "企业" in str(ei.value)


@pytest.mark.asyncio
async def test_ensure_risk_object_in_enterprise_rejects_missing_object():
    from app.services.major_hazard_linkage import ensure_risk_object_in_enterprise

    db = _db(objects=[])
    with pytest.raises(LinkageError):
        await ensure_risk_object_in_enterprise(db, enterprise_id="e1", risk_object_id="nope")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_major_hazard_linkage.py -q`

预期：`test_list_linkable_objects_returns_prefill_fields` FAIL（KeyError: `location`）；两个 `ensure_risk_object_in_enterprise` 用例 FAIL（`ImportError`）。

- [ ] **步骤 3：编写实现（服务层）**

在 `backend/app/services/major_hazard_linkage.py` 中，把 `link_risk_object` 里的内联校验抽成独立函数，并让它复用：

```python
async def ensure_risk_object_in_enterprise(
    db: AsyncSession,
    *,
    enterprise_id: str,
    risk_object_id: str,
) -> None:
    """校验风险点存在且属于该企业，非法时抛 LinkageError。

    抽成独立函数的原因：不只 `link_risk_object` 需要它，单元的新建/编辑接口
    也必须过同一道门——否则构造请求就能把别家企业的风险点 id 写进来。
    """
    obj_res = await db.execute(select(RiskObject).where(RiskObject.id == risk_object_id))
    obj = obj_res.scalar_one_or_none()
    if obj is None:
        raise LinkageError("风险点不存在")
    if getattr(obj, "enterprise_id", None) != enterprise_id:
        raise LinkageError("风险点与单元不属于同一企业，禁止关联")
```

`link_risk_object` 的校验段替换为：

```python
    if risk_object_id is None:
        unit.risk_object_id = None
        await db.commit()
        return {"unit_id": unit_id, "risk_object_id": None}

    await ensure_risk_object_in_enterprise(
        db, enterprise_id=unit.enterprise_id, risk_object_id=risk_object_id
    )
    unit.risk_object_id = risk_object_id
    await db.commit()
    return {"unit_id": unit_id, "risk_object_id": risk_object_id}
```

`list_linkable_risk_objects` 的返回项补 4 个字段：

```python
    return [
        {
            "id": o.id,
            "name": o.name,
            "zone_id": getattr(o, "zone_id", None),
            "floor_id": getattr(o, "floor_id", None),
            # 供单元表单带出默认值；不含坐标与分区多边形——见规格 §2.4
            "location": getattr(o, "location", None),
            "responsible_unit": getattr(o, "responsible_unit", None),
            "responsible_person": getattr(o, "responsible_person", None),
            "contact_phone": getattr(o, "contact_phone", None),
        }
        for o in res.scalars().all()
    ]
```

- [ ] **步骤 4：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_major_hazard_linkage.py -q`

预期：全绿（含既有的跨企业用例——它们现在走抽出来的函数，断言不变）。

- [ ] **步骤 5：编写失败的测试（接口层同企业校验）**

追加到 `backend/tests/test_major_hazard_api.py`。夹具口径：企业 `e1` 归当前用户，风险点 `o2` 属于
企业 `e9`——任何把 `o2` 写进 `e1` 单元的动作都必须被拒。一个 handler 同时服务两条用例
（按语句文本分派，与查询顺序无关）：

```python
def _cross_enterprise_handler(unit=None):
    async def handler(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit] if unit else [])
        if "enterprises" in text:
            ent = MagicMock()
            ent.id = "e1"
            ent.user_id = "user1"
            return _Result([ent])
        if "risk_objects" in text:
            obj = MagicMock()
            obj.id = "o2"
            obj.enterprise_id = "e9"
            return _Result([obj])
        return _Result([])

    return handler


def test_create_unit_rejects_cross_enterprise_risk_object():
    client = _client(_cross_enterprise_handler())
    resp = client.post(
        "/api/v1/major-hazard/units",
        params={"enterprise_id": "e1"},
        json={"name": "罐区A", "unit_type": "storage", "risk_object_id": "o2"},
    )
    assert resp.status_code == 422
    assert "企业" in resp.json()["detail"]


def test_update_unit_rejects_cross_enterprise_risk_object():
    # 必须给 unit：update_unit 先走 ensure_major_hazard_unit_owned，否则会先 404
    client = _client(_cross_enterprise_handler(unit=_unit_for_update()))
    resp = client.put(
        "/api/v1/major-hazard/units/u1",
        json={"name": "罐区A", "unit_type": "storage", "risk_object_id": "o2"},
    )
    assert resp.status_code == 422
    assert "企业" in resp.json()["detail"]
```

- [ ] **步骤 6：运行测试验证失败**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_major_hazard_api.py -q -k cross_enterprise`

预期：两条 FAIL（当前返回 200，关联被写入）。

- [ ] **步骤 7：编写实现（路由层）**

在 `backend/app/routers/major_hazard.py` 的 import 段补上 `ensure_risk_object_in_enterprise`，并加一个模块级辅助函数（放在 `_ok` 定义之后）：

```python
async def _guard_risk_object(db, enterprise_id: str, risk_object_id: str | None) -> None:
    """单元写入前的同企业校验。跨企业引用是数据越界，不是边界情况。"""
    if risk_object_id is None:
        return
    try:
        await ensure_risk_object_in_enterprise(
            db, enterprise_id=enterprise_id, risk_object_id=risk_object_id
        )
    except LinkageError as exc:
        raise HTTPException(422, str(exc)) from exc
```

`create_unit` 在 `db.add(unit)` 之前插入：

```python
    await ensure_enterprise_owned(db, user, enterprise_id)
    await _guard_risk_object(db, enterprise_id, payload.risk_object_id)
    unit = MajorHazardUnit(enterprise_id=enterprise_id, **payload.model_dump())
```

`update_unit`：校验放在取到 `unit` 之后、写入之前——重命名前先备份原值以便报错回滚，不必真回滚，因为校验失败时还没改内存对象：

```python
    unit = await ensure_major_hazard_unit_owned(db, user, unit_id)
    await _guard_risk_object(db, unit.enterprise_id, payload.risk_object_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(unit, key, value)
```

- [ ] **步骤 8：运行测试验证通过**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_major_hazard_api.py backend/tests/test_major_hazard_linkage.py -q`

预期：全绿。

- [ ] **步骤 9：跑一次全量后端门禁**

运行：`backend\.venv\Scripts\python.exe -m pytest backend/tests -q`

预期：`2176+ passed, 1 skipped`（只增不减）。

- [ ] **步骤 10：Commit**

```bash
git add backend/app/services/major_hazard_linkage.py backend/app/routers/major_hazard.py backend/tests/test_major_hazard_linkage.py backend/tests/test_major_hazard_api.py
git commit -m "feat(major-hazard): 可关联风险点带出 4 项字段；单元写入补同企业校验"
```

---

## 任务 3：前端带出纯函数与单测

**文件：**

- 创建：`frontend/src/components/enterprise/majorHazard/riskObjectPrefill.ts`
- 创建：`frontend/src/components/enterprise/majorHazard/riskObjectPrefill.test.ts`
- 修改：`frontend/src/types/majorHazard.ts:42-47`

- [ ] **步骤 1：补类型**

`frontend/src/types/majorHazard.ts` 中 `LinkableRiskObject` 改为：

```ts
export interface LinkableRiskObject {
  id: string;
  name: string;
  zone_id?: string | null;
  floor_id?: string | null;
  /** 以下 4 项供单元表单带出默认值（规格 §2.1）。 */
  location?: string | null;
  responsible_unit?: string | null;
  responsible_person?: string | null;
  contact_phone?: string | null;
}
```

- [ ] **步骤 2：编写失败的测试**

创建 `frontend/src/components/enterprise/majorHazard/riskObjectPrefill.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import type { LinkableRiskObject } from "@/types/majorHazard";
import { buildUnitPrefill, isPrefillMarkVisible } from "./riskObjectPrefill";

const SOURCE: LinkableRiskObject = {
  id: "o1",
  name: "罐区A风险点",
  location: "厂区北侧罐区东侧",
  responsible_unit: "生产运行部",
  responsible_person: "张峰",
  contact_phone: "13800000000",
};

describe("buildUnitPrefill（风险点 → 单元表单）", () => {
  it("空白项全部带出", () => {
    const { patch, fields } = buildUnitPrefill(SOURCE, {});
    expect(patch).toEqual({
      address: "厂区北侧罐区东侧",
      department: "生产运行部",
      responsible_person: "张峰",
      responsible_phone: "13800000000",
    });
    expect(fields).toEqual([
      "address",
      "department",
      "responsible_person",
      "responsible_phone",
    ]);
  });

  it("已填字段不被覆盖", () => {
    const { patch, fields } = buildUnitPrefill(SOURCE, { department: "人工填的部门" });
    expect(patch.department).toBeUndefined();
    expect(patch.address).toBe("厂区北侧罐区东侧");
    expect(fields).not.toContain("department");
  });

  it("纯空格视为空白", () => {
    const { patch } = buildUnitPrefill(SOURCE, { address: "   " });
    expect(patch.address).toBe("厂区北侧罐区东侧");
  });

  it("来源字段为空则不产出该项", () => {
    const { patch, fields } = buildUnitPrefill(
      { id: "o2", name: "空风险点", location: "" },
      {},
    );
    expect(patch).toEqual({});
    expect(fields).toEqual([]);
  });

  it("不产出名称、楼层与多边形", () => {
    const { patch } = buildUnitPrefill(SOURCE, {});
    expect("name" in patch).toBe(false);
    expect("floor_id" in patch).toBe(false);
    expect("polygon" in patch).toBe(false);
  });
});

describe("isPrefillMarkVisible（来源标记）", () => {
  it("值仍是带出时的原值 → 显示", () => {
    expect(isPrefillMarkVisible({ address: "厂区北侧" }, "address", "厂区北侧")).toBe(true);
  });

  it("用户改过 → 不显示", () => {
    expect(isPrefillMarkVisible({ address: "厂区北侧" }, "address", "厂区北侧（改）")).toBe(false);
  });

  it("该字段没被带出过 → 不显示", () => {
    expect(isPrefillMarkVisible({ address: "厂区北侧" }, "department", "生产运行部")).toBe(false);
  });
});
```

- [ ] **步骤 3：运行测试验证失败**

运行：`docker exec emergency-plan-frontend npx vitest run src/components/enterprise/majorHazard/riskObjectPrefill.test.ts`

预期：FAIL，`Failed to resolve import "./riskObjectPrefill"`。

- [ ] **步骤 4：编写实现**

创建 `frontend/src/components/enterprise/majorHazard/riskObjectPrefill.ts`：

```ts
import type { LinkableRiskObject, MajorHazardUnitPayload } from "@/types/majorHazard";

/**
 * 单元表单可被风险点带出的字段。
 *
 * 单独成文件：组件文件只能导出组件（react-refresh/only-export-components），
 * 常量与纯函数混在组件里会触发 lint。参照 workTicket/fieldSources.ts。
 */
export const PREFILL_FIELD_LABELS = {
  address: "所在位置",
  department: "责任部门",
  responsible_person: "责任人",
  responsible_phone: "联系电话",
} as const;

export type PrefillField = keyof typeof PREFILL_FIELD_LABELS;

/** 空白定义：null / undefined / 纯空格都算空白。 */
function isBlank(v: unknown): boolean {
  return v == null || String(v).trim() === "";
}

export interface UnitPrefillResult {
  /** 只含可带出的 4 个字段——刻意不用 Partial<MajorHazardUnitPayload>，
   *  好让调用方不必强转就能塞进 form.setFieldsValue 与来源标记状态。 */
  patch: Partial<Record<PrefillField, string>>;
  fields: PrefillField[];
}

/**
 * 从风险点带出单元表单的空白项。
 *
 * 只填空白项、不覆盖人工值：目标是省一遍打字，不是纠正人工值。
 * 名称、楼层、多边形不参与带出——理由见规格 §2.4（楼层与多边形在接口上必须成对，
 * 且风险点存的是一个坐标点，不是单元边界）。
 */
export function buildUnitPrefill(
  source: LinkableRiskObject,
  current: Partial<MajorHazardUnitPayload>,
): UnitPrefillResult {
  const mapping: Array<[PrefillField, string | null | undefined]> = [
    ["address", source.location],
    ["department", source.responsible_unit],
    ["responsible_person", source.responsible_person],
    ["responsible_phone", source.contact_phone],
  ];
  const patch: Partial<Record<PrefillField, string>> = {};
  const fields: PrefillField[] = [];
  for (const [field, value] of mapping) {
    if (isBlank(value)) continue;
    if (!isBlank(current[field])) continue;
    patch[field] = String(value).trim();
    fields.push(field);
  }
  return { patch, fields };
}

/**
 * 来源标记是否还该显示。
 *
 * 判定标准是"值没被改过"，而不是"填过一次"——用户只要动过这个字段，
 * 它就不再是"来自风险点"的值了，继续标着反而误导。
 */
export function isPrefillMarkVisible(
  prefilled: Partial<Record<string, string>>,
  field: string,
  currentValue: unknown,
): boolean {
  const v = prefilled[field];
  return v != null && currentValue === v;
}
```

- [ ] **步骤 5：运行测试验证通过**

运行：`docker exec emergency-plan-frontend npx vitest run src/components/enterprise/majorHazard/riskObjectPrefill.test.ts`

预期：8 passed。

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/types/majorHazard.ts frontend/src/components/enterprise/majorHazard/riskObjectPrefill.ts frontend/src/components/enterprise/majorHazard/riskObjectPrefill.test.ts
git commit -m "feat(major-hazard): 风险点→单元带出的纯函数与单测"
```

---

## 任务 4：选择器回调与页面接线（含来源标记）

**文件：**

- 修改：`frontend/src/components/enterprise/majorHazard/RiskObjectPicker.tsx`
- 修改：`frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx:1-100`（import 与状态）、`:128-172`（表单与卡片）

- [ ] **步骤 1：给选择器加回调**

`frontend/src/components/enterprise/majorHazard/RiskObjectPicker.tsx`：

```tsx
import type { LinkableRiskObject } from "@/types/majorHazard";

interface Props {
  enterpriseId: string;
  unitId: string;
  riskObjectId?: string | null;
  /** 关联成功后的回调：带上被选中的风险点（解除关联时传 null），供调用方带出字段。 */
  onLinked?: (object: LinkableRiskObject | null) => void;
}

export default function RiskObjectPicker({ enterpriseId, unitId, riskObjectId, onLinked }: Props) {
```

`handleChange` 改为：

```tsx
  const handleChange = async (value?: string) => {
    setSaving(true);
    try {
      await linkRiskObject(unitId, value ?? null);
      message.success(value ? "已关联风险点" : "已解除关联");
      queryClient.invalidateQueries({ queryKey: ["major-hazard-units", enterpriseId] });
      // 选择器只管关联，不碰表单——带出的字段由调用方决定怎么用。
      onLinked?.(value ? (objects.find((o) => o.id === value) ?? null) : null);
    } finally {
      setSaving(false);
    }
  };
```

并把卡片下方那段说明文字改成（避免用户误以为关联即落库）：

```tsx
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        风险点来自「风险分级管控」中标记为风险点的对象；选中后会把对方的
        位置、责任部门、责任人、联系电话填入下方空白的表单项，改完记得点保存。
      </Typography.Text>
```

- [ ] **步骤 2：页面接线**

`frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx`：

import 段补：

```tsx
import { Tag } from "antd";
import {
  buildUnitPrefill,
  isPrefillMarkVisible,
  PREFILL_FIELD_LABELS,
} from "@/components/enterprise/majorHazard/riskObjectPrefill";
import type { LinkableRiskObject } from "@/types/majorHazard";
```

（`antd` 的既有 import 行已含 `App as AntApp, Button, Card, Form, Input, Select, Space, Spin, Tabs`，把 `Tag` 合并进去即可。）

**位置要求（重要）：** 下面三段都要放在 `const invalidateUnits = ...` 之后、第一个提前
`return`（`if (isLoading) return <Spin />;`）之前。放在提前 return 之后会触发
"Rendered fewer hooks than expected"——加载态切换时 hooks 数量会变。

第一段，紧跟 `const [savingChem, setSavingChem] = useState(false);`：

```tsx
  /** 带出时记下"字段 → 当时的值"：值没被改过才继续显示来源标记。 */
  const [prefilled, setPrefilled] = useState<Partial<Record<string, string>>>({});

  const handleRiskObjectLinked = (object: LinkableRiskObject | null) => {
    if (!object) {
      setPrefilled({});
      return;
    }
    const { patch, fields } = buildUnitPrefill(object, form.getFieldsValue());
    if (fields.length === 0) {
      setPrefilled({});
      return;
    }
    form.setFieldsValue(patch);
    setPrefilled(patch);
    message.info(`已从风险点带出 ${fields.length} 项，请检查后保存`);
  };
```

第二段，接在第一段之后：

```tsx
  const watched = {
    address: Form.useWatch("address", form),
    department: Form.useWatch("department", form),
    responsible_person: Form.useWatch("responsible_person", form),
    responsible_phone: Form.useWatch("responsible_phone", form),
  };

  const fieldLabel = (field: keyof typeof watched, text: string) =>
    isPrefillMarkVisible(prefilled, field, watched[field]) ? (
      <span>
        {text}
        <Tag color="blue" style={{ marginInlineStart: 6 }}>
          来自风险点
        </Tag>
      </span>
    ) : (
      text
    );
```

表单 4 项的 label 改为：

```tsx
                    <Form.Item
                      name="address"
                      label={fieldLabel("address", PREFILL_FIELD_LABELS.address)}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="department"
                      label={fieldLabel("department", PREFILL_FIELD_LABELS.department)}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="responsible_person"
                      label={fieldLabel("responsible_person", PREFILL_FIELD_LABELS.responsible_person)}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="responsible_phone"
                      label={fieldLabel("responsible_phone", PREFILL_FIELD_LABELS.responsible_phone)}
                    >
                      <Input />
                    </Form.Item>
```

`RiskObjectPicker` 处传入回调：

```tsx
                  <RiskObjectPicker
                    enterpriseId={id!}
                    unitId={effectiveUnitId}
                    riskObjectId={unit.risk_object_id}
                    onLinked={handleRiskObjectLinked}
                  />
```

- [ ] **步骤 3：跑前端门禁**

依次运行：

```bash
docker exec emergency-plan-frontend npx tsc -b
docker exec emergency-plan-frontend npx vitest run
docker exec emergency-plan-frontend npx eslint src
docker exec emergency-plan-frontend npm run build
```

预期：tsc 0 错误；vitest 全绿（含任务 3 的 8 例）；eslint 0；build OK。

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/enterprise/majorHazard/RiskObjectPicker.tsx frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx
git commit -m "feat(major-hazard): 选风险点即带出单元空白字段并标注来源"
```

---

## 任务 5：浏览器实测（P0 与带出的唯一有效证据）

**文件：**

- 创建：`output/playwright/e2e-20260921/scripts/_major_hazard_prefill_probe.py`
- 证据输出：`output/playwright/e2e-20260921/scripts/major-hazard-prefill.json`

为什么必须做：本轮修的是"保存导致数据消失"这类问题，单测与类型检查都看不见；
只有真浏览器 + 真后端 + 真保存动作能证明它不复发。

- [ ] **步骤 1：把新构建搬到 8082 服务的位置**

```bash
docker exec emergency-plan-frontend npm run build
docker cp emergency-plan-frontend:/app/dist /tmp/dist-new
docker cp /tmp/dist-new/. shuzihuayuan:/app/dist
docker restart shuzihuayuan
docker restart emergency-plan-backend
```

（8082 服务的是 `shuzihuayuan` 镜像内的 dist；宿主机 `frontend/dist` 是 1 字节占位。更新流程已在 TASKS.md 记录，必要时先 `docker exec shuzihuayuan cp -r /app/dist /app/dist.bak` 备份。）

- [ ] **步骤 2：编写探针**

创建 `output/playwright/e2e-20260921/scripts/_major_hazard_prefill_probe.py`：

```python
"""重大危险源单元「从风险点带出填写项」浏览器实测。

覆盖规格 2026-09-21-major-hazard-riskpoint-prefill-design.md 的验收清单：
  1. 选风险点后 4 项空白字段被填，已填的人工值不被覆盖
  2. 带出字段显示「来自风险点」标记，改过的字段标记消失
  3. 点保存后：关联仍在（P0 回归）、带出与手改的值都落库
  4. 全程 0 console error

用法（仓库根目录）：
    python output/playwright/e2e-20260921/scripts/_major_hazard_prefill_probe.py
证据输出：同目录 major-hazard-prefill.json
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

API = os.environ.get("E2E_API", "http://localhost:8000/api/v1")
BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
OUT = Path(__file__).resolve().parent
U, P = "qa_e2e_test@test.com", "test123456"

RISK = {
    "location": "厂区北侧罐区东侧",
    "responsible_unit": "生产运行部",
    "responsible_person": "张峰",
    "contact_phone": "13800000000",
}
FIELDS = ("address", "department", "responsible_person", "responsible_phone")


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def call_data(method, path, token, body=None):
    return call(method, path, token, body)["data"]


def click_button(page, text: str) -> None:
    """antd 会给两字按钮插空格，故用允许空白的正则。"""
    page.get_by_role("button", name=re.compile(r"\s*".join(text))).first.click()


def build_fixture(token: str) -> dict:
    """隔离夹具：企业 → 分区 → 带 4 项信息的风险点 → 空单元。"""
    stamp = int(time.time() * 1000)
    ent = call_data("POST", "/enterprises", token, {"name": f"E2E_Prefill_{stamp}"})["id"]
    zone = call_data(
        "POST", f"/risk-management/zones?enterprise_id={ent}", token, {"name": f"分区{stamp}"}
    )
    obj = call_data(
        "POST",
        f"/risk-management/objects?enterprise_id={ent}",
        token,
        {
            "name": "罐区A风险点",
            "zone_id": zone["id"],
            "location_x": 10.0,
            "location_y": 20.0,
            "is_risk_point": True,
            **RISK,
        },
    )
    unit = call_data(
        "POST",
        f"/major-hazard/units?enterprise_id={ent}",
        token,
        {"name": "罐区A", "unit_type": "storage"},
    )
    return {
        "enterprise": ent,
        "zone": zone["id"],
        "object": obj["id"],
        "unit": unit["id"],
    }


def main() -> int:
    checks: dict[str, bool] = {}
    detail: dict = {}
    errors: list[str] = []

    token = call_data("POST", "/auth/login", None, {"email": U, "password": P})["access_token"]
    fx = build_fixture(token)
    detail["fixture"] = fx

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: errors.append(f"console:{m.text[:120]}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))

        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        page.fill('input[placeholder="邮箱"]', U)
        page.fill('input[placeholder="密码"]', P)
        click_button(page, "登录")
        page.wait_for_timeout(4000)

        url = f"{BASE}/enterprises/{fx['enterprise']}/major-hazard/units/{fx['unit']}"
        page.goto(url, wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)

        before = {f: page.input_value(f"#{f}") for f in FIELDS}
        detail["before"] = before
        checks["fields_start_blank"] = all(v == "" for v in before.values())

        # 先人工填一项：验证「空白才填、已填不覆盖」
        page.fill("#department", "人工填的部门")
        page.wait_for_timeout(300)

        # 选择风险点（antd Select 由 rc-select 渲染，选项带 role="option"）
        page.click('input[placeholder="选择该单元对应的风险点"]')
        page.wait_for_timeout(800)
        page.get_by_role("option", name="罐区A风险点").click()
        page.wait_for_timeout(2000)

        after = {f: page.input_value(f"#{f}") for f in FIELDS}
        detail["after_pick"] = after
        checks["prefilled_blank_fields"] = (
            after["address"] == RISK["location"]
            and after["responsible_person"] == RISK["responsible_person"]
            and after["responsible_phone"] == RISK["contact_phone"]
        )
        checks["manual_value_not_overwritten"] = after["department"] == "人工填的部门"

        body = page.inner_text("body")
        detail["tag_count_after_pick"] = body.count("来自风险点")
        checks["source_tag_shown_for_three"] = body.count("来自风险点") == 3
        page.screenshot(path=str(OUT / "major-hazard-prefill-before-save.png"), full_page=True)

        # 改掉一个带出字段 → 该字段标记消失，其余仍标记
        page.fill("#address", f"{RISK['location']}（改过）")
        page.wait_for_timeout(800)
        detail["tag_count_after_edit"] = page.inner_text("body").count("来自风险点")
        checks["tag_cleared_after_edit"] = detail["tag_count_after_edit"] == 2

        click_button(page, "保存")
        page.wait_for_timeout(2500)

        # P0 回归：保存后关联必须还在（走接口判定，避免被页面文本干扰）
        units = call_data("GET", f"/major-hazard/units?enterprise_id={fx['enterprise']}", token)
        saved = next(u for u in units if u["id"] == fx["unit"])
        detail["saved_unit"] = saved
        checks["link_survived_save"] = saved["risk_object_id"] == fx["object"]
        checks["prefilled_value_persisted"] = saved["responsible_person"] == RISK["responsible_person"]
        checks["edited_value_persisted"] = saved["address"] == f"{RISK['location']}（改过）"
        checks["manual_value_persisted"] = saved["department"] == "人工填的部门"

        # 重载后界面仍应显示关联与该字段值
        page.reload(wait_until="load")
        page.wait_for_timeout(3000)
        after_reload = {f: page.input_value(f"#{f}") for f in FIELDS}
        detail["after_reload"] = after_reload
        checks["reload_shows_persisted"] = (
            after_reload["responsible_person"] == RISK["responsible_person"]
            and after_reload["address"] == f"{RISK['location']}（改过）"
        )
        checks["reload_has_no_tag"] = page.inner_text("body").count("来自风险点") <= 1

        checks["no_console_error"] = len(errors) == 0
        detail["errors"] = errors[:5]
        page.screenshot(path=str(OUT / "major-hazard-prefill-after-reload.png"), full_page=True)
        browser.close()

    (OUT / "major-hazard-prefill.json").write_text(
        json.dumps(
            {"checks": checks, "detail": detail, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if errors:
        print("errors:", errors[:3])
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

说明两处判定口径：

- 重载后 `checks["reload_has_no_tag"]` 用 `<= 1`：选择器下方那段说明文字里也含「来自风险点」，
  所以不能断言等于 0。若实测发现说明文字导致计数不准，把说明文字改成"来自该风险点"再收紧到 `== 0`。
- 夹具数据（企业/分区/风险点/单元）**故意不清理**：与其他 E2E 探针一致，留证据、便于人工复核。

- [ ] **步骤 3：运行探针**

运行：`python output/playwright/e2e-20260921/scripts/_major_hazard_prefill_probe.py`

预期：`all_passed` 为 true，12 项 checks 全 true，退出码 0。任何一项 false 都**不许**改断言迁就，回到对应任务查根因。

- [ ] **步骤 4：Commit**

```bash
git add output/playwright/e2e-20260921/scripts/_major_hazard_prefill_probe.py output/playwright/e2e-20260921/scripts/major-hazard-prefill.json output/playwright/e2e-20260921/scripts/major-hazard-prefill-before-save.png output/playwright/e2e-20260921/scripts/major-hazard-prefill-after-reload.png
git commit -m "test(probe): 单元带出字段与保存后仍存活的浏览器实测证据"
```

---

## 收尾检查（全部任务完成后执行）

- [ ] 后端：`backend\.venv\Scripts\python.exe -m pytest backend/tests -q` → `2176+ passed, 1 skipped`
- [ ] 前端：`tsc -b` / `vitest run` / `eslint src` / `npm run build` 四项全绿
- [ ] 浏览器探针 `all_passed: true`
- [ ] 核对规格 §8 验收清单六条，逐条在 TASKS.md 里写上证据路径
- [ ] 更新 `TASKS.md`「当前状态快照」（**TASKS.md 永不 commit**）
- [ ] 图谱同步：`codegraph sync .` 与 `graphify update .`（本轮改了 `backend/app` 与 `frontend/src`）
