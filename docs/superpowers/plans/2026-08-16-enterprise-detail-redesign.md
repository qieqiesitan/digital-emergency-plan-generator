# 企业驾驶舱（企业详情页重构）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。
> 规格：`docs/superpowers/specs/2026-08-16-enterprise-detail-redesign.md`（commit e2e7594）。

**目标：** 把企业详情页 `/enterprises/:id` 从 Tabs 重构为深色科技感「企业驾驶舱」总览页，10 个功能模块图标平铺导航；模块页保持现有浅色风格，复杂模块（风险管控、隐患治理）加左竖分组导航。

**架构：** 前端新增驾驶舱页面与模块页外壳（`ModulePageShell`），复用全部现有 Tab 组件与子页面；后端新增 1 个 `cockpit-summary` 汇总端点（服务层聚合 + 归属校验）。驾驶舱样式为独立 `cockpit.css`，不污染全局。

**技术栈：** FastAPI + SQLAlchemy async（后端）；React 19 + React Router 7 + Ant Design 6 + TanStack Query + Vitest（前端）；Playwright e2e。

**实现环境：** 实现阶段在独立 worktree（分支 `codex/enterprise-cockpit`，基于当前 master）中进行，遵循 `using-git-worktrees` 技能。

---

## 文件结构

**后端（新增 3 / 修改 1）：**

| 文件 | 职责 |
|------|------|
| `backend/app/services/enterprise_cockpit_service.py` | 新增：驾驶舱汇总聚合（纯函数 + 查询编排） |
| `backend/app/schemas/enterprise_cockpit.py` | 新增：CockpitSummary 系列 Pydantic 模型 |
| `backend/app/routers/enterprises.py` | 修改：新增 `GET /{enterprise_id}/cockpit-summary` 端点 |
| `backend/tests/test_enterprise_cockpit.py` | 新增：纯函数单测 + 端点测试 |

**前端（新增 13 / 修改 5）：**

| 文件 | 职责 |
|------|------|
| `frontend/src/types/cockpit.ts` | 新增：驾驶舱数据类型 |
| `frontend/src/services/cockpitService.ts` | 新增：汇总端点前端服务（箭头函数 + 解包惯例） |
| `frontend/src/services/cockpitService.test.ts` | 新增：URL/解包契约测试 |
| `frontend/src/styles/cockpit.css` | 新增：驾驶舱设计系统（令牌/背景层/动效/面板） |
| `frontend/src/components/enterprise/cockpit/CockpitBackground.tsx` | 新增：背景层（网格/光晕/粒子/数据流/扫描线/地台） |
| `frontend/src/components/enterprise/cockpit/CockpitHeader.tsx` | 新增：顶栏 |
| `frontend/src/components/enterprise/cockpit/CockpitTicker.tsx` | 新增：数据跑马灯 |
| `frontend/src/components/enterprise/cockpit/RiskDonutPanel.tsx` | 新增：风险等级分布环形图 + 图例 + 重大风险 TOP |
| `frontend/src/components/enterprise/cockpit/RiskRadarPanel.tsx` | 新增：风险雷达 + 分区风险分布 |
| `frontend/src/components/enterprise/cockpit/CockpitTodoPanel.tsx` | 新增：待办提醒 |
| `frontend/src/components/enterprise/cockpit/CockpitCompletionPanel.tsx` | 新增：数据完成度环 + 模块清单 |
| `frontend/src/components/enterprise/cockpit/CockpitActivityPanel.tsx` | 新增：最近动态 |
| `frontend/src/components/enterprise/cockpit/ModuleNav.tsx` | 新增：10 模块图标导航（内联 SVG） |
| `frontend/src/components/enterprise/cockpit/ModulePageShell.tsx` | 新增：模块页外壳（返回驾驶舱 + ModuleSideNav + Outlet） |
| `frontend/src/components/enterprise/cockpit/ModuleSideNav.tsx` | 新增：左竖分组导航 |
| `frontend/src/pages/Enterprise/EnterpriseCockpitPage.tsx` | 新增：驾驶舱主页面 |
| `frontend/src/routes/index.tsx` | 修改：驾驶舱替换详情页 + 模块页/壳路由 + 旧路径重定向 |
| `frontend/src/pages/Enterprise/EnterpriseModulePage.tsx` | 新增：简单模块通用包装页（/modules/:moduleKey） |
| `frontend/src/pages/Enterprise/enterpriseNavConfig.ts` | 新增：风险/隐患模块左竖导航分组配置 |
| `frontend/src/pages/Enterprise/RiskManagementTab.tsx` | 修改：加 `embedded` prop + `?floor=1` 自动开楼层抽屉 |
| `frontend/src/pages/Hazard/HazardInspectionTab.tsx` | 修改：加 `embedded` prop 隐藏内部按钮行 |

> 说明：`EnterpriseOrgPage` 现有 `onBack` 已指向 `/enterprises/${enterpriseId}`，路由改为驾驶舱后自动生效，无需修改；`PlanListPage` 保留其自身返回逻辑（返回预案总览），不做修改。

---

### 任务 1：后端驾驶舱聚合服务（纯函数 + 查询编排）

**文件：**
- 创建：`backend/app/services/enterprise_cockpit_service.py`
- 测试：`backend/tests/test_enterprise_cockpit.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_enterprise_cockpit.py`：

```python
from datetime import date, timedelta

import pytest

from app.services.enterprise_cockpit_service import (
    _classify_level,
    _risk_index,
    aggregate_events,
    derive_todos,
)


class FakeEvent:
    def __init__(self, level="一般", score="60", zone="生产车间", obj="反应釜区", unit=None, responsible=None):
        self.risk_level = level
        self.risk_score = score
        self._zone = zone
        self._obj = obj
        self._unit = unit
        self._responsible = responsible

    @property
    def zone(self):
        return type("Z", (), {"name": self._zone})()

    @property
    def object(self):
        o = type("O", (), {"name": self._obj, "responsible_unit": self._responsible})
        o.zone = self.zone
        return o

    @property
    def unit(self):
        if self._unit is None:
            return None
        u = type("U", (), {"name": self._unit})
        u.object = self.object
        return u


def test_classify_level():
    assert _classify_level("重大") == "major"
    assert _classify_level("较大") == "larger"
    assert _classify_level("一般") == "general"
    assert _classify_level("低") == "low"
    assert _classify_level(None) == "general"
    assert _classify_level("未知") == "general"


def test_risk_index_formula_and_clamp():
    assert _risk_index({"major": 2, "larger": 4, "general": 18, "low": 10}) == 38
    assert _risk_index({"major": 5, "larger": 0, "general": 0, "low": 0}) == 100


def test_aggregate_events_counts_zones_and_top():
    events = [
        FakeEvent("重大", "82", "生产车间", "反应釜区", responsible="生产部"),
        FakeEvent("较大", "74", "生产车间", "反应釜区"),
        FakeEvent("一般", "45", "生产车间", "烘干车间"),
        FakeEvent("低", "20", "办公楼", "办公室"),
    ]
    out = aggregate_events(events)
    assert out["risk_counts"] == {"major": 1, "larger": 1, "general": 1, "low": 1, "total": 4}
    assert out["risk_index"] == 55
    assert out["zone_risks"][0]["zone_name"] == "生产车间"
    assert out["zone_risks"][0]["total"] == 3
    assert out["top_risks"][0]["name"] == "反应釜区"
    assert out["top_risks"][0]["score"] == 82
    assert out["top_risks"][0]["responsible_unit"] == "生产部"


def test_derive_todos_reports_hazard_surrounding():
    todos = derive_todos(
        reports={"assessment": False, "investigation": True},
        open_hazard_count=3,
        due_hazard_count=2,
        overdue_hazard_count=0,
        completion_modules=[
            {"key": "surrounding", "label": "周边环境", "done": False},
            {"key": "reports", "label": "报告", "done": False},
        ],
    )
    assert todos[0]["title"] == "风险评估报告未生成"
    assert todos[0]["priority"] == "high"
    assert any(t["title"].startswith("2 条隐患整改即将到期") for t in todos)
    assert len(todos) == 3


def test_derive_todos_empty():
    todos = derive_todos(
        reports={"assessment": True, "investigation": True},
        open_hazard_count=0,
        due_hazard_count=0,
        overdue_hazard_count=0,
        completion_modules=[],
    )
    assert todos == []
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd backend && python -m pytest tests/test_enterprise_cockpit.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.enterprise_cockpit_service'`

- [ ] **步骤 3：实现聚合服务**

创建 `backend/app/services/enterprise_cockpit_service.py`：

```python
"""企业驾驶舱汇总服务。"""
from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.hazard_management import HazardRecord
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport
from app.models.risk_management import RiskEvent, RiskObject, RiskUnit, RiskZone
from app.services.onboarding_service import compute_completion

LEVEL_KEY = {"重大": "major", "较大": "larger", "一般": "general", "低": "low"}
LEVEL_ORDER = {"重大": 0, "较大": 1, "一般": 2, "低": 3}


def _classify_level(level: str | None) -> str:
    """归一化风险等级；缺失/未知按『一般』处理。"""
    return LEVEL_KEY.get(level, "general")


def _risk_index(counts: dict) -> int:
    total = counts.get("total") or (
        counts["major"] + counts["larger"] + counts["general"] + counts["low"]
    )
    if total <= 0:
        return 0
    weighted = (
        counts["major"] * 100
        + counts["larger"] * 70
        + counts["general"] * 40
        + counts["low"] * 10
    )
    return min(100, round(weighted / total))


def _event_zone_name(e: RiskEvent) -> str:
    zone = getattr(getattr(e, "object", None), "zone", None)
    if zone is None:
        unit = getattr(e, "unit", None)
        zone = getattr(getattr(unit, "object", None), "zone", None)
    return zone.name if zone else "未分区"


def _event_object(e: RiskEvent):
    obj = getattr(e, "object", None)
    if obj is None and getattr(e, "unit", None) is not None:
        obj = getattr(e.unit, "object", None)
    return obj


def _event_level(e: RiskEvent) -> str:
    return e.risk_level or "一般"


def _parse_score(raw: str | None) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def aggregate_events(events: list) -> dict:
    """纯函数：由事件列表聚合出等级分布/分区分布/TOP/风险指数。"""
    counts = {"major": 0, "larger": 0, "general": 0, "low": 0, "total": 0}
    zone_map: dict[str, dict] = {}
    object_map: dict[str, dict] = {}

    for e in events:
        key = _classify_level(_event_level(e))
        counts[key] += 1
        counts["total"] += 1

        zname = _event_zone_name(e)
        zone = zone_map.setdefault(
            zname, {"zone_name": zname, "counts": {"major": 0, "larger": 0, "general": 0, "low": 0}, "total": 0}
        )
        zone["counts"][key] += 1
        zone["total"] += 1

        obj = _event_object(e)
        oname = obj.name if obj else "未命名风险点"
        score = _parse_score(e.risk_score) or 0.0
        entry = object_map.get(oname)
        if entry is None or score > (entry.get("score") or 0):
            object_map[oname] = {
                "name": oname,
                "level": _event_level(e),
                "score": score,
                "responsible_unit": getattr(obj, "responsible_unit", None) if obj else None,
            }

    top_risks = sorted(object_map.values(), key=lambda x: x["score"] or 0, reverse=True)[:3]
    zone_risks = sorted(zone_map.values(), key=lambda z: z["total"], reverse=True)
    return {
        "risk_counts": counts,
        "zone_risks": zone_risks,
        "top_risks": top_risks,
        "risk_index": _risk_index(counts),
    }


def derive_todos(
    reports: dict,
    open_hazard_count: int,
    due_hazard_count: int,
    overdue_hazard_count: int,
    completion_modules: list,
) -> list[dict]:
    """纯函数：由报告/隐患/完成度信号派生待办（最多 3 条）。"""
    todos: list[dict] = []
    if not reports.get("assessment"):
        todos.append({"priority": "high", "title": "风险评估报告未生成", "note": "建议本周完成 · AI 可辅助生成"})
    if not reports.get("investigation"):
        todos.append({"priority": "medium", "title": "应急资源调查报告未生成", "note": "建议本周完成 · AI 可辅助生成"})
    if overdue_hazard_count > 0:
        todos.append({"priority": "high", "title": f"{overdue_hazard_count} 条隐患整改已逾期", "note": "请尽快安排整改闭环"})
    elif due_hazard_count > 0:
        todos.append({"priority": "medium", "title": f"{due_hazard_count} 条隐患整改即将到期", "note": "3 天内到期，请关注"})
    elif open_hazard_count > 0:
        todos.append({"priority": "low", "title": f"{open_hazard_count} 条隐患正在整改中", "note": "整改闭环后自动归档"})

    missing = {m["key"]: m["label"] for m in completion_modules if not m["done"]}
    if "surrounding" in missing:
        todos.append({"priority": "low", "title": "周边环境数据未更新", "note": "可用高德地图一键获取"})
    return todos[:3]


async def _fetch_events(db: AsyncSession, enterprise_id: str) -> list[RiskEvent]:
    rows = await db.execute(
        select(RiskEvent)
        .outerjoin(RiskUnit, RiskEvent.unit_id == RiskUnit.id)
        .join(
            RiskObject,
            (RiskEvent.object_id == RiskObject.id) | (RiskUnit.object_id == RiskObject.id),
        )
        .join(RiskZone, RiskObject.zone_id == RiskZone.id)
        .where(RiskZone.enterprise_id == enterprise_id)
    )
    return list(dict.fromkeys(rows.scalars().all()))


async def build_cockpit_summary(
    db: AsyncSession, enterprise_id: str, enterprise: Enterprise | None = None
) -> dict:
    ent = enterprise
    if ent is None:
        ent = (
            await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))
        ).scalar_one_or_none()
    if not ent:
        raise ValueError("企业不存在")

    events = await _fetch_events(db, enterprise_id)
    aggregated = aggregate_events(events)

    completion = await compute_completion(enterprise_id, db, enterprise=ent)
    completion_payload = {
        "percent": completion["percent"],
        "modules": [
            {"key": m["key"], "label": m["label"], "done": m["done"]}
            for m in completion["modules"]
        ],
    }

    ra_done = bool(
        (
            await db.execute(
                select(func.count()).select_from(RiskAssessmentReport).where(
                    RiskAssessmentReport.enterprise_id == enterprise_id,
                    RiskAssessmentReport.status == "completed",
                )
            )
        ).scalar()
    )
    ri_done = bool(
        (
            await db.execute(
                select(func.count()).select_from(ResourceInvestigationReport).where(
                    ResourceInvestigationReport.enterprise_id == enterprise_id,
                    ResourceInvestigationReport.status == "completed",
                )
            )
        ).scalar()
    )

    today = date.today()
    open_hazards = (
        await db.execute(
            select(HazardRecord).where(
                HazardRecord.enterprise_id == enterprise_id,
                HazardRecord.status != "closed",
            )
        )
    ).scalars().all()
    due = [h for h in open_hazards if h.deadline and h.deadline <= today + timedelta(days=3)]
    overdue = [h for h in open_hazards if h.deadline and h.deadline < today]

    todos = derive_todos(
        reports={"assessment": ra_done, "investigation": ri_done},
        open_hazard_count=len(open_hazards),
        due_hazard_count=len(due),
        overdue_hazard_count=len(overdue),
        completion_modules=completion_payload["modules"],
    )
    hazard_counts = {"open": len(open_hazards), "due": len(due), "overdue": len(overdue)}

    updated_at = ent.updated_at
    recent_activities = [
        {"actor": "系统", "action": "企业档案更新", "time": updated_at.isoformat() if updated_at else ""},
    ]

    return {
        **aggregated,
        "hazard_counts": hazard_counts,
        "todos": todos,
        "completion": completion_payload,
        "recent_activities": recent_activities,
    }
```

> 注：报告模型与 `onboarding_service.py` 一致，直接导入 `RiskAssessmentReport` / `ResourceInvestigationReport` 做 count 查询，避免依赖 `Enterprise` 关系属性。

- [ ] **步骤 4：运行测试确认通过**

运行：`cd backend && python -m pytest tests/test_enterprise_cockpit.py -v`
预期：5 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/tests/test_enterprise_cockpit.py backend/app/services/enterprise_cockpit_service.py
git commit -m "feat(cockpit): enterprise cockpit summary aggregation service"
```

---

### 任务 2：后端 schemas + cockpit-summary 端点

**文件：**
- 创建：`backend/app/schemas/enterprise_cockpit.py`
- 修改：`backend/app/routers/enterprises.py`
- 测试：`backend/tests/test_enterprise_cockpit.py`（追加）

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_enterprise_cockpit.py` 末尾追加：

```python
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.routers import enterprises


def _make_client(db_session):
    app = FastAPI()
    app.include_router(enterprises.router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="a@b.com", name="测试", hashed_password="x"
    )
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_cockpit_summary_returns_404_for_missing_enterprise():
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    client = _make_client(session)
    resp = client.get("/enterprises/nope/cockpit-summary")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "企业不存在"


@patch("app.routers.enterprises.build_cockpit_summary", new_callable=AsyncMock)
def test_cockpit_summary_returns_payload(mock_build):
    mock_build.return_value = {
        "risk_counts": {"major": 1, "larger": 1, "general": 1, "low": 1, "total": 4},
        "zone_risks": [],
        "top_risks": [],
        "risk_index": 55,
        "hazard_counts": {"open": 3, "due": 2, "overdue": 0},
        "todos": [],
        "completion": {"percent": 50, "modules": []},
        "recent_activities": [],
    }
    enterprise = MagicMock(id="e1", user_id="u1")
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=enterprise)))
    client = _make_client(session)
    resp = client.get("/enterprises/e1/cockpit-summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["risk_index"] == 55
    assert data["completion"]["percent"] == 50
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd backend && python -m pytest tests/test_enterprise_cockpit.py -v`
预期：FAIL，`ImportError: cannot import name 'build_cockpit_summary' from 'app.routers.enterprises'`（及 schema 缺失）

- [ ] **步骤 3：实现 schemas**

创建 `backend/app/schemas/enterprise_cockpit.py`：

```python
from pydantic import BaseModel


class RiskCounts(BaseModel):
    major: int = 0
    larger: int = 0
    general: int = 0
    low: int = 0
    total: int = 0


class TopRisk(BaseModel):
    name: str
    level: str
    score: float | None = None
    responsible_unit: str | None = None


class ZoneRisk(BaseModel):
    zone_name: str
    counts: RiskCounts
    total: int = 0


class CockpitTodo(BaseModel):
    priority: str
    title: str
    note: str = ""


class CompletionModule(BaseModel):
    key: str
    label: str
    done: bool


class CockpitCompletion(BaseModel):
    percent: int = 0
    modules: list[CompletionModule] = []


class ActivityItem(BaseModel):
    actor: str = "系统"
    action: str
    time: str = ""


class HazardCounts(BaseModel):
    open: int = 0
    due: int = 0
    overdue: int = 0


class CockpitSummary(BaseModel):
    risk_counts: RiskCounts = RiskCounts()
    zone_risks: list[ZoneRisk] = []
    top_risks: list[TopRisk] = []
    risk_index: int = 0
    hazard_counts: HazardCounts = HazardCounts()
    todos: list[CockpitTodo] = []
    completion: CockpitCompletion = CockpitCompletion()
    recent_activities: list[ActivityItem] = []
```

- [ ] **步骤 4：实现端点**

在 `backend/app/routers/enterprises.py` 中：

1. 顶部 import 追加：

```python
from app.schemas.enterprise_cockpit import CockpitSummary
from app.services.enterprise_cockpit_service import build_cockpit_summary
```

2. 在 `get_enterprise` 端点后追加：

```python
@router.get("/{enterprise_id}/cockpit-summary", response_model=ApiResponse[CockpitSummary])
async def get_enterprise_cockpit_summary(
    enterprise_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Enterprise).where(
            Enterprise.id == enterprise_id,
            Enterprise.user_id == current_user.id,
        )
    )
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="企业不存在")
    data = await build_cockpit_summary(db, enterprise_id, enterprise=e)
    return ApiResponse(data=CockpitSummary(**data))
```

- [ ] **步骤 5：运行测试确认通过**

运行：`cd backend && python -m pytest tests/test_enterprise_cockpit.py -v`
预期：7 passed（5 个任务 1 + 2 个新增）

再运行全量后端测试：

运行：`cd backend && python -m pytest tests/ -q`
预期：全量通过（既有告警视为噪音）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/schemas/enterprise_cockpit.py backend/app/routers/enterprises.py backend/tests/test_enterprise_cockpit.py
git commit -m "feat(cockpit): enterprise cockpit summary endpoint"
```

---

### 任务 3：前端类型 + cockpitService + 契约测试

**文件：**
- 创建：`frontend/src/types/cockpit.ts`
- 创建：`frontend/src/services/cockpitService.ts`
- 创建：`frontend/src/services/cockpitService.test.ts`

- [ ] **步骤 1：编写失败的测试**

创建 `frontend/src/services/cockpitService.test.ts`（沿用 riskManagementService.test.ts 的 mock 惯例）：

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/services/api", () => ({
  default: { get: vi.fn() },
}));

import api from "@/services/api";
import { getCockpitSummary } from "@/services/cockpitService";
import type { CockpitSummary } from "@/types/cockpit";

const mockedGet = vi.mocked(api.get);

describe("cockpitService", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  it("requests cockpit-summary with the enterprise id", async () => {
    const summary: CockpitSummary = {
      risk_counts: { major: 1, larger: 1, general: 1, low: 1, total: 4 },
      zone_risks: [],
      top_risks: [],
      risk_index: 55,
      hazard_counts: { open: 3, due: 2, overdue: 0 },
      todos: [],
      completion: { percent: 50, modules: [] },
      recent_activities: [],
    };
    mockedGet.mockResolvedValue({ data: { data: summary } });

    const result = await getCockpitSummary("e1");

    expect(mockedGet).toHaveBeenCalledWith("/enterprises/e1/cockpit-summary");
    expect(result).toEqual(summary);
  });
});
```

- [ ] **步骤 2：运行测试确认失败**

运行：`cd frontend && npx vitest run src/services/cockpitService.test.ts`
预期：FAIL，`Cannot find module '@/services/cockpitService'`

- [ ] **步骤 3：实现类型与服务**

创建 `frontend/src/types/cockpit.ts`：

```ts
export interface RiskCounts {
  major: number;
  larger: number;
  general: number;
  low: number;
  total: number;
}

export interface TopRisk {
  name: string;
  level: string;
  score: number | null;
  responsible_unit: string | null;
}

export interface ZoneRisk {
  zone_name: string;
  counts: RiskCounts;
  total: number;
}

export interface CockpitTodo {
  priority: "high" | "medium" | "low";
  title: string;
  note: string;
}

export interface CompletionModule {
  key: string;
  label: string;
  done: boolean;
}

export interface CockpitCompletion {
  percent: number;
  modules: CompletionModule[];
}

export interface ActivityItem {
  actor: string;
  action: string;
  time: string;
}

export interface HazardCounts {
  open: number;
  due: number;
  overdue: number;
}

export interface CockpitSummary {
  risk_counts: RiskCounts;
  zone_risks: ZoneRisk[];
  top_risks: TopRisk[];
  risk_index: number;
  hazard_counts: HazardCounts;
  todos: CockpitTodo[];
  completion: CockpitCompletion;
  recent_activities: ActivityItem[];
}
```

创建 `frontend/src/services/cockpitService.ts`：

```ts
import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { CockpitSummary } from "@/types/cockpit";

export const getCockpitSummary = (enterpriseId: string): Promise<CockpitSummary> =>
  api
    .get<ApiResponse<CockpitSummary>>(`/enterprises/${enterpriseId}/cockpit-summary`)
    .then((r) => r.data.data);
```

- [ ] **步骤 4：运行测试确认通过**

运行：`cd frontend && npx vitest run src/services/cockpitService.test.ts`
预期：1 passed

再运行类型检查：

运行：`cd frontend && npx tsc -b`
预期：exit 0

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/types/cockpit.ts frontend/src/services/cockpitService.ts frontend/src/services/cockpitService.test.ts
git commit -m "feat(cockpit): cockpit summary frontend service"
```

---

### 任务 4：驾驶舱设计系统 CSS + 背景/顶栏/跑马灯

**文件：**
- 创建：`frontend/src/styles/cockpit.css`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitBackground.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitHeader.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitTicker.tsx`

- [ ] **步骤 1：实现设计系统 CSS**

创建 `frontend/src/styles/cockpit.css`：

```css
/* ===== 企业驾驶舱设计系统 ===== */
.cp-page {
  --bg0: #030814; --bg1: #06112a; --bg2: #0a1d3f;
  --panel: linear-gradient(160deg, rgba(19,38,74,.78), rgba(8,18,42,.9));
  --line: rgba(0,212,255,.20); --cyan: #00d4ff; --blue: #2f81f7;
  --text: #eaf2ff; --muted: #8aa3c8;
  --red: #ff4d4f; --orange: #ff9f43; --yellow: #ffd666; --blue2: #40a9ff;
  position: relative; border-radius: 14px; padding: 16px 18px; overflow: hidden;
  background:
    radial-gradient(1200px 500px at 70% -10%, rgba(47,129,247,.28), transparent 60%),
    radial-gradient(900px 420px at 8% 110%, rgba(0,212,255,.14), transparent 55%),
    linear-gradient(155deg, var(--bg1), var(--bg0) 55%, var(--bg2));
  color: var(--text);
  font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
}
.cp-bg { position: absolute; inset: 0; pointer-events: none; overflow: hidden; border-radius: inherit; }
.cp-bg .grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(120,180,255,.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(120,180,255,.045) 1px, transparent 1px);
  background-size: 26px 26px;
}
.cp-bg .aurora { position: absolute; width: 380px; height: 260px; border-radius: 50%; filter: blur(28px);
  background: radial-gradient(circle, rgba(0,212,255,.16), transparent 70%); top: -120px; right: -80px; }
.cp-bg .aurora2 { position: absolute; width: 300px; height: 220px; border-radius: 50%; filter: blur(30px);
  background: radial-gradient(circle, rgba(47,129,247,.22), transparent 70%); bottom: -110px; left: -70px; }
.cp-bg .floor { position: absolute; left: -15%; right: -15%; bottom: -70px; height: 190px; opacity: .55;
  background:
    repeating-linear-gradient(90deg, rgba(0,212,255,.16) 0 1px, transparent 1px 48px),
    repeating-linear-gradient(0deg, rgba(0,212,255,.16) 0 1px, transparent 1px 26px);
  transform: perspective(260px) rotateX(58deg); transform-origin: center bottom;
  -webkit-mask-image: linear-gradient(transparent, #000 55%); mask-image: linear-gradient(transparent, #000 55%); }
.cp-bg .scan { position: absolute; top: -80px; left: 0; right: 0; height: 90px;
  background: linear-gradient(180deg, transparent, rgba(0,212,255,.06), transparent);
  animation: cp-scan 6s linear infinite; }
@keyframes cp-scan { 0% { transform: translateY(0); } 100% { transform: translateY(900px); } }
.cp-bg .stream { position: absolute; top: 0; bottom: 0; width: 9px; opacity: .8;
  background: repeating-linear-gradient(180deg, rgba(0,212,255,.5) 0 2px, transparent 2px 16px);
  animation: cp-stream 1.5s linear infinite;
  -webkit-mask-image: linear-gradient(180deg, transparent, #000 18%, #000 82%, transparent);
  mask-image: linear-gradient(180deg, transparent, #000 18%, #000 82%, transparent); }
@keyframes cp-stream { to { background-position-y: 16px; } }
.cp-bg .part { position: absolute; width: 2.5px; height: 2.5px; border-radius: 50%; background: var(--cyan);
  box-shadow: 0 0 7px var(--cyan); animation: cp-rise linear infinite; }
@keyframes cp-rise {
  0% { transform: translateY(0); opacity: 0; }
  10% { opacity: .9; } 80% { opacity: .4; }
  100% { transform: translateY(-430px); opacity: 0; }
}

.cp-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; position: relative; z-index: 3; margin-bottom: 12px; flex-wrap: wrap; }
.cp-name { font-size: 18px; font-weight: 800; letter-spacing: 1px; }
.cp-sub { font-size: 11px; color: var(--muted); margin-left: 10px; letter-spacing: 0; font-weight: 500; }
.cp-tag { font-size: 10px; padding: 2px 9px; border-radius: 20px; border: 1px solid rgba(0,212,255,.4);
  background: rgba(0,212,255,.07); color: #a8ecff; letter-spacing: .5px; }
.cp-tag.red { border-color: rgba(255,77,79,.5); background: rgba(255,77,79,.10); color: #ff9b9c; }
.cp-btn { font-size: 11px; padding: 5px 14px; border-radius: 6px; font-weight: 700; cursor: pointer;
  background: linear-gradient(90deg, var(--blue), var(--cyan)); color: #04101f;
  box-shadow: 0 0 16px rgba(0,212,255,.45); border: none; letter-spacing: 1px; }
.cp-live { display: inline-flex; align-items: center; gap: 6px; font-size: 10px; color: #7de8a0; letter-spacing: 1px; }
.cp-live i { width: 6px; height: 6px; border-radius: 50%; background: #52e38a; box-shadow: 0 0 8px #52e38a; animation: cp-blink 1.8s ease-in-out infinite; }
@keyframes cp-blink { 0%,100% { opacity: 1; } 50% { opacity: .25; } }

.cp-ticker { position: relative; z-index: 3; overflow: hidden; white-space: nowrap; margin-bottom: 12px;
  border: 1px solid rgba(0,212,255,.18); border-radius: 6px; background: rgba(0,212,255,.04); padding: 5px 0; }
.cp-ticker div { display: inline-block; animation: cp-tick 22s linear infinite; font-size: 10px; color: #9fe8ff; letter-spacing: 1.5px; }
.cp-ticker span { margin: 0 22px; }
.cp-ticker span b { color: var(--text); }
@keyframes cp-tick { from { transform: translateX(0); } to { transform: translateX(-50%); } }

.cp-grid { display: grid; grid-template-columns: 240px 1fr 276px; gap: 12px; position: relative; z-index: 3; }
.cp-col { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.cp-panel { position: relative; border: 1px solid var(--line); border-radius: 10px;
  background: var(--panel); box-shadow: 0 10px 34px rgba(0,0,0,.38), inset 0 1px 0 rgba(255,255,255,.045);
  padding: 12px 13px; overflow: hidden; }
.cp-panel::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent 8%, rgba(0,212,255,.55), transparent 92%); }
.cp-corner { position: absolute; width: 9px; height: 9px; pointer-events: none; }
.cp-corner.tl { top: -1px; left: -1px; border-top: 1.5px solid rgba(0,212,255,.75); border-left: 1.5px solid rgba(0,212,255,.75); }
.cp-corner.tr { top: -1px; right: -1px; border-top: 1.5px solid rgba(0,212,255,.75); border-right: 1.5px solid rgba(0,212,255,.75); }
.cp-corner.bl { bottom: -1px; left: -1px; border-bottom: 1.5px solid rgba(0,212,255,.75); border-left: 1.5px solid rgba(0,212,255,.75); }
.cp-corner.br { bottom: -1px; right: -1px; border-bottom: 1.5px solid rgba(0,212,255,.75); border-right: 1.5px solid rgba(0,212,255,.75); }
.cp-h { display: flex; align-items: center; gap: 8px; font-size: 11px; font-weight: 700; letter-spacing: 2.5px; color: var(--muted); margin-bottom: 10px; }
.cp-h::before { content: ""; width: 14px; height: 2px; border-radius: 1px;
  background: linear-gradient(90deg, var(--cyan), transparent); box-shadow: 0 0 8px rgba(0,212,255,.8); }
.cp-h b { color: var(--text); font-weight: 800; letter-spacing: 1px; }
.cp-h .right { margin-left: auto; font-weight: 400; letter-spacing: 1px; font-size: 9px; color: var(--muted); }

.cp-donut { position: relative; width: 138px; height: 138px; margin: 0 auto 10px; border-radius: 50%;
  filter: drop-shadow(0 0 14px rgba(0,212,255,.22));
  -webkit-mask: radial-gradient(circle, transparent 60%, #000 61%); mask: radial-gradient(circle, transparent 60%, #000 61%); }
.cp-donut-center { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; margin-top: -148px; }
.cp-donut-center b { font-size: 24px; font-weight: 800; font-variant-numeric: tabular-nums;
  background: linear-gradient(180deg, #fff, #8fd6ff); -webkit-background-clip: text; background-clip: text; color: transparent;
  filter: drop-shadow(0 0 8px rgba(0,212,255,.45)); }
.cp-donut-center span { font-size: 9px; color: var(--muted); letter-spacing: 2px; }
.cp-legend { display: flex; flex-direction: column; gap: 5px; }
.cp-lg { display: flex; align-items: center; justify-content: space-between; font-size: 10px; color: var(--muted); letter-spacing: .5px; }
.cp-lg i { width: 7px; height: 7px; border-radius: 2px; margin-right: 6px; display: inline-block; }
.cp-lg b { color: var(--text); font-variant-numeric: tabular-nums; }

.cp-radar { position: relative; width: 264px; height: 264px; margin: 4px auto 0; }
.cp-radar .r { position: absolute; border-radius: 50%; border: 1px solid rgba(0,212,255,.16); }
.cp-radar .r1 { inset: 0; } .cp-radar .r2 { inset: 24px; border-style: dashed; }
.cp-radar .r3 { inset: 52px; } .cp-radar .r4 { inset: 80px; border-color: rgba(0,212,255,.30); }
.cp-radar .x { position: absolute; background: rgba(0,212,255,.14); }
.cp-radar .x.h { left: 0; right: 0; top: 50%; height: 1px; }
.cp-radar .x.v { top: 0; bottom: 0; left: 50%; width: 1px; }
.cp-sweep { position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(from 0deg, rgba(0,212,255,.5), transparent 62deg);
  animation: cp-spin 4.2s linear infinite; }
@keyframes cp-spin { to { transform: rotate(360deg); } }
.cp-orbit { position: absolute; inset: 12px; animation: cp-spin 11s linear infinite; }
.cp-orbit i { position: absolute; top: -3px; left: 50%; width: 6px; height: 6px; margin-left: -3px; border-radius: 50%;
  background: var(--cyan); box-shadow: 0 0 10px var(--cyan); }
.cp-orbit.o2 { inset: 44px; animation: cp-spin 8s linear infinite reverse; }
.cp-orbit.o2 i { background: #fff; box-shadow: 0 0 10px #fff; width: 4px; height: 4px; margin-left: -2px; }
.cp-riskdot { position: absolute; width: 8px; height: 8px; border-radius: 50%; animation: cp-pulse 2s ease-in-out infinite; }
.cp-riskdot::after { content: ""; position: absolute; inset: -4px; border-radius: 50%; border: 1px solid currentColor; opacity: .4; }
@keyframes cp-pulse { 0%,100% { transform: scale(1); opacity: .9; } 50% { transform: scale(1.5); opacity: .5; } }
.cp-radar-center { position: absolute; inset: 88px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px;
  background: radial-gradient(circle, rgba(0,212,255,.10), transparent 70%); border: 1px solid rgba(0,212,255,.30);
  box-shadow: 0 0 24px rgba(0,212,255,.22), inset 0 0 18px rgba(0,212,255,.10); }
.cp-radar-center b { font-size: 21px; font-weight: 800; font-variant-numeric: tabular-nums;
  background: linear-gradient(180deg, #fff, #8fd6ff); -webkit-background-clip: text; background-clip: text; color: transparent;
  filter: drop-shadow(0 0 8px rgba(0,212,255,.5)); }
.cp-radar-center span { font-size: 8.5px; color: var(--muted); letter-spacing: 2px; }
.cp-radar-cap { text-align: center; font-size: 9.5px; color: var(--muted); letter-spacing: 2px; margin-top: 2px; }
.cp-radar-cap b { color: var(--cyan); }

.cp-bars { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.cp-bar-row { display: grid; grid-template-columns: 64px 1fr 30px; align-items: center; gap: 8px; font-size: 10px; }
.cp-bar-row .nm { color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cp-bar-row .tot { color: var(--text); text-align: right; font-variant-numeric: tabular-nums; }
.cp-bar { display: flex; height: 7px; border-radius: 2px; overflow: hidden; gap: 2px; background: rgba(255,255,255,.05); }
.cp-bar i { display: block; height: 100%; border-radius: 1px; }

.cp-todo { display: flex; gap: 9px; padding: 7px 9px; border-radius: 7px; margin-bottom: 6px; align-items: flex-start;
  background: rgba(255,255,255,.035); border: 1px solid rgba(255,255,255,.05); font-size: 10.5px; line-height: 1.5; }
.cp-todo .lv { width: 3px; align-self: stretch; border-radius: 2px; flex-shrink: 0; }
.cp-todo b { display: block; color: var(--text); font-weight: 600; }
.cp-todo span { color: var(--muted); font-size: 9.5px; }

.cp-ringwrap { display: flex; align-items: center; gap: 14px; }
.cp-ring { position: relative; width: 96px; height: 96px; flex-shrink: 0; border-radius: 50%;
  background: conic-gradient(var(--cyan) 0 78%, rgba(255,255,255,.07) 78% 100%);
  -webkit-mask: radial-gradient(circle, transparent 66%, #000 67%); mask: radial-gradient(circle, transparent 66%, #000 67%);
  filter: drop-shadow(0 0 10px rgba(0,212,255,.35)); }
.cp-ring b { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 800;
  font-variant-numeric: tabular-nums; background: linear-gradient(180deg, #fff, #8fd6ff);
  -webkit-background-clip: text; background-clip: text; color: transparent; }
.cp-modules { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; flex: 1; }
.cp-mod { font-size: 9.5px; display: flex; justify-content: space-between; padding: 4px 7px; border-radius: 5px;
  background: rgba(0,212,255,.05); border: 1px solid rgba(0,212,255,.10); color: var(--muted); }
.cp-mod b { color: var(--cyan); }
.cp-mod b.warn { color: var(--yellow); }
.cp-mod b.bad { color: var(--red); }

.cp-feed { display: flex; flex-direction: column; gap: 7px; }
.cp-feed .it { display: flex; gap: 8px; font-size: 10px; color: var(--muted); line-height: 1.5; }
.cp-feed .it .tm { color: #5e7ea8; flex-shrink: 0; font-variant-numeric: tabular-nums; }
.cp-feed .dot { width: 5px; height: 5px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; background: var(--cyan); box-shadow: 0 0 6px var(--cyan); }
.cp-feed b { color: var(--text); font-weight: 600; }

.cp-nav { display: grid; grid-template-columns: repeat(10, 1fr); gap: 9px; margin-top: 12px; position: relative; z-index: 3; }
.cp-nav .it { position: relative; display: flex; flex-direction: column; align-items: center; gap: 7px; padding: 13px 4px 10px; cursor: pointer;
  border-radius: 10px; border: 1px solid rgba(0,212,255,.14); background: var(--panel);
  box-shadow: 0 8px 24px rgba(0,0,0,.3), inset 0 1px 0 rgba(255,255,255,.04); transition: all .22s; }
.cp-nav .it::before { content: ""; position: absolute; top: 0; left: 18%; right: 18%; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0,212,255,.6), transparent); opacity: .5; transition: opacity .22s; }
.cp-nav .it:hover { transform: translateY(-4px); border-color: rgba(0,212,255,.55);
  box-shadow: 0 0 22px rgba(0,212,255,.28), 0 10px 28px rgba(0,0,0,.35); }
.cp-nav .it:hover::before { opacity: 1; }
.cp-nav .it:hover svg { filter: drop-shadow(0 0 8px rgba(0,212,255,.8)); }
.cp-nav .lb { font-size: 10.5px; color: var(--text); font-weight: 600; letter-spacing: .5px; }
.cp-nav .sb { font-size: 8px; color: var(--muted); letter-spacing: 1px; }
.cp-nav svg { width: 26px; height: 26px; stroke: url(#cp-grad); filter: drop-shadow(0 0 5px rgba(0,212,255,.45)); }
.cp-nav .it.hot { border-color: rgba(255,77,79,.4); }
.cp-nav .it.hot .badge { position: absolute; top: 6px; right: 8px; width: 6px; height: 6px; border-radius: 50%; background: var(--red);
  box-shadow: 0 0 8px var(--red); animation: cp-blink 1.6s infinite; }

.cp-empty { color: var(--muted); font-size: 10.5px; text-align: center; padding: 16px 0; letter-spacing: 1px; }
.cp-error { color: #ff9b9c; font-size: 12px; text-align: center; padding: 48px 16px; }

@media (max-width: 1240px) {
  .cp-grid { grid-template-columns: 1fr 1fr; }
  .cp-nav { grid-template-columns: repeat(5, 1fr); }
}
@media (max-width: 860px) {
  .cp-grid { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  .cp-bg .scan, .cp-bg .stream, .cp-bg .part, .cp-sweep, .cp-orbit, .cp-riskdot,
  .cp-ticker div, .cp-live i, .cp-nav .it.hot .badge { animation: none !important; }
}
```

- [ ] **步骤 2：实现背景/顶栏/跑马灯组件**

创建 `CockpitBackground.tsx`：

```tsx
const PARTICLES = [
  { left: "6%", bottom: 150, duration: 8, delay: 0 },
  { left: "18%", bottom: 90, duration: 10, delay: 1.2 },
  { left: "31%", bottom: 170, duration: 7, delay: 2 },
  { left: "47%", bottom: 110, duration: 9, delay: 0.6 },
  { left: "63%", bottom: 160, duration: 8.4, delay: 1.8 },
  { left: "78%", bottom: 100, duration: 7.6, delay: 0.9 },
  { left: "92%", bottom: 180, duration: 9.6, delay: 2.6 },
];

export default function CockpitBackground() {
  return (
    <div className="cp-bg" aria-hidden>
      <div className="grid" />
      <div className="aurora" />
      <div className="aurora2" />
      <div className="floor" />
      <div className="scan" />
      <div className="stream" style={{ left: 10 }} />
      <div className="stream" style={{ right: 10, animationDelay: "0.7s" }} />
      {PARTICLES.map((p, i) => (
        <div
          key={i}
          className="part"
          style={{ left: p.left, bottom: p.bottom, animationDuration: `${p.duration}s`, animationDelay: `${p.delay}s` }}
        />
      ))}
    </div>
  );
}
```

创建 `CockpitHeader.tsx`：

```tsx
import { Button } from "antd";

interface Props {
  name: string;
  industry?: string;
  majorCount?: number;
  onBack: () => void;
  onEdit: () => void;
}

export default function CockpitHeader({ name, industry, majorCount, onBack, onEdit }: Props) {
  return (
    <div className="cp-top">
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <Button type="text" size="small" onClick={onBack} style={{ color: "#00d4ff", paddingLeft: 0 }}>
          ← 返回
        </Button>
        <span className="cp-name">
          {name} <small className="cp-sub">Enterprise Cockpit · 企业驾驶舱</small>
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
        <span className="cp-live"><i />系统运行正常</span>
        {industry && <span className="cp-tag">{industry}</span>}
        {typeof majorCount === "number" && majorCount > 0 && (
          <span className="cp-tag red">重大风险 {majorCount}</span>
        )}
        <button type="button" className="cp-btn" onClick={onEdit}>编辑企业</button>
      </div>
    </div>
  );
}
```

创建 `CockpitTicker.tsx`：

```tsx
interface Props {
  items: string[];
}

export default function CockpitTicker({ items }: Props) {
  const inner = (
    <>
      {items.map((it, i) => (
        <span key={i}>{it}</span>
      ))}
    </>
  );
  return (
    <div className="cp-ticker">
      <div>
        {inner}
        {inner}
      </div>
    </div>
  );
}
```

- [ ] **步骤 3：验证**

运行：`cd frontend && npx tsc -b`
预期：exit 0（组件尚无调用方，仅类型检查）

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/styles/cockpit.css frontend/src/components/enterprise/cockpit/CockpitBackground.tsx frontend/src/components/enterprise/cockpit/CockpitHeader.tsx frontend/src/components/enterprise/cockpit/CockpitTicker.tsx
git commit -m "feat(cockpit): cockpit design system css, background, header, ticker"
```

---

### 任务 5：驾驶舱数据面板组件

**文件：**
- 修改：`frontend/src/types/cockpit.ts`（追加 RISK_LEVEL_COLORS 常量）
- 创建：`frontend/src/components/enterprise/cockpit/RiskDonutPanel.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/RiskRadarPanel.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitTodoPanel.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitCompletionPanel.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/CockpitActivityPanel.tsx`

- [ ] **步骤 1：追加共享常量**

在 `frontend/src/types/cockpit.ts` 末尾追加：

```ts
export const RISK_LEVEL_COLORS: Record<string, string> = {
  major: "#ff4d4f",
  larger: "#ff9f43",
  general: "#ffd666",
  low: "#40a9ff",
};

export const RISK_LEVEL_LABELS: Record<string, string> = {
  major: "重大",
  larger: "较大",
  general: "一般",
  low: "低",
};
```

- [ ] **步骤 2：实现环形图 + 重大风险 TOP 面板**

创建 `RiskDonutPanel.tsx`：

```tsx
import type { RiskCounts, TopRisk } from "@/types/cockpit";
import { RISK_LEVEL_COLORS, RISK_LEVEL_LABELS } from "@/types/cockpit";

const ORDER: Array<keyof RiskCounts> = ["major", "larger", "general", "low"];

function donutBackground(counts: RiskCounts): string {
  if (counts.total <= 0) return "rgba(255,255,255,.06)";
  let cursor = 0;
  const stops = ORDER.map((key) => {
    const pct = (counts[key] / counts.total) * 100;
    const start = cursor;
    cursor += pct;
    return `${RISK_LEVEL_COLORS[key]} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(", ")})`;
}

interface Props {
  counts: RiskCounts;
  topRisks: TopRisk[];
}

export default function RiskDonutPanel({ counts, topRisks }: Props) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">风险等级分布</div>
      <div className="cp-donut" style={{ background: donutBackground(counts) }} />
      <div className="cp-donut-center">
        <b>{counts.total > 0 ? counts.total : "--"}</b>
        <span>风险事件</span>
      </div>
      <div className="cp-legend">
        {ORDER.map((key) => (
          <div className="cp-lg" key={key}>
            <span><i style={{ background: RISK_LEVEL_COLORS[key] }} />{RISK_LEVEL_LABELS[key]}</span>
            <b>{counts[key]}</b>
          </div>
        ))}
      </div>
      <div className="cp-h" style={{ marginTop: 14 }}>重大风险 TOP</div>
      {topRisks.length === 0 ? (
        <div className="cp-empty">暂无高风险数据</div>
      ) : (
        topRisks.slice(0, 3).map((r) => (
          <div className="cp-todo" style={{ marginBottom: 0 }} key={r.name}>
            <span className="lv" style={{ background: RISK_LEVEL_COLORS[r.level] || "#8aa3c8" }} />
            <div>
              <b>{r.name}</b>
              <span>综合得分 {r.score ?? "--"} · {r.responsible_unit ?? "未指定责任单位"}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
```

- [ ] **步骤 3：实现风险雷达 + 分区分布面板**

创建 `RiskRadarPanel.tsx`：

```tsx
import type { ZoneRisk } from "@/types/cockpit";
import { RISK_LEVEL_COLORS } from "@/types/cockpit";

const DOTS = [
  { top: "34%", left: "62%", color: "#ff4d4f", delay: 0 },
  { top: "58%", left: "32%", color: "#ff9f43", delay: 0.5 },
  { top: "24%", left: "40%", color: "#ffd666", delay: 1 },
  { top: "66%", left: "58%", color: "#40a9ff", delay: 1.4 },
  { top: "48%", left: "74%", color: "#ff9f43", delay: 0.8 },
];

interface Props {
  riskIndex: number;
  zoneRisks: ZoneRisk[];
}

const LEVEL_ORDER = ["major", "larger", "general", "low"] as const;

export default function RiskRadarPanel({ riskIndex, zoneRisks }: Props) {
  return (
    <div className="cp-panel" style={{ flex: 1 }}>
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h" style={{ justifyContent: "space-between" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>风险雷达 <b>LIVE</b></span>
        <span className="right">扫描中 · 每 4.2s 刷新</span>
      </div>
      <div className="cp-radar">
        <div className="r r1" /><div className="r r2" /><div className="r r3" /><div className="r r4" />
        <div className="x h" /><div className="x v" />
        <div className="cp-sweep" />
        <div className="cp-orbit"><i /></div>
        <div className="cp-orbit o2"><i /></div>
        {DOTS.map((d, i) => (
          <div
            key={i}
            className="cp-riskdot"
            style={{ top: d.top, left: d.left, background: d.color, color: d.color, boxShadow: `0 0 12px ${d.color}`, animationDelay: `${d.delay}s` }}
          />
        ))}
        <div className="cp-radar-center">
          <b>{riskIndex > 0 ? riskIndex : "--"}</b>
          <span>综合风险指数</span>
        </div>
      </div>
      <div className="cp-radar-cap">风险点实时定位 · 圆心为风险指数 <b>{riskIndex} / 100</b></div>
      <div className="cp-h" style={{ marginTop: 12 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>分区风险分布</span>
        <span className="right">按管控区域</span>
      </div>
      <div className="cp-bars">
        {zoneRisks.length === 0 ? (
          <div className="cp-empty">暂无分区数据</div>
        ) : (
          zoneRisks.slice(0, 4).map((z) => (
            <div className="cp-bar-row" key={z.zone_name}>
              <span className="nm">{z.zone_name}</span>
              <div className="cp-bar">
                {LEVEL_ORDER.map((k) =>
                  z.counts[k] > 0 ? (
                    <i key={k} style={{ width: `${(z.counts[k] / z.total) * 100}%`, background: RISK_LEVEL_COLORS[k] }} />
                  ) : null,
                )}
              </div>
              <span className="tot">{z.total}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **步骤 4：实现待办 / 完成度 / 动态面板**

创建 `CockpitTodoPanel.tsx`：

```tsx
import type { CockpitTodo } from "@/types/cockpit";

const PRIORITY_COLORS: Record<string, string> = { high: "#ff4d4f", medium: "#ff9f43", low: "#2f81f7" };

export default function CockpitTodoPanel({ todos }: { todos: CockpitTodo[] }) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">待办提醒 <b style={{ color: "#ff9f43" }}>{todos.length}</b></div>
      {todos.length === 0 ? (
        <div className="cp-empty">暂无待办事项</div>
      ) : (
        todos.map((t) => (
          <div className="cp-todo" key={t.title}>
            <span className="lv" style={{ background: PRIORITY_COLORS[t.priority] || "#2f81f7" }} />
            <div><b>{t.title}</b><span>{t.note}</span></div>
          </div>
        ))
      )}
    </div>
  );
}
```

创建 `CockpitCompletionPanel.tsx`：

```tsx
import type { CockpitCompletion } from "@/types/cockpit";

export default function CockpitCompletionPanel({ completion }: { completion: CockpitCompletion }) {
  const percent = completion.percent ?? 0;
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">数据完成度</div>
      <div className="cp-ringwrap">
        <div className="cp-ring" style={{ background: `conic-gradient(#00d4ff 0 ${percent}%, rgba(255,255,255,.07) ${percent}% 100%)` }}>
          <b>{percent > 0 ? `${percent}%` : "--"}</b>
        </div>
        <div className="cp-modules">
          {completion.modules.length === 0 ? (
            <div className="cp-empty">暂无数据</div>
          ) : (
            completion.modules.map((m) => (
              <div className="cp-mod" key={m.key}>
                {m.label}
                {m.done ? <b>✓</b> : <b className="warn">…</b>}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
```

创建 `CockpitActivityPanel.tsx`：

```tsx
import type { ActivityItem } from "@/types/cockpit";

function formatTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function CockpitActivityPanel({ activities }: { activities: ActivityItem[] }) {
  return (
    <div className="cp-panel">
      <i className="cp-corner tl" /><i className="cp-corner tr" />
      <i className="cp-corner bl" /><i className="cp-corner br" />
      <div className="cp-h">最近动态</div>
      <div className="cp-feed">
        {activities.length === 0 ? (
          <div className="cp-empty">暂无动态</div>
        ) : (
          activities.slice(0, 3).map((a, i) => (
            <div className="it" key={i}>
              <span className="dot" />
              <span><b>{a.actor}</b> {a.action}</span>
              <span className="tm">{formatTime(a.time)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **步骤 5：验证**

运行：`cd frontend && npx tsc -b && npx eslint src/components/enterprise/cockpit src/types/cockpit.ts`
预期：exit 0

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/types/cockpit.ts frontend/src/components/enterprise/cockpit/RiskDonutPanel.tsx frontend/src/components/enterprise/cockpit/RiskRadarPanel.tsx frontend/src/components/enterprise/cockpit/CockpitTodoPanel.tsx frontend/src/components/enterprise/cockpit/CockpitCompletionPanel.tsx frontend/src/components/enterprise/cockpit/CockpitActivityPanel.tsx
git commit -m "feat(cockpit): cockpit data panels (donut, radar, todo, completion, activity)"
```

---

### 任务 6：模块导航 + 驾驶舱主页面组装

**文件：**
- 创建：`frontend/src/components/enterprise/cockpit/ModuleNav.tsx`
- 创建：`frontend/src/pages/Enterprise/EnterpriseCockpitPage.tsx`

- [ ] **步骤 1：实现模块导航（内联 SVG 图标）**

创建 `ModuleNav.tsx`：

```tsx
import { useNavigate } from "react-router-dom";

interface ModuleItem {
  key: string;
  label: string;
  en: string;
  to: (id: string) => string;
  hot?: boolean;
  icon: React.ReactNode;
}

const stroke = { fill: "none", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

const MODULES: ModuleItem[] = [
  {
    key: "info", label: "基本信息", en: "ARCHIVE", to: (id) => `/enterprises/${id}/modules/info`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><rect x="3" y="4" width="14" height="17" rx="1.5" /><path d="M3 9l7-4 7 4M8 21v-4.5h4V21M7 13h.01M10 13h.01M13 13h.01M7 16.5h.01M10 16.5h.01" /></svg>,
  },
  {
    key: "org", label: "组织架构", en: "ORG", to: (id) => `/enterprises/${id}/org`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><circle cx="5.5" cy="6.5" r="2" /><circle cx="18.5" cy="6.5" r="2" /><circle cx="12" cy="17.5" r="2" /><path d="M7 8l4.2 7.4M17 8l-4.2 7.4M7.5 6.5h9" /></svg>,
  },
  {
    key: "geo", label: "周边环境", en: "GEO", to: (id) => `/enterprises/${id}/modules/surrounding`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><circle cx="12" cy="12" r="8" /><path d="M12 4.5c3.8 2.6 3.8 12.4 0 15M12 4.5c-3.8 2.6-3.8 12.4 0 15M4.5 12h15" /></svg>,
  },
  {
    key: "chem", label: "危险化学品", en: "CHEM", to: (id) => `/enterprises/${id}/modules/chemicals`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M10 2.5v5.1a2 2 0 0 1-.21.9L4.72 18.6a1 1 0 0 0 .9 1.4h12.76a1 1 0 0 0 .9-1.4l-5.07-10.1a2 2 0 0 1-.21-.9V2.5" /><path d="M8.5 2.5h7M7 15.5h10" /></svg>,
  },
  {
    key: "risk", label: "风险管控", en: "RISK", hot: true, to: (id) => `/enterprises/${id}/risk-management`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M12 2.8 19 5.6v4.9c0 4.5-3 8-7 10-4-2-7-5.5-7-10V5.6z" /><path d="M12 8.5v3.5M12 15.2h.01" /></svg>,
  },
  {
    key: "hazard", label: "隐患治理", en: "HAZARD", hot: true, to: (id) => `/enterprises/${id}/hazard`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><circle cx="11" cy="11" r="6.5" /><path d="M20.5 20.5 16 16M11 7.5v3.5M8 11h6" /></svg>,
  },
  {
    key: "rescue", label: "应急资源", en: "RESCUE", to: (id) => `/enterprises/${id}/modules/resources`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M3 6.5h12v8H3zM15 10h3.2L21 12.7V14.5h-6z" /><circle cx="7" cy="17.5" r="1.7" /><circle cx="17" cy="17.5" r="1.7" /></svg>,
  },
  {
    key: "assessment", label: "风险评估", en: "REPORT", to: (id) => `/enterprises/${id}/modules/assessment`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M4 19.5v-6M9.5 19.5V9.5M15 19.5v-8M20.5 19.5V5" /><path d="M3 19.5h18.5" /></svg>,
  },
  {
    key: "investigation", label: "资源调查", en: "SURVEY", to: (id) => `/enterprises/${id}/modules/investigation`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><rect x="5" y="3.5" width="14" height="17.5" rx="2" /><path d="M9 8.5h6M9 12.5h6M9 16.5h4M12 3.5v-1" /></svg>,
  },
  {
    key: "plan", label: "预案管理", en: "PLAN", to: (id) => `/enterprises/${id}/plans`,
    icon: <svg viewBox="0 0 24 24" {...stroke}><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9.5 12h5M9.5 16h5" /></svg>,
  },
];

export default function ModuleNav({ enterpriseId }: { enterpriseId: string }) {
  const navigate = useNavigate();
  return (
    <div className="cp-nav">
      {MODULES.map((m) => (
        <div
          key={m.key}
          className={`it${m.hot ? " hot" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => navigate(m.to(enterpriseId))}
          onKeyDown={(e) => e.key === "Enter" && navigate(m.to(enterpriseId))}
        >
          {m.hot && <span className="badge" />}
          {m.icon}
          <span className="lb">{m.label}</span>
          <span className="sb">{m.en}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **步骤 2：实现驾驶舱主页面**

创建 `EnterpriseCockpitPage.tsx`：

```tsx
import { useParams, useNavigate } from "react-router-dom";
import { Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { getEnterprise } from "@/services/enterpriseService";
import { getCockpitSummary } from "@/services/cockpitService";
import CockpitBackground from "@/components/enterprise/cockpit/CockpitBackground";
import CockpitHeader from "@/components/enterprise/cockpit/CockpitHeader";
import CockpitTicker from "@/components/enterprise/cockpit/CockpitTicker";
import RiskDonutPanel from "@/components/enterprise/cockpit/RiskDonutPanel";
import RiskRadarPanel from "@/components/enterprise/cockpit/RiskRadarPanel";
import CockpitTodoPanel from "@/components/enterprise/cockpit/CockpitTodoPanel";
import CockpitCompletionPanel from "@/components/enterprise/cockpit/CockpitCompletionPanel";
import CockpitActivityPanel from "@/components/enterprise/cockpit/CockpitActivityPanel";
import ModuleNav from "@/components/enterprise/cockpit/ModuleNav";
import "@/styles/cockpit.css";

function buildTickerItems(summary: NonNullable<ReturnType<typeof getCockpitSummary> extends Promise<infer T> ? T : never>, resources: number, plans: number): string[] {
  const c = summary.risk_counts;
  return [
    `风险事件 ${c.total}`, `重大 ${c.major}`, `较大 ${c.larger}`, `一般 ${c.general}`, `低 ${c.low}`,
    `待整改隐患 ${summary.hazard_counts.open}`, `应急资源 ${resources}`, `预案 ${plans}`,
    `数据完成度 ${summary.completion.percent}%`,
  ];
}

export default function EnterpriseCockpitPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const enterpriseQ = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });
  const summaryQ = useQuery({
    queryKey: ["cockpit-summary", id],
    queryFn: () => getCockpitSummary(id!),
    enabled: !!id,
  });

  if (enterpriseQ.isLoading || summaryQ.isLoading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: 80 }}><Spin size="large" /></div>;
  }
  if (enterpriseQ.isError || !enterpriseQ.data || summaryQ.isError || !summaryQ.data) {
    return (
      <div className="cp-page" style={{ padding: 80 }}>
        <div className="cp-error">
          驾驶舱数据加载失败
          <button className="cp-btn" style={{ marginLeft: 12 }} onClick={() => { enterpriseQ.refetch(); summaryQ.refetch(); }}>
            重试
          </button>
        </div>
      </div>
    );
  }

  const ent = enterpriseQ.data;
  const summary = summaryQ.data;
  const ticker = buildTickerItems(summary, ent.resources_count ?? 0, ent.plans_count ?? 0);

  return (
    <div className="cp-page">
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
        <defs>
          <linearGradient id="cp-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#4da8ff" />
            <stop offset="1" stopColor="#00d4ff" />
          </linearGradient>
        </defs>
      </svg>
      <CockpitBackground />
      <CockpitHeader
        name={ent.name}
        industry={ent.industry}
        majorCount={summary.risk_counts.major}
        onBack={() => navigate("/enterprises")}
        onEdit={() => navigate(`/enterprises/${id}/edit`)}
      />
      <CockpitTicker items={ticker} />
      <div className="cp-grid">
        <div className="cp-col">
          <RiskDonutPanel counts={summary.risk_counts} topRisks={summary.top_risks} />
        </div>
        <div className="cp-col">
          <RiskRadarPanel riskIndex={summary.risk_index} zoneRisks={summary.zone_risks} />
        </div>
        <div className="cp-col">
          <CockpitTodoPanel todos={summary.todos} />
          <CockpitCompletionPanel completion={summary.completion} />
          <CockpitActivityPanel activities={summary.recent_activities} />
        </div>
      </div>
      <ModuleNav enterpriseId={id!} />
    </div>
  );
}
```

> 说明：`buildTickerItems` 引用 `summary.hazard_counts.open`，对应任务 1/2/3 中追加的 `hazard_counts` 字段（见任务 9 前的小修订）；`Enterprise` 类型需含 `resources_count`/`plans_count`（现有类型已含）。

- [ ] **步骤 3：验证**

运行：`cd frontend && npx tsc -b && npx eslint src/pages/Enterprise/EnterpriseCockpitPage.tsx src/components/enterprise/cockpit/ModuleNav.tsx`
预期：exit 0（页面尚未挂路由，先通过类型与 lint）

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/enterprise/cockpit/ModuleNav.tsx frontend/src/pages/Enterprise/EnterpriseCockpitPage.tsx
git commit -m "feat(cockpit): module nav and cockpit page assembly"
```

---

### 任务 7：模块页外壳 + 左竖导航 + 现有 Tab 组件嵌入改造

**文件：**
- 创建：`frontend/src/components/enterprise/cockpit/ModulePageShell.tsx`
- 创建：`frontend/src/components/enterprise/cockpit/ModuleSideNav.tsx`
- 创建：`frontend/src/pages/Enterprise/enterpriseNavConfig.ts`
- 创建：`frontend/src/pages/Enterprise/EnterpriseModulePage.tsx`
- 修改：`frontend/src/pages/Enterprise/RiskManagementTab.tsx`
- 修改：`frontend/src/pages/Hazard/HazardInspectionTab.tsx`

- [ ] **步骤 1：实现外壳与左竖导航**

创建 `ModuleSideNav.tsx`：

```tsx
import { useLocation, useNavigate } from "react-router-dom";

export interface SideNavItem {
  key: string;
  label: string;
  to: string;
  matchSearch?: string;
}

export interface SideNavGroup {
  label: string;
  items: SideNavItem[];
}

export default function ModuleSideNav({ groups }: { groups: SideNavGroup[] }) {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <div
      style={{
        width: 170, flexShrink: 0, background: "#fff", border: "1px solid #e5e9f0",
        borderRadius: 8, padding: "8px 0", alignSelf: "flex-start",
      }}
    >
      {groups.map((g) => (
        <div key={g.label}>
          <div style={{ fontSize: 10, color: "#9aa4b4", padding: "8px 12px 3px", letterSpacing: 1 }}>{g.label}</div>
          {g.items.map((it) => {
            const active = it.matchSearch
              ? location.search.includes(it.matchSearch)
              : location.pathname === it.to;
            return (
              <div
                key={it.key}
                role="button"
                tabIndex={0}
                onClick={() => navigate(it.to)}
                onKeyDown={(e) => e.key === "Enter" && navigate(it.to)}
                style={{
                  fontSize: 12, padding: "7px 12px", cursor: "pointer",
                  color: active ? "#1677ff" : "#5a6a80",
                  background: active ? "#e6f0ff" : "transparent",
                  borderRight: active ? "2px solid #1677ff" : "2px solid transparent",
                  fontWeight: active ? 600 : 400,
                }}
              >
                {it.label}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
```

创建 `ModulePageShell.tsx`：

```tsx
import { useNavigate, useParams, Outlet } from "react-router-dom";
import { Button } from "antd";
import ModuleSideNav, { type SideNavGroup } from "./ModuleSideNav";

interface Props {
  title: string;
  en?: string;
  groups?: (id: string) => SideNavGroup[];
}

export default function ModulePageShell({ title, en, groups }: Props) {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const navGroups = groups?.(id ?? "");
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Button type="link" onClick={() => navigate(`/enterprises/${id}`)}>← 返回企业驾驶舱</Button>
          <span style={{ fontSize: 16, fontWeight: 700 }}>{title}</span>
          {en && <span style={{ fontSize: 9, color: "#8a94a6", letterSpacing: 2 }}>{en}</span>}
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        {navGroups && <ModuleSideNav groups={navGroups} />}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Outlet />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **步骤 2：实现导航分组配置**

创建 `enterpriseNavConfig.ts`：

```ts
import type { SideNavGroup } from "@/components/enterprise/cockpit/ModuleSideNav";

export function riskNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "数据编辑",
      items: [
        { key: "tree", label: "风险树编辑", to: `/enterprises/${id}/risk-management` },
        { key: "floors", label: "楼层平面图", to: `/enterprises/${id}/risk-management?floor=1`, matchSearch: "floor=1" },
        { key: "methods", label: "评估方法", to: `/enterprises/${id}/risk-management/methods` },
        { key: "dicts", label: "风险与隐患配置", to: `/enterprises/${id}/risk-management/data-dicts` },
      ],
    },
    {
      label: "成果输出",
      items: [
        { key: "overview", label: "可视化总览", to: `/enterprises/${id}/risk-management/overview` },
        { key: "workbench", label: "四色图工作台", to: `/enterprises/${id}/risk-management/workbench` },
        { key: "list", label: "管控清单", to: `/enterprises/${id}/risk-management/control-list` },
        { key: "cards", label: "风险告知卡", to: `/enterprises/${id}/risk-management/notice-cards` },
        { key: "publicity", label: "风险公示", to: `/enterprises/${id}/risk-management/publicity` },
      ],
    },
  ];
}

export function hazardNavGroups(id: string): SideNavGroup[] {
  return [
    {
      label: "排查管理",
      items: [
        { key: "ledger", label: "隐患台账", to: `/enterprises/${id}/hazard` },
        { key: "plans", label: "排查计划", to: `/enterprises/${id}/hazard/plans` },
        { key: "tasks", label: "排查任务", to: `/enterprises/${id}/hazard/tasks` },
        { key: "templates", label: "排查模板", to: `/enterprises/${id}/hazard/templates` },
      ],
    },
    {
      label: "分析公示",
      items: [
        { key: "dashboard", label: "隐患看板", to: `/enterprises/${id}/hazard/dashboard` },
        { key: "publicity", label: "隐患公示", to: `/enterprises/${id}/hazard/publicity` },
      ],
    },
  ];
}
```

- [ ] **步骤 3：改造 RiskManagementTab（embedded + floor 参数）**

`frontend/src/pages/Enterprise/RiskManagementTab.tsx` 三处修改：

1. Props 增加可选字段并读取楼层参数：

```tsx
import { useSearchParams } from "react-router-dom";

interface Props {
  enterpriseId: string;
  floorPlanUrl?: string | null;
  embedded?: boolean;
}
```

组件内（`const [form, setForm] = useState...` 附近）追加：

```tsx
const [searchParams] = useSearchParams();
useEffect(() => {
  if (searchParams.get("floor") === "1") setFloorDrawerOpen(true);
}, [searchParams]);
```

（`useEffect` 需从 `react` 导入，当前文件已导入 `useState, useCallback, useMemo`，追加 `useEffect`。）

2. 顶部按钮区（约 349-361 行）：把「可视化总览 / 四色分布图工作台 / 管控清单 / 重大风险公示 / 风险告知卡 / 评估方法 / 风险与隐患配置 / 组织与人员」8 个按钮包进条件渲染，保留「添加分区 / 智能导引 / 楼层管理」：

```tsx
<Button icon={<PlusOutlined />} onClick={() => setForm({ type: "zone", open: true })}>添加分区</Button>
<Button icon={<ThunderboltOutlined />} onClick={() => setSmartGuideOpen(true)}>🚀 智能导引</Button>
<Button icon={<ApartmentOutlined />} onClick={() => setFloorDrawerOpen(true)}>楼层管理</Button>
{!embedded && (
  <>
    <Button icon={<BarChartOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-overview`)}>📊 可视化总览</Button>
    <Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-mapping-workbench`)}>四色分布图工作台</Button>
    <Button icon={<UnorderedListOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-control-list`)}>管控清单</Button>
    <Button icon={<NotificationOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-publicity`)}>重大风险公示</Button>
    <Button icon={<ApartmentOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-notice-cards`)}>风险告知卡</Button>
    <Button icon={<SettingOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/risk-methods`)}>⚙ 评估方法</Button>
    <Button icon={<SettingOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/data-dicts`)}>风险与隐患配置</Button>
    <Button icon={<ApartmentOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/org`)}>组织与人员</Button>
  </>
)}
```

3. `FloorManagementDrawer` 与 `RiskMigrationWizard`、表单弹窗保持不变。

- [ ] **步骤 4：改造 HazardInspectionTab（embedded）**

`frontend/src/pages/Hazard/HazardInspectionTab.tsx` 两处修改：

1. Props 增加可选字段：

```tsx
interface Props {
  enterpriseId: string;
  embedded?: boolean;
}
```

2. 按钮区（约 281-299 行）：保留「新增记录 / 导出」，把 5 个导航按钮包进条件渲染：

```tsx
<Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>新增记录</Button>
<Button icon={<DownloadOutlined />} loading={exporting} onClick={handleExport}>导出台账</Button>
{!embedded && (
  <>
    <Button icon={<ScheduleOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/plans`)}>排查计划</Button>
    <Button icon={<CheckSquareOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/tasks`)}>排查任务</Button>
    <Button icon={<FileTextOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/templates`)}>排查模板</Button>
    <Button icon={<DashboardOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/dashboard`)}>隐患看板</Button>
    <Button icon={<EyeOutlined />} onClick={() => navigate(`/enterprises/${enterpriseId}/hazard/publicity`)}>隐患公示</Button>
  </>
)}
```

- [ ] **步骤 5：实现简单模块通用包装页**

创建 `EnterpriseModulePage.tsx`：

```tsx
import { useParams } from "react-router-dom";
import { Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/PageHeader";
import { getEnterprise } from "@/services/enterpriseService";
import EnterpriseInfoCards from "@/components/enterprise/EnterpriseInfoCards";
import SurroundingInfoPanel from "@/components/enterprise/SurroundingInfoPanel";
import HazardousChemicalsTab from "@/pages/Enterprise/HazardousChemicalsTab";
import EmergencyResourceForm from "@/components/enterprise/EmergencyResourceForm";
import RiskAssessmentTab from "@/pages/Enterprise/RiskAssessmentTab";
import ResourceInvestigationTab from "@/pages/Enterprise/ResourceInvestigationTab";
import { useNavigate } from "react-router-dom";
import { Button } from "antd";
import { EditOutlined } from "@ant-design/icons";
import type { Enterprise } from "@/types/enterprise";

type Ctx = { enterpriseId: string; enterprise: Enterprise };

const MODULE_MAP: Record<string, { title: string; en: string; render: (ctx: Ctx) => React.ReactNode }> = {
  info: {
    title: "基本信息", en: "ENTERPRISE ARCHIVE",
    render: ({ enterprise }) => (
      <>
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
          <EditButton />
        </div>
        <EnterpriseInfoCards enterprise={enterprise} readOnly />
      </>
    ),
  },
  surrounding: {
    title: "周边环境", en: "SURROUNDING",
    render: ({ enterpriseId, enterprise }) => (
      <SurroundingInfoPanel
        enterpriseId={enterpriseId}
        surroundingInfo={enterprise.surrounding_info || { nearby_units: [], sensitive_targets: [], traffic_info: "" }}
        onRefresh={() => undefined}
      />
    ),
  },
  chemicals: { title: "危险化学品", en: "CHEMICALS", render: ({ enterpriseId }) => <HazardousChemicalsTab enterpriseId={enterpriseId} /> },
  resources: { title: "应急资源", en: "EMERGENCY RESOURCES", render: ({ enterpriseId }) => <EmergencyResourceForm enterpriseId={enterpriseId} /> },
  assessment: { title: "风险评估报告", en: "RISK ASSESSMENT", render: ({ enterpriseId }) => <RiskAssessmentTab enterpriseId={enterpriseId} /> },
  investigation: { title: "应急资源调查报告", en: "RESOURCE INVESTIGATION", render: ({ enterpriseId }) => <ResourceInvestigationTab enterpriseId={enterpriseId} /> },
};

function EditButton() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <Button icon={<EditOutlined />} onClick={() => navigate(`/enterprises/${id}/edit`)}>编辑</Button>;
}

export default function EnterpriseModulePage() {
  const { id, moduleKey = "" } = useParams<{ id: string; moduleKey: string }>();
  const navigate = useNavigate();
  const mod = MODULE_MAP[moduleKey];
  const { data: enterprise, isLoading } = useQuery({
    queryKey: ["enterprise", id],
    queryFn: () => getEnterprise(id!),
    enabled: !!id,
  });

  if (!mod) return <div>模块不存在</div>;
  if (isLoading || !enterprise) return <Spin size="large" />;

  return (
    <div>
      <PageHeader
        title={mod.title}
        subtitle={mod.en}
        onBack={() => navigate(`/enterprises/${id}`)}
      />
      {mod.render({ enterpriseId: id!, enterprise })}
    </div>
  );
}
```

> 注意：`EnterpriseInfoCards`、`SurroundingInfoPanel` 的 props 以现有组件签名为准（若与上面假设不一致，按现有调用处补齐），其余代码可直接使用。

- [ ] **步骤 6：验证**

运行：`cd frontend && npx tsc -b && npx eslint src/components/enterprise/cockpit/ModulePageShell.tsx src/components/enterprise/cockpit/ModuleSideNav.tsx src/pages/Enterprise/enterpriseNavConfig.ts src/pages/Enterprise/EnterpriseModulePage.tsx src/pages/Enterprise/RiskManagementTab.tsx src/pages/Hazard/HazardInspectionTab.tsx`
预期：exit 0

- [ ] **步骤 7：Commit**

```bash
git add frontend/src/components/enterprise/cockpit/ModulePageShell.tsx frontend/src/components/enterprise/cockpit/ModuleSideNav.tsx frontend/src/pages/Enterprise/enterpriseNavConfig.ts frontend/src/pages/Enterprise/EnterpriseModulePage.tsx frontend/src/pages/Enterprise/RiskManagementTab.tsx frontend/src/pages/Hazard/HazardInspectionTab.tsx
git commit -m "feat(cockpit): module page shell, side nav and embedded tab components"
```

---

### 任务 8：路由重构（驾驶舱替换详情页 + 壳路由 + 旧路径重定向）

**文件：**
- 修改：`frontend/src/routes/index.tsx`
- 删除：`frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`

- [ ] **步骤 1：更新导入与辅助组件**

`frontend/src/routes/index.tsx` 顶部：

```tsx
import { createBrowserRouter, Navigate, useParams } from "react-router-dom";
```

把 `import EnterpriseDetailPage from "@/pages/Enterprise/EnterpriseDetailPage";` 替换为：

```tsx
import EnterpriseCockpitPage from "@/pages/Enterprise/EnterpriseCockpitPage";
import EnterpriseModulePage from "@/pages/Enterprise/EnterpriseModulePage";
import ModulePageShell from "@/components/enterprise/cockpit/ModulePageShell";
import RiskManagementTab from "@/pages/Enterprise/RiskManagementTab";
import HazardInspectionTab from "@/pages/Hazard/HazardInspectionTab";
import { riskNavGroups, hazardNavGroups } from "@/pages/Enterprise/enterpriseNavConfig";
```

在 `contentRoutes` 定义前追加辅助组件：

```tsx
function RiskRedirect({ to, params = [] }: { to: string; params?: Array<"objectId" | "methodId"> }) {
  const { id, objectId, methodId } = useParams<{ id: string; objectId?: string; methodId?: string }>();
  let suffix = "";
  if (params.includes("objectId") && objectId) suffix += `/${objectId}`;
  if (params.includes("methodId") && methodId) suffix += `/${methodId}`;
  return <Navigate to={`/enterprises/${id}${to}${suffix}`} replace />;
}

function RiskManagementRoute() {
  const { id } = useParams<{ id: string }>();
  return <RiskManagementTab enterpriseId={id!} embedded />;
}

function HazardLedgerRoute() {
  const { id } = useParams<{ id: string }>();
  return <HazardInspectionTab enterpriseId={id!} embedded />;
}
```

- [ ] **步骤 2：替换企业路由块**

`contentRoutes` 中把企业相关条目替换为（删除原 `:id` 详情、风险平级路由、隐患平级路由组）：

```tsx
{ path: "/enterprises", element: <EnterpriseListPage /> },
{ path: "/enterprises/new", element: <EnterpriseCreatePage /> },
{ path: "/enterprises/:id", element: <EnterpriseCockpitPage /> },
{ path: "/enterprises/:id/edit", element: <EnterpriseEditPage /> },
{ path: "/enterprises/:id/modules/:moduleKey", element: <EnterpriseModulePage /> },
{
  path: "/enterprises/:id/risk-management",
  element: <ModulePageShell title="风险分级管控" en="RISK MANAGEMENT" groups={riskNavGroups} />,
  children: [
    { index: true, element: <RiskManagementRoute /> },
    { path: "overview", element: <RiskOverviewPage /> },
    { path: "workbench", element: <RiskMappingWorkbenchPage /> },
    { path: "control-list", element: <RiskControlListPage /> },
    { path: "notice-cards", element: <RiskNoticeCardPage /> },
    { path: "notice-cards/:objectId", element: <RiskNoticeCardPreviewPage /> },
    { path: "publicity", element: <RiskPublicityPage /> },
    { path: "methods", element: <RiskMethodListPage /> },
    { path: "methods/:methodId", element: <RiskMethodEditorPage /> },
    { path: "data-dicts", element: <EnterpriseDictConfigPage /> },
  ],
},
{
  path: "/enterprises/:id/hazard",
  element: <ModulePageShell title="隐患排查治理" en="HAZARD MANAGEMENT" groups={hazardNavGroups} />,
  children: [
    { index: true, element: <HazardLedgerRoute /> },
    { path: "plans", element: <HazardPlanPage /> },
    { path: "tasks", element: <HazardTaskPage /> },
    { path: "templates", element: <HazardTemplatePage /> },
    { path: "dashboard", element: <HazardDashboardPage /> },
    { path: "publicity", element: <HazardPublicityPage /> },
    { path: "records/:rid", element: <HazardRecordDetailPage /> },
  ],
},
{ path: "/enterprises/:id/risk-assessment/preview", element: <RiskAssessmentPreview /> },
{ path: "/enterprises/:id/resource-investigation/preview", element: <ResourceInvestigationPreview /> },
{ path: "/enterprises/:id/org", element: <EnterpriseOrgPage /> },
{ path: "/enterprises/:id/data-dicts", element: <RiskRedirect to="/risk-management/data-dicts" /> },
{ path: "/enterprises/:id/risk-overview", element: <RiskRedirect to="/risk-management/overview" /> },
{ path: "/enterprises/:id/risk-mapping-workbench", element: <RiskRedirect to="/risk-management/workbench" /> },
{ path: "/enterprises/:id/risk-control-list", element: <RiskRedirect to="/risk-management/control-list" /> },
{ path: "/enterprises/:id/risk-publicity", element: <RiskRedirect to="/risk-management/publicity" /> },
{ path: "/enterprises/:id/risk-notice-cards", element: <RiskRedirect to="/risk-management/notice-cards" /> },
{ path: "/enterprises/:id/risk-notice-cards/:objectId", element: <RiskRedirect to="/risk-management/notice-cards" params={["objectId"]} /> },
{ path: "/enterprises/:id/risk-methods", element: <RiskRedirect to="/risk-management/methods" /> },
{ path: "/enterprises/:id/risk-methods/:methodId", element: <RiskRedirect to="/risk-management/methods" params={["methodId"]} /> },
{ path: "/enterprises/:enterprise_id/plans", element: <PlanListPage /> },
```

保留原 `/plans`、`/plans/new` 等预案路由与公开页路由不变。删除文件 `frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx`（`git rm`），确认无其他引用。

- [ ] **步骤 3：验证**

运行：`cd frontend && npx tsc -b`
预期：exit 0（确认无 EnterpriseDetailPage 残留引用）

运行：`cd frontend && npx eslint src/routes/index.tsx`
预期：exit 0（该文件既有 react-refresh/only-export-components 豁免注释保留）

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/routes/index.tsx
git rm frontend/src/pages/Enterprise/EnterpriseDetailPage.tsx
git commit -m "feat(cockpit): restructure enterprise routes to cockpit and module shells"
```

---

### 任务 9：全量门禁 + e2e 冒烟 + 收尾

**文件：**
- 创建：`frontend/e2e/enterprise-cockpit.spec.ts`

- [ ] **步骤 1：编写驾驶舱 e2e 冒烟测试**

创建 `frontend/e2e/enterprise-cockpit.spec.ts`（沿用 enterprise-switch.spec.ts 的 API mock 惯例）：

```ts
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
    if (path === "/api/v1/enterprises/ent-a" && method === "GET") {
      return route.fulfill(json(200, { code: 0, message: "ok", data: { id: "ent-a", name: "企业A", industry: "危险化学品", resources_count: 25, plans_count: 3, surrounding_info: {}, created_at: "x", updated_at: "x" } }));
    }
    if (path === "/api/v1/enterprises/ent-a/cockpit-summary" && method === "GET") {
      return route.fulfill(json(200, SUMMARY));
    }
    return route.continue();
  });
}

test("enterprise cockpit renders and navigates to risk module", async ({ page }) => {
  await mockApis(page);
  await page.goto("/login");
  await page.getByPlaceholder(/邮箱|账号/).fill("qa_e2e_test@test.com");
  await page.getByPlaceholder(/密码/).fill("password123");
  await page.getByRole("button", { name: /登\s*录/ }).click();
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
```

> 实现时以登录页实际占位符/按钮文案为准微调选择器；若项目 e2e 已用固定账号直连（storageState），沿用既有写法。

- [ ] **步骤 2：运行全量门禁**

后端：

运行：`cd backend && python -m pytest tests/ -q`
预期：全量通过（既有 asyncio 资源告警视为噪音）

前端：

运行：`cd frontend && npx tsc -b`
预期：exit 0

运行：`cd frontend && npx eslint .`
预期：exit 0（或仅剩既有文件债务，无新增）

运行：`cd frontend && npx vitest run`
预期：既有测试 + cockpitService 测试全部通过

e2e：

运行：`cd frontend && npx playwright test e2e/enterprise-cockpit.spec.ts`
预期：1 passed

- [ ] **步骤 3：手工冒烟清单（记录到提交说明）**

1. `/enterprises/:id` 驾驶舱：深色背景、跑马灯滚动、雷达扫描、10 模块导航 hover 辉光；
2. 点「风险管控」→ 左竖导航 9 项分组正确，默认风险树页无重复按钮行；点「楼层平面图」→ 楼层抽屉自动打开；
3. 点「隐患治理」→ 左竖导航 6 项，台账页无重复按钮行；
4. 点「基本信息」等简单模块 → 浅色页面 + 返回驾驶舱；
5. 旧链接 `/enterprises/:id/risk-overview` 与 `/enterprises/:id?tab=info` 均不 404；
6. `prefers-reduced-motion` 下动效停止、页面可用。

- [ ] **步骤 4：Commit 与收尾**

```bash
git add frontend/e2e/enterprise-cockpit.spec.ts
git commit -m "test(cockpit): enterprise cockpit e2e smoke test"
```

全部完成后：`codegraph sync .`、`graphify update .`（遵循项目铁律二），并向主控/用户汇报验收结果。

---

## 计划自检

**1. 规格覆盖度：**

- 驾驶舱布局（§4.1/4.2）→ 任务 4/5/6；
- 视觉令牌与动效（§4.3/4.4）→ 任务 4（cockpit.css 含全部关键帧与 reduced-motion）；
- 模块归类与导航（§3/§5）→ 任务 7（enterpriseNavConfig）+ 任务 6（ModuleNav）+ 任务 8（路由）；
- 汇总端点与数据契约（§7）→ 任务 1/2/3（含 hazard_counts 补充）；
- 路由与旧链接兼容（§6）→ 任务 8（RiskRedirect + ?tab 忽略）；
- 测试与验收（§9/§10）→ 任务 1-3 单测、任务 9 门禁与 e2e。

**2. 占位符扫描：** 无 TODO/待定；两处实现时注意点（现有组件 props 签名、登录选择器）为显式假设并给出兜底路径，非占位。

**3. 类型一致性：** `hazard_counts` 在后端 service/schema、前端 types/service/页面/e2e 中签名一致（open/due/overdue）；`ModulePageShell.groups` 为 `(id: string) => SideNavGroup[]`，与 enterpriseNavConfig 中 `riskNavGroups(id)`/`hazardNavGroups(id)` 一致；`embedded` prop 在两个 Tab 组件中签名一致。

**4. 已知取舍：** ① 最近动态 MVP 仅返回企业档案更新时间（无审计表，规格已声明）；② 风险管控「组织与人员」入口在 embedded 模式下隐藏（左竖导航不含跨模块链接）；③ `EnterpriseDetailPage.tsx` 删除，旧 `?tab=` 参数不再生效但 URL 不 404。
