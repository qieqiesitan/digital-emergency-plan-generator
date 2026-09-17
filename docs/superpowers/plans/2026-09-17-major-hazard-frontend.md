# 重大危险源前端（模块入口 + 单元台账 + 品种存量 + 计算分级 + 档案依据）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让计划 1 交付的后端在界面上可用——建单元、录品种与设计最大量、实时预览并固化 R 值分级、建档备案、挂法规依据。

**架构：** 前端沿用现有 `api.ts` + `services/*Service.ts` + `types/*.ts` + 页面组件的既有分层；模块入口走 `ModuleNav.tsx`（11→12）与 `enterpriseNavConfig.ts`；**实时预览不把 R 值公式复制到 TypeScript**，而是新增后端 `POST /units/{id}/preview`（只算不写快照），避免合规计算出现两个真源。

**技术栈：** React 18 / TypeScript / antd 5 / react-router 6 / TanStack Query / vitest / FastAPI（仅新增一个预览端点）。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §6、§13.1（视觉走查确认）

**依赖：** 计划 1（已完成并合入 master）。未开工前请先读 `README-安全生产管控平台-计划总览.md` 的执行纪律。

**视觉走查确认的两条交互（必须遵守）：**

1. 计算页 = **实时预览 + 手动固化**：改动输入即时显示 s/R（标注"预览，未保存"），点「固化本次结果」才写不可变快照
2. `q_design_max` = **从危化品台账 `max_storage` 带出初值 + 强制人工确认**，字段旁标注"设计最大量口径，通常 ≥ 台账最大储存量"

---

## 文件结构

**后端（仅一处新增）**

| 文件 | 改动 |
|---|---|
| `backend/app/routers/major_hazard.py` | 新增 `POST /units/{unit_id}/preview`：只算不写快照 |
| `backend/app/services/major_hazard_service.py` | 新增 `preview_unit_calculation()`，复用 `major_hazard_calc.compute` |
| `backend/tests/test_major_hazard_preview.py` | 预览不写快照的回归测试 |

**前端 — 类型与服务**

| 文件 | 职责 |
|---|---|
| `frontend/src/types/majorHazard.ts` | 与后端 schema 对应的类型（注意 `Decimal` 走线是 **string**） |
| `frontend/src/services/majorHazardService.ts` | 14+1 个端点的封装 |
| `frontend/src/services/majorHazardService.test.ts` | service 层测试 |

**前端 — 入口**

| 文件 | 改动 |
|---|---|
| `frontend/src/components/enterprise/cockpit/ModuleNav.tsx` | 模块从 11 个加到 12 个（在「危险化学品」后插入「重大危险源」） |
| `frontend/src/pages/Enterprise/enterpriseNavConfig.ts` | 新增 `majorHazardNavGroups(id)` |
| `frontend/src/routes/index.tsx` | 新增 4 条路由 |

**前端 — 页面与组件**

| 文件 | 职责 |
|---|---|
| `frontend/src/pages/Enterprise/MajorHazardListPage.tsx` | 单元台账（列表 + 结论列读最近快照） |
| `frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx` | 单元详情：基本信息 + 品种存量表（含设计最大量带出初值） |
| `frontend/src/pages/Enterprise/MajorHazardComputePage.tsx` | 计算与分级（实时预览 + 固化）+ 快照历史 |
| `frontend/src/pages/Enterprise/MajorHazardRecordPage.tsx` | 档案与备案 |
| `frontend/src/components/enterprise/majorHazard/UnitChemicalTable.tsx` | 品种存量可编辑表格（独立组件，便于测试） |
| `frontend/src/components/enterprise/majorHazard/EvidencePanel.tsx` | 法规依据侧栏（可被作业票复用） |
| `frontend/src/utils/majorHazardFormat.ts` | Decimal 字符串 → 展示数值、等级色板等纯函数 |
| `frontend/src/utils/majorHazardFormat.test.ts` | 纯函数测试 |

**既有约定（务必遵守）**

- service 层写法：`import api from "./api"`，返回 `ApiResponse<T>` 的 `data` 字段，见 `frontend/src/services/riskManagementService.ts`
- `api.ts` 的 `baseURL` 已含 `/api/v1`，因此业务路径写 `/major-hazard/...` 即可
- 全局错误 toast 默认开启；需要页面自己处理时传 `{ skipGlobalError: true }`
- 页面用 TanStack Query（`useQuery` / `useMutation`）取数与失效

---

## 任务 1：后端预览端点（只算不写快照）

**文件：**

- 修改：`backend/app/services/major_hazard_service.py`
- 修改：`backend/app/routers/major_hazard.py`
- 测试：`backend/tests/test_major_hazard_preview.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""预览端点：只计算、不写快照。"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.major_hazard_service import preview_unit_calculation


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


def _db(unit, chemicals, added):
    db = MagicMock()
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "major_hazard_units" in text:
            return _Result([unit] if unit else [])
        if "major_hazard_unit_chemicals" in text:
            return _Result(chemicals)
        return _Result([])

    db.execute = execute
    return db


def _unit():
    u = MagicMock()
    u.id = "u1"
    return u


def _chem(name, q, Q, beta):
    c = MagicMock()
    c.chemical_name = name
    c.q_design_max = Decimal(str(q))
    c.critical_quantity_t = Decimal(str(Q))
    c.beta = Decimal(str(beta))
    return c


@pytest.mark.asyncio
async def test_preview_returns_result_without_writing_snapshot():
    """预览必须算出结果，且一行都不写库——这是"手动固化"语义的前提。"""
    added = []
    db = _db(_unit(), [_chem("氯", 5, 5, 4), _chem("氨", 5, 10, 2)], added)

    out = await preview_unit_calculation(db, unit_id="u1", exposed_population=60)

    assert out["s_value"] == 1.5
    assert out["r_value"] == 7.5
    assert out["alpha"] == 1.5
    assert out["is_major_hazard"] is True
    assert out["level"] == "四级"
    assert out["formula_version"] == "GB18218-2018"
    assert len(out["chemicals"]) == 2
    assert added == [], "预览绝不能写快照"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_rejects_empty_unit():
    from app.services.major_hazard_service import MajorHazardRuleError

    added = []
    db = _db(_unit(), [], added)
    with pytest.raises(MajorHazardRuleError):
        await preview_unit_calculation(db, unit_id="u1", exposed_population=0)
    assert added == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_preview.py -q
```

预期：FAIL，`ImportError: cannot import name 'preview_unit_calculation'`

- [ ] **步骤 3：编写实现**

在 `backend/app/services/major_hazard_service.py` 的 `compute_unit_snapshot` **之前**插入：

```python
async def _load_unit_and_chemicals(db: AsyncSession, unit_id: str):
    """取单元与其品种清单；缺任一则抛 MajorHazardRuleError。"""
    unit_res = await db.execute(select(MajorHazardUnit).where(MajorHazardUnit.id == unit_id))
    if unit_res.scalar_one_or_none() is None:
        raise MajorHazardRuleError("重大危险源单元不存在")
    chem_res = await db.execute(
        select(MajorHazardUnitChemical).where(MajorHazardUnitChemical.unit_id == unit_id)
    )
    chemicals = list(chem_res.scalars().all())
    if not chemicals:
        raise MajorHazardRuleError("该单元尚未录入危险化学品，无法计算")
    return unit_res.scalar_one_or_none(), chemicals


def _run_engine(chemicals, exposed_population: int):
    """把 DB 行转成引擎输入并计算；输入不合法统一转成 MajorHazardRuleError。"""
    try:
        return compute(
            [
                ChemicalInput(
                    name=c.chemical_name,
                    q_design_max=float(c.q_design_max),
                    critical_quantity=float(c.critical_quantity_t),
                    beta=float(c.beta),
                )
                for c in chemicals
            ],
            exposed_population=exposed_population,
        )
    except CalcInputError as exc:
        raise MajorHazardRuleError(str(exc)) from exc


async def preview_unit_calculation(
    db: AsyncSession,
    *,
    unit_id: str,
    exposed_population: int,
) -> dict:
    """只计算并返回结果，**不写任何快照**。供前端"实时预览"使用。

    快照是不可变的审计凭证，必须由用户显式点「固化」才产生；
    预览走这条路径，保证"改数字看结果"不会污染历史。
    """
    _, chemicals = await _load_unit_and_chemicals(db, unit_id)
    result = _run_engine(chemicals, exposed_population)
    return {
        "s_value": round(result.s_value, 6),
        "r_value": round(result.r_value, 6),
        "alpha": result.alpha,
        "exposed_population": exposed_population,
        "is_major_hazard": result.is_major_hazard,
        "level": result.level,
        "formula_version": FORMULA_VERSION,
        "standard": STANDARD,
        "chemicals": list(result.items),
    }
```

同时把 `compute_unit_snapshot` 里重复的取数与计算改为复用上面两个 helper：

```python
async def compute_unit_snapshot(
    db: AsyncSession,
    *,
    unit_id: str,
    exposed_population: int,
    user_id: str | None = None,
) -> dict:
    """对指定单元执行一次计算并写入不可变快照，返回快照内容。"""
    _, chemicals = await _load_unit_and_chemicals(db, unit_id)
    result = _run_engine(chemicals, exposed_population)
    seq = await _next_seq(db, unit_id)
    snapshot = { ... }   # 保持原有构造逻辑不变
```

> 注意：`_load_unit_and_chemicals` 里两次 `scalar_one_or_none()` 会消耗结果集，
> 实现时应先取 `unit = unit_res.scalar_one_or_none()` 再判断并返回，避免第二次调用返回 None。

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_major_hazard_preview.py tests/test_major_hazard_service.py -v
```

预期：`9 passed`（预览 2 + 既有服务 7）

- [ ] **步骤 5：加路由端点**

在 `backend/app/routers/major_hazard.py` 的 `compute_unit` 之前插入：

```python
@router.post("/units/{unit_id}/preview")
async def preview_unit(
    unit_id: str,
    payload: ComputeIn,
    db: AsyncSession = Depends(get_db),
):
    """实时预览：只计算不写快照。前端在输入变化（防抖）时调用。"""
    try:
        snapshot = await preview_unit_calculation(
            db, unit_id=unit_id, exposed_population=payload.exposed_population
        )
    except MajorHazardRuleError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _ok(snapshot)
```

并把顶部 import 改为：

```python
from app.services.major_hazard_service import (
    MajorHazardRuleError,
    compute_unit_snapshot,
    preview_unit_calculation,
)
```

- [ ] **步骤 6：跑后端全量确认无回归**

运行：

```bash
cd backend && python -m pytest tests/ -q
```

预期：失败数不高于 4 个既有失败

- [ ] **步骤 7：Commit**

```bash
git add backend/app/services/major_hazard_service.py backend/app/routers/major_hazard.py backend/tests/test_major_hazard_preview.py
git commit -m "feat(major-hazard): 预览端点（只算不写快照），支撑前端实时预览（任务 1/7）"
```

---

## 任务 2：前端类型与 service 层

**文件：**

- 创建：`frontend/src/types/majorHazard.ts`
- 创建：`frontend/src/services/majorHazardService.ts`
- 测试：`frontend/src/services/majorHazardService.test.ts`
- 创建：`frontend/src/utils/majorHazardFormat.ts` + `.test.ts`

- [ ] **步骤 1：编写失败的测试**

```ts
// frontend/src/services/majorHazardService.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import api from "./api";
import {
  listUnits,
  previewCalculation,
  computeCalculation,
  listCalculations,
  listCriticalQuantities,
} from "./majorHazardService";

vi.mock("./api", () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const mocked = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

describe("majorHazardService", () => {
  beforeEach(() => vi.clearAllMocks());

  it("listUnits 走 /major-hazard/units 并带 enterprise_id", async () => {
    mocked.get.mockResolvedValue({ data: { data: [{ id: "u1", name: "罐区A" }] } });
    const out = await listUnits("e1");
    expect(mocked.get).toHaveBeenCalledWith("/major-hazard/units", {
      params: { enterprise_id: "e1" },
    });
    expect(out[0].name).toBe("罐区A");
  });

  it("previewCalculation 调 preview 端点且不传 user", async () => {
    mocked.post.mockResolvedValue({ data: { data: { s_value: "1.5", r_value: "7.5" } } });
    const out = await previewCalculation("u1", 60);
    expect(mocked.post).toHaveBeenCalledWith("/major-hazard/units/u1/preview", {
      exposed_population: 60,
    });
    expect(out.r_value).toBe("7.5");
  });

  it("computeCalculation 调 compute 端点", async () => {
    mocked.post.mockResolvedValue({ data: { data: { seq: 1 } } });
    await computeCalculation("u1", 60);
    expect(mocked.post).toHaveBeenCalledWith("/major-hazard/units/u1/compute", {
      exposed_population: 60,
    });
  });

  it("listCalculations 取快照列表", async () => {
    mocked.get.mockResolvedValue({ data: { data: [{ seq: 2 }, { seq: 1 }] } });
    const out = await listCalculations("u1");
    expect(mocked.get).toHaveBeenCalledWith("/major-hazard/units/u1/calculations");
    expect(out).toHaveLength(2);
  });

  it("listCriticalQuantities 带 keyword", async () => {
    mocked.get.mockResolvedValue({ data: { data: [] } });
    await listCriticalQuantities("氯");
    expect(mocked.get).toHaveBeenCalledWith("/major-hazard/definitions/critical-quantities", {
      params: { keyword: "氯", limit: 30 },
    });
  });
});
```

```ts
// frontend/src/utils/majorHazardFormat.test.ts
import { describe, expect, it } from "vitest";
import { toNumber, formatQty, levelColor, computeConclusionText } from "./majorHazardFormat";

describe("majorHazardFormat", () => {
  it("toNumber 兼容后端 Decimal 字符串", () => {
    expect(toNumber("1.500000")).toBe(1.5);
    expect(toNumber(2)).toBe(2);
    expect(toNumber(null)).toBeNull();
    expect(toNumber("abc")).toBeNull();
  });

  it("formatQty 去掉无意义尾零", () => {
    expect(formatQty("5.000000")).toBe("5");
    expect(formatQty("0.300000")).toBe("0.3");
    expect(formatQty(null)).toBe("—");
  });

  it("levelColor 按等级给色", () => {
    expect(levelColor("一级")).toBe("red");
    expect(levelColor("二级")).toBe("orange");
    expect(levelColor("三级")).toBe("gold");
    expect(levelColor("四级")).toBe("blue");
    expect(levelColor(null)).toBe("default");
  });

  it("computeConclusionText 区分"不构成"与"未计算"", () => {
    expect(computeConclusionText(null)).toBe("未计算");
    expect(computeConclusionText({ is_major_hazard: false, level: null })).toBe("不构成");
    expect(computeConclusionText({ is_major_hazard: true, level: "二级" })).toBe("二级");
  });
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx vitest run src/services/majorHazardService.test.ts src/utils/majorHazardFormat.test.ts
```

预期：FAIL，模块不存在

> 前端测试必须在容器内跑（宿主 `node_modules` 只有 Linux 原生包）。若容器名不同用 `docker ps` 确认。

- [ ] **步骤 3：编写类型**

```ts
// frontend/src/types/majorHazard.ts
// 注意：后端 Decimal 字段经 FastAPI 序列化为【字符串】（保精度），
// 展示前统一用 utils/majorHazardFormat.toNumber / formatQty 转换。

export interface MajorHazardUnit {
  id: string;
  enterprise_id: string;
  name: string;
  unit_type: "production" | "storage";
  address?: string | null;
  department?: string | null;
  responsible_person?: string | null;
  responsible_phone?: string | null;
  risk_object_id?: string | null;
  is_active: boolean;
  created_at?: string | null;
}

export interface MajorHazardUnitPayload {
  name: string;
  unit_type: "production" | "storage";
  boundary_desc?: string | null;
  floor_id?: string | null;
  address?: string | null;
  department?: string | null;
  responsible_person?: string | null;
  responsible_phone?: string | null;
  risk_object_id?: string | null;
  is_active?: boolean;
}

export interface MajorHazardUnitChemical {
  id: string;
  unit_id: string;
  chemical_id?: string | null;
  chemical_name: string;
  physical_state?: string | null;
  storage_location?: string | null;
  q_design_max: string;
  q_actual?: string | null;
  critical_quantity_t: string;
  beta: string;
  beta_source: "table3" | "table4" | "manual";
}

export type MajorHazardUnitChemicalPayload = Omit<
  MajorHazardUnitChemical,
  "id" | "unit_id"
>;

export interface MajorHazardCalculation {
  id: string;
  seq: number;
  s_value: string;
  r_value: string;
  alpha: string;
  exposed_population: number;
  is_major_hazard: boolean;
  level?: string | null;
  formula_version: string;
  calculated_at?: string | null;
}

/** 预览与固化共用同一形状（预览不含 id/seq/calculated_at）。 */
export interface MajorHazardPreviewResult {
  seq?: number;
  s_value: string | number;
  r_value: string | number;
  alpha: string | number;
  exposed_population: number;
  is_major_hazard: boolean;
  level?: string | null;
  formula_version: string;
  chemicals: Array<{
    name: string;
    q: number;
    Q: number;
    beta: number;
    q_over_Q: number;
    beta_times_q_over_Q: number;
  }>;
}

export interface CriticalQuantity {
  chemical_name: string;
  alias?: string | null;
  cas_no?: string | null;
  critical_t?: string | null;
  critical_note?: string | null;
  table_no: string;
  source_page?: number | null;
}

export interface MajorHazardRecord {
  id: string;
  unit_id: string;
  enterprise_id: string;
  hazard_code?: string | null;
  filing_status: string;
  filing_no?: string | null;
  filing_date?: string | null;
  chief_name?: string | null;
  chief_post?: string | null;
  chief_phone?: string | null;
  tech_name?: string | null;
  tech_post?: string | null;
  tech_phone?: string | null;
  oper_name?: string | null;
  oper_post?: string | null;
  oper_phone?: string | null;
  attachments: Record<string, unknown>;
  completeness: Record<string, unknown>;
}

export interface EvidenceItem {
  id: string;
  regulation_id?: string | null;
  article_anchor: string;
  relation: string;
  note?: string | null;
}
```

- [ ] **步骤 4：编写 service**

```ts
// frontend/src/services/majorHazardService.ts
import api from "./api";
import type { ApiResponse } from "@/types/common";
import type {
  CriticalQuantity,
  EvidenceItem,
  MajorHazardCalculation,
  MajorHazardPreviewResult,
  MajorHazardRecord,
  MajorHazardUnit,
  MajorHazardUnitChemical,
  MajorHazardUnitChemicalPayload,
  MajorHazardUnitPayload,
} from "@/types/majorHazard";

const BASE = "/major-hazard";

// --- 常量查询 ---
export const listCriticalQuantities = (keyword?: string) =>
  api
    .get<ApiResponse<CriticalQuantity[]>>(`${BASE}/definitions/critical-quantities`, {
      params: { keyword, limit: 30 },
    })
    .then((r) => r.data.data);

// --- 单元 ---
export const listUnits = (enterpriseId: string) =>
  api
    .get<ApiResponse<MajorHazardUnit[]>>(`${BASE}/units`, {
      params: { enterprise_id: enterpriseId },
    })
    .then((r) => r.data.data);

export const createUnit = (enterpriseId: string, payload: MajorHazardUnitPayload) =>
  api
    .post<ApiResponse<MajorHazardUnit>>(`${BASE}/units`, payload, {
      params: { enterprise_id: enterpriseId },
    })
    .then((r) => r.data.data);

export const updateUnit = (unitId: string, payload: MajorHazardUnitPayload) =>
  api.put<ApiResponse<MajorHazardUnit>>(`${BASE}/units/${unitId}`, payload).then((r) => r.data.data);

export const deleteUnit = (unitId: string) => api.delete(`${BASE}/units/${unitId}`);

// --- 单元品种 ---
export const listUnitChemicals = (unitId: string) =>
  api
    .get<ApiResponse<MajorHazardUnitChemical[]>>(`${BASE}/units/${unitId}/chemicals`)
    .then((r) => r.data.data);

export const replaceUnitChemicals = (
  unitId: string,
  payload: MajorHazardUnitChemicalPayload[],
) =>
  api
    .put<ApiResponse<{ unit_id: string; count: number }>>(
      `${BASE}/units/${unitId}/chemicals`,
      payload,
    )
    .then((r) => r.data.data);

// --- 计算 ---
/** 实时预览：只算不写快照。调用方需自行防抖。 */
export const previewCalculation = (unitId: string, exposedPopulation: number) =>
  api
    .post<ApiResponse<MajorHazardPreviewResult>>(`${BASE}/units/${unitId}/preview`, {
      exposed_population: exposedPopulation,
    })
    .then((r) => r.data.data);

/** 固化：写一条不可变快照。 */
export const computeCalculation = (unitId: string, exposedPopulation: number) =>
  api
    .post<ApiResponse<MajorHazardPreviewResult>>(`${BASE}/units/${unitId}/compute`, {
      exposed_population: exposedPopulation,
    })
    .then((r) => r.data.data);

export const listCalculations = (unitId: string) =>
  api
    .get<ApiResponse<MajorHazardCalculation[]>>(`${BASE}/units/${unitId}/calculations`)
    .then((r) => r.data.data);

// --- 档案 ---
export const getUnitRecord = (unitId: string) =>
  api
    .get<ApiResponse<MajorHazardRecord>>(`${BASE}/units/${unitId}/record`, {
      skipGlobalError: true,
    })
    .then((r) => r.data.data);

export const upsertUnitRecord = (
  unitId: string,
  enterpriseId: string,
  payload: Partial<MajorHazardRecord>,
) =>
  api
    .put<ApiResponse<MajorHazardRecord>>(`${BASE}/units/${unitId}/record`, payload, {
      params: { enterprise_id: enterpriseId },
    })
    .then((r) => r.data.data);

// --- 依据 ---
export const listUnitEvidence = (unitId: string) =>
  api
    .get<ApiResponse<EvidenceItem[]>>(`${BASE}/units/${unitId}/evidence`)
    .then((r) => r.data.data);

export const attachUnitEvidence = (
  unitId: string,
  items: Array<{ article_anchor: string; regulation_id?: string; relation?: string; note?: string }>,
) =>
  api
    .post<ApiResponse<{ created: number }>>(`${BASE}/units/${unitId}/evidence`, items)
    .then((r) => r.data.data);
```

- [ ] **步骤 5：编写格式化工具**

```ts
// frontend/src/utils/majorHazardFormat.ts
/** 后端 Decimal 走线是字符串，这里统一转换；非法值返回 null 而不是 0。 */
export function toNumber(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function formatQty(v: string | number | null | undefined, digits = 6): string {
  const n = toNumber(v);
  if (n === null) return "—";
  // 去尾零：5.000000 -> "5"，0.300000 -> "0.3"
  return String(Number(n.toFixed(digits)));
}

export type LevelColor = "red" | "orange" | "gold" | "blue" | "default";

export function levelColor(level?: string | null): LevelColor {
  switch (level) {
    case "一级":
      return "red";
    case "二级":
      return "orange";
    case "三级":
      return "gold";
    case "四级":
      return "blue";
    default:
      return "default";
  }
}

/** 列表"结论"列文案。区分"不构成"（算过了）与"未计算"（没算过）——两者含义完全不同。 */
export function computeConclusionText(
  latest?: { is_major_hazard: boolean; level?: string | null } | null,
): string {
  if (!latest) return "未计算";
  return latest.is_major_hazard ? latest.level || "构成" : "不构成";
}
```

- [ ] **步骤 6：运行测试验证通过**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx vitest run src/services/majorHazardService.test.ts src/utils/majorHazardFormat.test.ts
```

预期：两个文件全绿（service 5 例 + format 4 例）

- [ ] **步骤 7：类型检查**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
```

预期：exit 0

- [ ] **步骤 8：Commit**

```bash
git add frontend/src/types/majorHazard.ts frontend/src/services/majorHazardService.ts frontend/src/services/majorHazardService.test.ts frontend/src/utils/majorHazardFormat.ts frontend/src/utils/majorHazardFormat.test.ts
git commit -m "feat(major-hazard): 前端类型、service 层与格式化工具（任务 2/7）"
```

---

## 任务 3：模块入口与路由（11 → 12）

**文件：**

- 修改：`frontend/src/components/enterprise/cockpit/ModuleNav.tsx`
- 修改：`frontend/src/pages/Enterprise/enterpriseNavConfig.ts`
- 修改：`frontend/src/routes/index.tsx`

- [ ] **步骤 1：在模块注册表里插入「重大危险源」**

`ModuleNav.tsx` 的 `MODULES` 数组中，在 `key: "chem"`（危险化学品）之后插入：

```tsx
  {
    key: "majorHazard",
    label: "重大危险源",
    en: "MAJOR",
    hot: true,
    to: (id) => `/enterprises/${id}/major-hazard`,
    icon: <AppIcon name="safety-certificate" size={24} />,
  },
```

> `AppIcon` 的可用名字见 `frontend/src/components/common/icons.tsx`；
> 若 `safety-certificate` 不在其中，挑一个语义接近的（如 `assessment`），不要新增图标资源。

- [ ] **步骤 2：加侧导航分组**

`enterpriseNavConfig.ts` 追加：

```ts
export function majorHazardNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "台账",
      items: [
        { key: "list", label: "单元台账", to: `/enterprises/${id}/major-hazard` },
      ],
    },
    {
      label: "分析与备案",
      items: [
        { key: "compute", label: "计算与分级", to: `/enterprises/${id}/major-hazard/compute` },
        { key: "record", label: "档案与备案", to: `/enterprises/${id}/major-hazard/record` },
      ],
    },
  ];
}
```

- [ ] **步骤 3：注册路由**

在 `frontend/src/routes/index.tsx` 里**照抄现有企业模块路由的写法**（同一层级、同样的懒加载与权限包裹方式）追加 4 条：

```
/enterprises/:id/major-hazard                        → MajorHazardListPage
/enterprises/:id/major-hazard/units/:unitId          → MajorHazardUnitPage
/enterprises/:id/major-hazard/compute                → MajorHazardComputePage
/enterprises/:id/major-hazard/record                 → MajorHazardRecordPage
```

> 该文件已有 `risk-management` 与 `hazard` 两组同构路由，照着它们写；
> 不要自创新的包裹组件或权限写法。

- [ ] **步骤 4：验证路由可达**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
```

预期：`tsc` exit 0；vitest 全绿（此时页面组件是占位导出，任务 4~7 逐个替换）

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/enterprise/cockpit/ModuleNav.tsx frontend/src/pages/Enterprise/enterpriseNavConfig.ts frontend/src/routes/index.tsx
git commit -m "feat(major-hazard): 模块入口 11→12 与 4 条路由（任务 3/7）"
```

---

## 任务 4：单元台账页

**文件：**

- 创建：`frontend/src/pages/Enterprise/MajorHazardListPage.tsx`

**关键行为（视觉走查确认）：** 列表的「结论」列读**最近一次快照**，不在打开列表时实时重算——单元多了以后每次开列表都跑计算会很慢，且没必要。

- [ ] **步骤 1：实现页面**

要点（照 `RiskControlListPage.tsx` 的结构写，保持一致的表格/筛选/分页风格）：

1. `useQuery(["major-hazard-units", id], () => listUnits(id!))` 取单元
2. 每个单元并发取 `listCalculations(unitId)` 的**第一条**（后端按 `seq desc` 返回）作为"最近结论"
3. 列：单元名称 / 类型（生产单元·储存单元）/ 责任部门·责任人 / 涉及品种数 / 最近计算时间 / 结论（用 `Tag color={levelColor(level)}` + `computeConclusionText`）/ 操作（详情·计算·档案·删除）
4. 顶部「+ 新增单元」用 `ModalForm`：名称必填、类型单选（`production` / `storage`）、责任部门、责任人、联系电话
5. 删除前 `Modal.confirm`，提示会一并删除该单元下的品种与全部计算快照（后端是级联删除）

```tsx
// 结论列渲染（关键片段）
<Tag color={levelColor(latest?.level)}>
  {computeConclusionText(latest)}
</Tag>
```

- [ ] **步骤 2：验证**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx eslint src/pages/Enterprise/MajorHazardListPage.tsx
```

预期：`tsc` exit 0；eslint 无新增错误

- [ ] **步骤 3：真实浏览器冒烟**

在后端可用的环境下打开 `/enterprises/<真实id>/major-hazard`，确认：

1. 模块导航里出现「重大危险源」且点击进入本页
2. 新建一个单元后列表出现该行
3. 「结论」列显示 **未计算**（而不是"不构成"）

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/pages/Enterprise/MajorHazardListPage.tsx
git commit -m "feat(major-hazard): 单元台账页（结论列读最近快照）（任务 4/7）"
```

---

## 任务 5：单元详情页（基本信息 + 品种存量）

**文件：**

- 创建：`frontend/src/components/enterprise/majorHazard/UnitChemicalTable.tsx`
- 创建：`frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx`

**关键行为（视觉走查确认）：** 录入品种时按名称/CAS 自动匹配 GB 18218 表1 带出 `critical_quantity_t` 与 `beta`；匹配不到时提示选危险性类别走表2/表4；**两者都定不了不允许保存**（不能默认取 1）；`q_design_max` 允许从危化品台账 `max_storage` 带出初值，但**必须人工确认**，字段旁标注口径差异。

- [ ] **步骤 1：实现品种存量表组件**

`UnitChemicalTable` 要点：

1. 可编辑表格（antd `Table` + 行内 `Input`/`InputNumber`/`Select`），列：品种名称 / 设计最大量(t) / 临界量 Q(t) / 来源标记 / β / q÷Q（只读，实时算）
2. 「品种名称」用 `AutoComplete`，输入 ≥ 2 字时（防抖 300ms）调 `listCriticalQuantities(keyword)`；
3. 选中某条后自动填 `critical_quantity_t`（`critical_t`）与 `beta`：表1 命中时 `beta` 从表3/表4 仍未取到 → 留空并提示"请选择危险性类别"；选择类别后按表4 填 β
4. **`q_design_max` 输入框下方常驻提示**：

```tsx
<div style={{ fontSize: 11, color: "#b45309" }}>
  设计最大量口径（GB 18218 4.2.2），通常 ≥ 台账最大储存量；请勿直接照抄台账数字
</div>
```

5. `q÷Q` 实时列：`formatQty(toNumber(q) / toNumber(Q))`，`Q` 为 0 或空时显示 `—`
6. 底部汇总一行：`Σq/Q = X.XXX`，`≥ 1 则构成`（仅提示，正式结论以后端计算为准）

- [ ] **步骤 2：实现详情页**

`MajorHazardUnitPage` 两个 Tab：

- **Tab 1 基本信息**：表单编辑名称/类型/边界描述/责任部门/责任人/电话，`updateUnit` 保存
- **Tab 2 品种与存量**：挂 `UnitChemicalTable`，保存时调 `replaceUnitChemicals`（整体替换语义，后端已实现）

页面右上角放两个按钮：「去计算」跳 `/enterprises/:id/major-hazard/compute?unitId=xxx`、「档案」跳 record 页。

- [ ] **步骤 3：验证**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
```

预期：`tsc` exit 0；vitest 全绿

- [ ] **步骤 4：真实浏览器冒烟**

1. 进入某单元的「品种与存量」，输入「氯」→ 应自动带出 Q=5、β 提示
2. 保存后刷新，数据仍在
3. **故意留空 Q 后保存** → 应被表单校验拦下，不允许提交

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/enterprise/majorHazard/UnitChemicalTable.tsx frontend/src/pages/Enterprise/MajorHazardUnitPage.tsx
git commit -m "feat(major-hazard): 单元详情与品种存量录入（自动带出临界量/β，设计最大量口径提示）（任务 5/7）"
```

---

## 任务 6：计算与分级页（实时预览 + 手动固化）

**文件：**

- 创建：`frontend/src/pages/Enterprise/MajorHazardComputePage.tsx`

**关键行为（视觉走查确认）：** 改动输入即时显示 s/R 并**明确标注"预览，未保存"**；点「固化本次结果」才写不可变快照。理由：快照是不可变审计凭证，"何时写库"直接决定可追溯性。

- [ ] **步骤 1：实现页面**

结构：

1. 顶部单元选择（`Select`，默认取 query 里的 `unitId`）
2. **暴露人数输入**：`InputNumber`（厂外 500m 内可能暴露人员数量），旁边给出 α 档位提示（0 人=0.5 / 1~29=1.0 / 30~49=1.2 / 50~99=1.5 / ≥100=2.0）
3. **预览区**（虚线框，灰底，标注"预览（未保存）"）：
   - 调 `previewCalculation(unitId, population)`，**防抖 500ms**
   - 展示 `α → R → 等级`，等级用 `levelColor` 上色
   - 下方折叠面板展示逐品种明细（名称 / q / Q / β / q÷Q / β×q÷Q）
4. **固化按钮**：「固化本次结果」→ `computeCalculation` → 成功后失效 `["major-hazard-calculations", unitId]` 并提示"已固化第 N 次计算"
5. **快照历史表**：`listCalculations(unitId)`，列：序号 / 计算时间 / 暴露人数 / α / s / R / 等级，行展开显示该次 `inputs_snapshot` 的品种明细
6. 单元未录品种时，预览请求会返回 422（"该单元尚未录入危险化学品"）→ 页面显示空状态并给「去录入品种」按钮，**不要显示成错误 toast**

```tsx
// 防抖预览（关键片段）
const [population, setPopulation] = useState(0);
const debouncedPopulation = useDebounce(population, 500);

const preview = useQuery({
  queryKey: ["major-hazard-preview", unitId, debouncedPopulation],
  queryFn: () => previewCalculation(unitId!, debouncedPopulation),
  enabled: !!unitId,
  retry: false,
});
```

> `useDebounce` 若项目内没有，就在本页内联实现（`useEffect` + `setTimeout` 12 行），
> **不要为此新增依赖**。

- [ ] **步骤 2：验证**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx eslint src/pages/Enterprise/MajorHazardComputePage.tsx
```

预期：`tsc` exit 0；eslint 无新增错误

- [ ] **步骤 3：真实浏览器端到端**

用「氯 5t / Q=5 / β=4」+「氨 5t / Q=10 / β=2」、暴露人数 60 走一遍：

1. 输入 60 后，预览区出现 **α=1.5 → R=7.5 → 四级**，且明确标着"未保存"
2. **改人数为 0**，预览立刻变 **R=2.5**，快照历史**没有新增行**（这是"预览不写库"的关键验证）
3. 点「固化本次结果」→ 快照历史新增 1 行，序号 1
4. 再点一次固化 → 新增序号 2，**序号 1 的内容不变**

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/pages/Enterprise/MajorHazardComputePage.tsx
git commit -m "feat(major-hazard): 计算与分级页（实时预览 + 手动固化 + 快照历史）（任务 6/7）"
```

---

## 任务 7：档案与备案页 + 依据面板

**文件：**

- 创建：`frontend/src/components/enterprise/majorHazard/EvidencePanel.tsx`
- 创建：`frontend/src/pages/Enterprise/MajorHazardRecordPage.tsx`

- [ ] **步骤 1：实现依据面板（可复用组件）**

`EvidencePanel` 接收 `{ ownerType: string; ownerId: string; listFn; attachFn }`，用于让作业票模块将来直接复用：

- 列表展示已挂条文：`article_anchor` + `relation` + 备注
- 「添加依据」`Modal`：条文锚点（必填，占位符示例 `GB 18218-2018 4.2.1`）、法规 id（可选）、关系（依据/引用/冲突）、备注
- 同一条文重复挂载时后端幂等返回 `created: 0`，前端提示"该依据已存在"

- [ ] **步骤 2：实现档案页**

1. 顶部单元选择
2. 「备案信息」表单：危险源编码、备案状态（未备案/已备案/变更中）、备案号、备案日期
3. 「包保责任人」三组（主要负责人 / 技术负责人 / 操作负责人）×（姓名 / 职务 / 联系电话）
4. 「资料完整性」区：按 GB 18218 备案惯例列出所需资料清单（基础资料、区域位置图、平面布置图、工艺流程图、设备一览表、安全评价报告、评估报告、重点部位签字、其他），每项可标记已具备 + 上传附件占位
5. 「法规依据」区：`<EvidencePanel ownerType="major_hazard_unit" ownerId={unitId} .../>`，并在页面加载时自动挂载本条标准依据：`GB 18218-2018 4.2.1`（辨识指标）、`GB 18218-2018 4.3.2`（分级指标）、`GB 18218-2018 表6`（分级标准）
6. 保存调 `upsertUnitRecord`（后端是「不存在则建、存在则局部更新」语义，故 `GET` 404 不代表出错————`getUnitRecord` 已设 `skipGlobalError: true`，页面要自己 catch 并把 404 当"尚未建档"处理）

- [ ] **步骤 3：验证**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
docker exec -w /app emergency-plan-frontend npx eslint src/pages/Enterprise/MajorHazardRecordPage.tsx src/components/enterprise/majorHazard/EvidencePanel.tsx
```

预期：`tsc` exit 0；vitest 全绿；eslint 无新增错误

- [ ] **步骤 4：真实浏览器冒烟**

1. 首次进入档案页**不报错**（后端 404 → 页面显示"尚未建档"）
2. 填备案信息保存成功，刷新后数据在
3. 依据面板能看到 3 条 GB 18218 条文；重复添加同一条文提示"已存在"且不产生重复行

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/enterprise/majorHazard/EvidencePanel.tsx frontend/src/pages/Enterprise/MajorHazardRecordPage.tsx
git commit -m "feat(major-hazard): 档案备案页与依据面板（EvidencePanel 可复用）（任务 7/7）"
```

---

## 验收清单

- [ ] `docker exec -w /app emergency-plan-frontend npx tsc -b` exit 0
- [ ] `docker exec -w /app emergency-plan-frontend npx vitest run` 全绿，且新增用例数 ≥ 9
- [ ] `cd backend && python -m pytest tests/ -q` 失败数不高于 4 个既有失败
- [ ] 模块导航出现「重大危险源」，4 条路由可达
- [ ] 建单元 → 录品种（自动带出 Q 与 β）→ 预览（不写库）→ 固化（写快照）全链路走通
- [ ] **预览不写库**：改人数使预览刷新多次后，`major_hazard_calculations` 行数不变（这条必须单独验证，它是"手动固化"语义的核心）
- [ ] **结论列不误报**：从未计算过的单元显示「未计算」，算过且不构成的显示「不构成」
- [ ] 设计最大量输入框旁的口径提示可见
- [ ] 档案页首次进入不报错；依据可挂、可幂等去重

## 未纳入本计划

- 单元在四色图/平面图上的落点绘制（复用 `RiskMappingWorkbenchPage` 的现有能力，属于计划 7「跨模块关联打通」）
- 辨识报告导出（计划 4）
- 批量计算多个单元（规格里定为 P1 场景）
- 危化品台账 `max_storage` 带出初值的**自动读取**（本计划只做提示与手填；自动读取要等计划 7 打通台账关联后接线）
