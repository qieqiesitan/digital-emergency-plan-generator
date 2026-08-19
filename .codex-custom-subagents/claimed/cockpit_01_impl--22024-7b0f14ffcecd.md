# Codex Custom Subagents task handoff v1

Task: cockpit_01_impl

你正在实现「企业驾驶舱重构」实现计划的 任务 1：后端驾驶舱聚合服务（纯函数 + 查询编排）。这是 9 个任务中的第 1 个（先做后端）。

## 工作目录（重要）
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit
（这是已创建的 git worktree，分支 codex/enterprise-cockpit，与主仓库隔离。所有命令在 PowerShell 中执行；后端命令请用 workdir 进入该目录的 backend 子目录。）

## 任务描述（来自计划，完整文本）

### 任务 1：后端驾驶舱聚合服务（纯函数 + 查询编排）

**文件：**
- 创建：`backend/app/services/enterprise_cockpit_service.py`
- 测试：`backend/tests/test_enterprise_cockpit.py`

步骤 1：编写失败的测试

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
    assert _risk_index({"major": 2, "larger": 4, "general": 18, "low": 10}) == 62
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
    assert out["risk_index"] == 45
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

步骤 2：运行测试确认失败
运行：`cd backend && python -m pytest tests/test_enterprise_cockpit.py -v`
预期：FAIL，`ModuleNotFoundError: No module named 'app.services.enterprise_cockpit_service'`

步骤 3：实现聚合服务

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
    return min(
        100,
        round(
            counts["major"] * 100
            + counts["larger"] * 70
            + counts["general"] * 40
            + counts["low"] * 10
        ),
    )


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

步骤 4：运行测试确认通过
运行：`cd backend && python -m pytest tests/test_enterprise_cockpit.py -v`
预期：5 passed

步骤 5：Commit
```bash
git add backend/tests/test_enterprise_cockpit.py backend/app/services/enterprise_cockpit_service.py
git commit -m "feat(cockpit): enterprise cockpit summary aggregation service"
```

## 上下文（场景铺设）
- 这是「企业驾驶舱」功能的后端地基：把企业详情页重构为深色驾驶舱总览页，总览需要一次性聚合风险/隐患/完成度等数据。后续任务 2 会在 enterprises.py 挂一个 cockpit-summary 端点调用本服务的 build_cockpit_summary。
- 参考既有实现：backend/app/services/risk_stats_service.py（RiskEvent↔RiskUnit/RiskObject→RiskZone 的 join 模式）、backend/app/services/onboarding_service.py（compute_completion 的调用与返回结构 {"percent", "modules":[{key,label,weight,done}]}）。
- 模型字段已确认：RiskEvent 有 risk_level/risk_score（str）；RiskObject 有 name/zone_id/responsible_unit；RiskUnit 有 object_id/name；RiskZone 有 enterprise_id/name；HazardRecord 有 enterprise_id/status/deadline（Date）；RiskAssessmentReport/ResourceInvestigationReport 有 enterprise_id/status。
- 测试命令在 backend 目录执行（python -m pytest）。

## 项目规则
- 代码注释和提交消息用英文/中文均可；提交消息遵循 conventional commits（如上面的示例）。
- TASKS.md 永不提交（不要 git add TASKS.md）。
- 不要修改任务范围外的文件；提交前运行 git diff --check。
- 你不是孤立的：同一 worktree 可能有其他会话/代理改动，不要 revert 他人的修改；如发现冲突先停下提问。
- 按项目 AGENTS.md 铁律一，在 TASKS.md 顶部追加一条「当前状态快照」记录你正在做什么/刚完成动作/下一步/关键上下文（不提交）。

## 开始之前
如果你对需求、方案、依赖或验收标准有疑问，**现在就问**，不要猜测。

## 汇报格式
完成后汇报：
- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 你实现了什么、测试了什么及结果
- 修改了哪些文件、commit SHA
- 自审发现、问题或疑虑
