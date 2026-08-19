# Codex Custom Subagents task handoff v1

Task: cockpit_02_impl

你正在实现「企业驾驶舱重构」实现计划的 任务 2：后端 schemas + cockpit-summary 端点。任务 1（聚合服务）已完成（commit 499a7a4，5 passed，已通过规格与质量审查）。

## 工作目录（重要）
C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\enterprise-cockpit
（git worktree，分支 codex/enterprise-cockpit。所有命令在 PowerShell 中执行；后端命令用 workdir 进入该目录的 backend 子目录。测试解释器用主仓库的：C:\Users\55061\Documents\数字化预案自动生成 2\backend\.venv\Scripts\python.exe）

## 任务描述（完整文本，含质量审查补充步骤）

**文件：**
- 创建：`backend/app/schemas/enterprise_cockpit.py`
- 修改：`backend/app/routers/enterprises.py`
- 修改：`backend/app/services/enterprise_cockpit_service.py`（补充 selectinload，见步骤 3 附加项）
- 测试：`backend/tests/test_enterprise_cockpit.py`（追加端点测试与边界用例）

步骤 1：编写失败的测试

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

同时追加边界用例（质量审查补充，覆盖任务 1 未覆盖路径）：

```python
def test_aggregate_events_empty():
    out = aggregate_events([])
    assert out["risk_counts"] == {"major": 0, "larger": 0, "general": 0, "low": 0, "total": 0}
    assert out["zone_risks"] == []
    assert out["top_risks"] == []
    assert out["risk_index"] == 0


def test_aggregate_events_unit_level_fallback_and_bad_values():
    events = [
        FakeEvent(level=None, score="abc", zone="储罐区", obj="球罐区", unit="1#球罐", responsible="生产部"),
        FakeEvent(level="低", score="10", zone="办公楼", obj="办公室"),
    ]
    out = aggregate_events(events)
    assert out["risk_counts"]["general"] == 1
    assert out["risk_counts"]["low"] == 1
    assert out["top_risks"][0]["name"] == "球罐区"
    assert out["top_risks"][0]["score"] == 0.0
    assert out["top_risks"][0]["responsible_unit"] == "生产部"
    zone_names = [z["zone_name"] for z in out["zone_risks"]]
    assert "储罐区" in zone_names and "办公楼" in zone_names
```

（`FakeEvent` 已在任务 1 定义：`unit` 非 None 时走 `unit.object` 链；`level=None` 归 general；`score="abc"` 解析为 0。）

步骤 2：运行测试确认失败
运行：`C:\Users\55061\Documents\数字化预案自动生成 2\backend\.venv\Scripts\python.exe -m pytest tests/test_enterprise_cockpit.py -v`
预期：FAIL（`ImportError: cannot import name 'build_cockpit_summary' from 'app.routers.enterprises'`，或边界用例失败）

步骤 3：实现 schemas

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

步骤 3 附加项（质量审查补充）：给 `_fetch_events` 加显式 `selectinload`，避免 async 会话下的惰性加载：

在 `backend/app/services/enterprise_cockpit_service.py`：

```python
from sqlalchemy.orm import selectinload
```

`_fetch_events` 的查询改为：

```python
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
        .options(
            selectinload(RiskEvent.object).selectinload(RiskObject.zone),
            selectinload(RiskEvent.unit).selectinload(RiskUnit.object).selectinload(RiskObject.zone),
        )
    )
    return list(dict.fromkeys(rows.scalars().all()))
```

步骤 4：实现端点

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

步骤 5：运行测试确认通过
运行：`C:\Users\55061\Documents\数字化预案自动生成 2\backend\.venv\Scripts\python.exe -m pytest tests/test_enterprise_cockpit.py -v`
预期：9 passed（5 个任务 1 + 2 个端点 + 2 个边界）

再运行全量后端测试：
运行：`C:\Users\55061\Documents\数字化预案自动生成 2\backend\.venv\Scripts\python.exe -m pytest tests/ -q`
预期：全量通过（既有告警视为噪音）

步骤 6：Commit
```bash
git add backend/app/schemas/enterprise_cockpit.py backend/app/routers/enterprises.py backend/app/services/enterprise_cockpit_service.py backend/tests/test_enterprise_cockpit.py
git commit -m "feat(cockpit): enterprise cockpit summary endpoint"
```

## 上下文（场景铺设）
- 任务 1 已完成：`build_cockpit_summary` 返回 dict，键与 `CockpitSummary` schema 一一对应（risk_counts/zone_risks/top_risks/risk_index/hazard_counts/todos/completion/recent_activities）。
- 参考端点模式：`backend/app/routers/enterprises.py` 中 `get_enterprise`（企业归属校验：id + user_id，404「企业不存在」）；`backend/app/routers/risk_management.py` 中 `_get_ent` 也可参考。
- 测试惯例：`backend/tests/test_enterprise_org.py` 用 TestClient + dependency_overrides（get_current_user/get_db）+ MagicMock 会话。

## 项目规则
- 提交消息遵循 conventional commits；TASKS.md 永不提交；不要修改任务范围外文件；提交前 `git diff --check`。
- 你不是孤立的：同一 worktree 可能有其他会话/代理改动，不要 revert 他人修改；冲突先停下提问。
- 按 AGENTS.md 铁律一，在 TASKS.md 顶部追加「当前状态快照」（不提交）。

## 开始之前
有疑问现在就问，不要猜测。

## 汇报格式
- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 实现内容、测试命令与结果、修改文件清单、commit SHA、自审发现
