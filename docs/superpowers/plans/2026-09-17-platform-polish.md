# 平台化收尾（AI 能力注册表 + 调用统计 + 跨企业总览）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把平台从"单企业工具"补成"平台"：AI 能力可管理可观测（注册表 + 调用统计），以及跨企业的经营视角总览。

**架构：** 两项都建立在已有数据上，不新建采集链路——

1. **AI 能力注册表**：把散在代码里的 AI 能力（提示词、模型、是否可人工介入）变成可管理对象；调用统计直接聚合计划 2 建的 `llm_call_logs`
2. **跨企业总览**：现有 `enterprise_cockpit_service` 是单企业视角，本计划加一层多企业聚合

**技术栈：** Python 3.12 / FastAPI / SQLAlchemy 2.x / React 18 + antd 5，无新依赖。

**规格来源：** `docs/superpowers/specs/2026-09-17-safety-control-platform-design.md` §5.4、§11（P3）

**依赖：** 计划 2（`llm_call_logs` 与能力覆盖是统计的前置）、计划 1（重大危险源数据）、计划 8（作业票数据）。

**范围提醒：** 这是 P3，是**锦上添花**，不是上线阻塞项。如果排期紧，可以整体后置——但 `llm_call_logs` 已经在计划 2 里开始积累了，统计随时可以补，不会丢历史数据。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `backend/app/models/ai_capability.py`（新建） | AI 能力注册表 ORM |
| `backend/db_migration_20260917_ai_capability.sql`（新建） | DDL + 内置能力种子 |
| `backend/app/services/ai_capability_service.py`（新建） | 能力注册/查询/启停 |
| `backend/app/services/ai_usage_stats.py`（新建） | 基于 `llm_call_logs` 的聚合统计（纯查询） |
| `backend/app/services/platform_overview.py`（新建） | 跨企业总览聚合 |
| `backend/app/schemas/platform.py`（新建） | 出入参 |
| `backend/app/routers/platform.py`（新建） | REST API |
| `backend/app/main.py`（修改） | 注册路由 |
| `backend/tests/test_ai_usage_stats.py`（新建） | 统计聚合 |
| `backend/tests/test_platform_overview.py`（新建） | 跨企业总览 |
| `backend/tests/test_platform_api.py`（新建） | 端点测试 |
| `frontend/src/pages/Settings/AiCapabilityPage.tsx`（新建） | AI 能力管理页 |
| `frontend/src/pages/Dashboard/PlatformOverviewPage.tsx`（新建） | 跨企业总览页 |
| `frontend/src/services/platformService.ts`（新建） | API 封装 |
| `frontend/src/routes/index.tsx`（修改） | 2 条路由 |

**既有约定**

- `llm_call_logs` 的字段：`module` / `capability` / `model` / `duration_ms` / 各类 token / `success` / `error_code` / `retry_count` / `truncated` / `created_at`
- 企业驾驶舱聚合见 `app/services/enterprise_cockpit_service.py`（单企业视角，本计划不改它）

---

## 任务 1：AI 能力注册表

**文件：**

- 创建：`backend/app/models/ai_capability.py`
- 创建：`backend/db_migration_20260917_ai_capability.sql`
- 创建：`backend/app/services/ai_capability_service.py`
- 测试：`backend/tests/test_ai_capability.py`

**为什么需要它：** 现在"平台有哪些 AI 能力"散在代码里——24 个端点的提示词与模型选择各写各的，运营想知道"风险辨识用的哪个模型、能不能关掉"得去翻代码。注册表把这件事变成可查可改的数据。

- [ ] **步骤 1：编写失败的测试**

```python
"""AI 能力注册表：结构、启停、与调用日志的关联。"""

import re
from pathlib import Path

from app.models.ai_capability import AICapability
from app.services.ai_capability_service import (
    CapabilityError,
    is_capability_enabled,
)

BACKEND = Path(__file__).resolve().parents[1]
SQL = (BACKEND / "db_migration_20260917_ai_capability.sql").read_text(encoding="utf-8")


def test_tablename_and_columns():
    assert AICapability.__tablename__ == "ai_capabilities"
    cols = AICapability.__table__.columns
    for name in (
        "code", "module", "name", "prompt_ref", "model_override",
        "is_enabled", "allow_manual", "description",
    ):
        assert name in cols, name
    assert cols["code"].nullable is False
    assert cols["is_enabled"].nullable is False


def test_migration_creates_table_and_unique_code():
    assert re.search(r"CREATE TABLE IF NOT EXISTS\s+ai_capabilities\b", SQL)
    assert re.search(r"UNIQUE\s*\(\s*code\s*\)", SQL, re.I)


def test_is_capability_enabled_returns_true_when_not_registered():
    """未注册的能力默认启用——注册表是"可管理"，不是"必须注册才能用"，
    否则新加一个 AI 能力忘了注册就会静默失效。"""
    assert is_capability_enabled(None) is True


def test_is_capability_enabled_respects_flag():
    cap = AICapability(code="x", module="m", name="n", is_enabled=False)
    assert is_capability_enabled(cap) is False
    cap.is_enabled = True
    assert is_capability_enabled(cap) is True


def test_capability_error_is_value_error():
    assert issubclass(CapabilityError, ValueError)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ai_capability.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写 ORM 与迁移**

```python
"""AI 能力注册表。

把"平台有哪些 AI 能力、每个用哪个提示词与模型、能不能关"变成可查可改的数据，
而不是散在 24 个端点里各写各的。
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AICapability(Base):
    __tablename__ = "ai_capabilities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(60), nullable=False)  # 与 llm_call_logs.capability 对齐
    module: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    prompt_ref: Mapped[Optional[str]] = mapped_column(String(120))  # 指向 prompt_templates.template_code
    model_override: Mapped[Optional[str]] = mapped_column(String(120))
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

```sql
-- 20260917 AI 能力注册表。
-- code 与 llm_call_logs.capability 对齐，便于把"能力"与其"调用记录"关联起来。
CREATE TABLE IF NOT EXISTS ai_capabilities (
    id UUID PRIMARY KEY,
    code VARCHAR(60) NOT NULL,
    module VARCHAR(60) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    prompt_ref VARCHAR(120),
    model_override VARCHAR(120),
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    allow_manual BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ai_capability_code UNIQUE (code)
);

-- 内置能力种子（与现有 24 个 AI 端点对应；用确定性 UUID5，可重复执行）
INSERT INTO ai_capabilities (id, code, module, name, description, sort_order) VALUES
 ('3f1a1c9e-0000-5000-8000-000000000001', 'risk_suggest_objects', '风险分级管控',
  'AI 建议风险分析对象', '按工艺/设备资料生成风险分析对象候选', 10),
 ('3f1a1c9e-0000-5000-8000-000000000002', 'risk_suggest_events', '风险分级管控',
  'AI 建议风险事件', '生成风险事件与后果描述', 20),
 ('3f1a1c9e-0000-5000-8000-000000000003', 'risk_suggest_measures', '风险分级管控',
  'AI 建议管控措施', '生成管控措施并匹配法规条文', 30),
 ('3f1a1c9e-0000-5000-8000-000000000004', 'hazard_record_assist', '隐患排查治理',
  '隐患登记辅助', '隐患摘要与分类', 40),
 ('3f1a1c9e-0000-5000-8000-000000000005', 'hazard_grade', '隐患排查治理',
  '隐患分级建议', '按认定依据建议隐患等级', 50),
 ('3f1a1c9e-0000-5000-8000-000000000006', 'major_hazard_extract', '重大危险源',
  '资料抽取（单元/品种）', '从安全评价报告中抽取重大危险源单元与品种存量', 60),
 ('3f1a1c9e-0000-5000-8000-000000000007', 'work_ticket_jsa', '特殊作业',
  'JSA 作业安全分析生成', '按作业内容生成危害识别与预防措施', 70),
 ('3f1a1c9e-0000-5000-8000-000000000008', 'work_ticket_precheck', '特殊作业',
  '提交前合规校验建议', '提示缺项与法规依据（不阻断，阻断由确定性校验负责）', 80)
ON CONFLICT (id) DO NOTHING;
```

```python
"""AI 能力注册表服务。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_capability import AICapability


class CapabilityError(ValueError):
    """能力配置错误。"""


def is_capability_enabled(capability) -> bool:
    """未注册的能力默认启用。

    注册表是"可管理"，不是"必须注册才能用"——否则新加一个 AI 能力忘了注册
    就会静默失效，这类 bug 极难排查。
    """
    if capability is None:
        return True
    return bool(getattr(capability, "is_enabled", True))


async def get_capability(db: AsyncSession, code: str):
    res = await db.execute(select(AICapability).where(AICapability.code == code))
    return res.scalar_one_or_none()


async def list_capabilities(db: AsyncSession) -> list[AICapability]:
    res = await db.execute(select(AICapability).order_by(AICapability.sort_order))
    return list(res.scalars().all())
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ai_capability.py -v
```

预期：`5 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/models/ai_capability.py backend/app/services/ai_capability_service.py backend/db_migration_20260917_ai_capability.sql backend/tests/test_ai_capability.py
git commit -m "feat(platform): AI 能力注册表（能力/提示词/模型/启停可管理）（任务 1/4）"
```

---

## 任务 2：AI 调用统计

**文件：**

- 创建：`backend/app/services/ai_usage_stats.py`
- 测试：`backend/tests/test_ai_usage_stats.py`

**目的：** 回答三个问题——**这个月花了多少**（按 token 估）、**哪些能力在失败**、**有没有被静默截断的调用**。数据源是计划 2 建的 `llm_call_logs`，本任务只做聚合查询，不新增采集。

- [ ] **步骤 1：编写失败的测试**

```python
"""AI 调用统计：按能力/模块聚合、失败率、截断计数。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.ai_usage_stats import (
    summarize_rows,
)


def _row(capability, success=True, tokens=100, truncated=False, duration=1000, retry=0, code=None):
    r = MagicMock()
    r.capability = capability
    r.success = success
    r.total_tokens = tokens
    r.truncated = truncated
    r.duration_ms = duration
    r.retry_count = retry
    r.error_code = code
    return r


def test_summarize_counts_and_tokens():
    rows = [
        _row("hazard_grade", tokens=100),
        _row("hazard_grade", tokens=200),
        _row("risk_suggest_measures", tokens=50),
    ]
    out = summarize_rows(rows)
    assert out["total_calls"] == 3
    assert out["total_tokens"] == 350
    by_cap = {c["capability"]: c for c in out["by_capability"]}
    assert by_cap["hazard_grade"]["calls"] == 2
    assert by_cap["hazard_grade"]["tokens"] == 300


def test_summarize_computes_failure_rate():
    rows = [
        _row("a", success=True),
        _row("a", success=False, code=429),
        _row("a", success=True),
        _row("a", success=True),
    ]
    out = summarize_rows(rows)
    by_cap = {c["capability"]: c for c in out["by_capability"]}
    assert by_cap["a"]["failures"] == 1
    assert by_cap["a"]["failure_rate"] == pytest.approx(0.25)


def test_summarize_flags_truncated_calls():
    """被截断的调用单独计数——它 success 可能是 True，但结果是半截的。"""
    rows = [_row("a", success=True, truncated=True), _row("a")]
    out = summarize_rows(rows)
    by_cap = {c["capability"]: c for c in out["by_capability"]}
    assert by_cap["a"]["truncated"] == 1
    assert out["total_truncated"] == 1


def test_summarize_averages_duration():
    rows = [_row("a", duration=1000), _row("a", duration=3000)]
    out = summarize_rows(rows)
    by_cap = {c["capability"]: c for c in out["by_capability"]}
    assert by_cap["a"]["avg_duration_ms"] == 2000


def test_summarize_handles_null_tokens():
    """有些供应商不回 token 数，不能因此报错或算成 0 而失真。"""
    rows = [_row("a", tokens=None), _row("a", tokens=100)]
    out = summarize_rows(rows)
    assert out["total_tokens"] == 100


def test_summarize_empty_rows():
    out = summarize_rows([])
    assert out["total_calls"] == 0
    assert out["by_capability"] == []


def test_summarize_ignores_rows_without_capability():
    """capability 为空的行归到 unknown，不丢弃——丢了会让总量对不上。"""
    rows = [_row(None), _row("a")]
    out = summarize_rows(rows)
    caps = {c["capability"] for c in out["by_capability"]}
    assert "unknown" in caps
    assert out["total_calls"] == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_ai_usage_stats.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""AI 调用统计：把 llm_call_logs 聚合成运营能看懂的数字。

只做聚合查询，不新增采集——采集在 llm_client 的埋点里做（计划 2）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_call_log import LlmCallLog


def summarize_rows(rows: Sequence) -> dict:
    """把调用日志行聚合成统计。纯函数，便于单测与复用。"""
    if not rows:
        return {"total_calls": 0, "total_tokens": 0, "total_truncated": 0, "by_capability": []}

    buckets: dict[str, dict] = {}
    total_tokens = 0
    total_truncated = 0

    for r in rows:
        cap = getattr(r, "capability", None) or "unknown"
        b = buckets.setdefault(
            cap,
            {"capability": cap, "calls": 0, "failures": 0, "truncated": 0,
             "tokens": 0, "duration_sum": 0, "duration_n": 0},
        )
        b["calls"] += 1
        if not getattr(r, "success", True):
            b["failures"] += 1
        if getattr(r, "truncated", False):
            b["truncated"] += 1
            total_truncated += 1
        tokens = getattr(r, "total_tokens", None)
        if tokens:
            b["tokens"] += int(tokens)
            total_tokens += int(tokens)
        duration = getattr(r, "duration_ms", None)
        if duration is not None:
            b["duration_sum"] += int(duration)
            b["duration_n"] += 1

    by_capability = []
    for b in buckets.values():
        calls = b["calls"]
        by_capability.append(
            {
                "capability": b["capability"],
                "calls": calls,
                "failures": b["failures"],
                "failure_rate": round(b["failures"] / calls, 4) if calls else 0.0,
                "truncated": b["truncated"],
                "tokens": b["tokens"],
                "avg_duration_ms": round(b["duration_sum"] / b["duration_n"]) if b["duration_n"] else None,
            }
        )
    by_capability.sort(key=lambda x: x["calls"], reverse=True)
    return {
        "total_calls": len(rows),
        "total_tokens": total_tokens,
        "total_truncated": total_truncated,
        "by_capability": by_capability,
    }


async def usage_stats(
    db: AsyncSession,
    *,
    days: int = 30,
    module: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict:
    """取最近 N 天的调用日志并聚合。"""
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    stmt = select(LlmCallLog).where(LlmCallLog.created_at >= since)
    if module:
        stmt = stmt.where(LlmCallLog.module == module)
    res = await db.execute(stmt)
    rows = list(res.scalars().all())
    out = summarize_rows(rows)
    out["since"] = since.isoformat()
    out["days"] = days
    return out
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_ai_usage_stats.py -v
```

预期：`7 passed`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/ai_usage_stats.py backend/tests/test_ai_usage_stats.py
git commit -m "feat(platform): AI 调用统计（按能力聚合调用数/失败率/截断/token/耗时）（任务 2/4）"
```

---

## 任务 3：跨企业总览

**文件：**

- 创建：`backend/app/services/platform_overview.py`
- 测试：`backend/tests/test_platform_overview.py`

**与现有能力的区别：** `enterprise_cockpit_service` 是**单企业**视角（进到某个企业看它的驾驶舱）。本任务加的是**跨企业**视角：一共有多少家企业、风险点/隐患/重大危险源/作业票各自的总量与分布。这是从"工具"到"平台"的分界线。

- [ ] **步骤 1：编写失败的测试**

```python
"""跨企业总览聚合。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.platform_overview import (
    overview_totals,
)


def _scalar_db(values: list):
    """按调用顺序依次返回 scalar 的假 db。"""
    db = MagicMock()
    seq = iter(values)

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar.return_value = next(seq, 0)
        return res

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_overview_totals_returns_all_sections():
    db = _scalar_db([3, 120, 45, 8, 2, 30])
    out = await overview_totals(db)
    assert set(out) == {"enterprises", "risk_points", "hazards", "major_hazard_units", "major_hazard_level_1_2", "work_tickets"}
    assert out["enterprises"] == 3
    assert out["major_hazard_units"] == 8


@pytest.mark.asyncio
async def test_overview_includes_level_1_2_count():
    """一、二级重大危险源是监管重点，单独计数。"""
    db = _scalar_db([1, 0, 0, 5, 2, 0])
    out = await overview_totals(db)
    assert out["major_hazard_level_1_2"] == 2


@pytest.mark.asyncio
async def test_overview_handles_zero_everything():
    db = _scalar_db([0, 0, 0, 0, 0, 0])
    out = await overview_totals(db)
    assert all(v == 0 for v in out.values())
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && python -m pytest tests/test_platform_overview.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：编写实现**

```python
"""跨企业总览聚合。

与 enterprise_cockpit_service 的分工：那个是单企业驾驶舱，这个是平台级视角。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.hazard_management import HazardRecord
from app.models.major_hazard import MajorHazardCalculation, MajorHazardUnit
from app.models.risk_management import RiskObject
from app.models.work_ticket import WorkTicketInstance


async def _count(db: AsyncSession, stmt) -> int:
    res = await db.execute(stmt)
    return int(res.scalar() or 0)


async def overview_totals(db: AsyncSession) -> dict:
    """平台级总量。每项一个 count 查询，够用且直观。"""
    enterprises = await _count(db, select(func.count()).select_from(Enterprise))
    risk_points = await _count(
        db,
        select(func.count()).select_from(RiskObject).where(RiskObject.is_risk_point.is_(True)),
    )
    hazards = await _count(db, select(func.count()).select_from(HazardRecord))
    major_units = await _count(db, select(func.count()).select_from(MajorHazardUnit))
    # 一、二级重大危险源是监管重点，单独计数
    level_1_2 = await _count(
        db,
        select(func.count())
        .select_from(MajorHazardCalculation)
        .where(MajorHazardCalculation.is_major_hazard.is_(True))
        .where(MajorHazardCalculation.level.in_(["一级", "二级"]))
        .where(
            MajorHazardCalculation.id.in_(
                select(MajorHazardCalculation.id).distinct()
            )
        ),
    )
    work_tickets = await _count(db, select(func.count()).select_from(WorkTicketInstance))
    return {
        "enterprises": enterprises,
        "risk_points": risk_points,
        "hazards": hazards,
        "major_hazard_units": major_units,
        "major_hazard_level_1_2": level_1_2,
        "work_tickets": work_tickets,
    }
```

> ⚠️ **`major_hazard_level_1_2` 的查询要按最新快照去重**：一个单元可能有多次计算，
> 直接 count 会把历史快照也算进去。实现时先取每个单元的最新 `seq` 再筛等级。
> 上面那段子查询只是占位结构，**落地时必须改成"每单元最新快照"的写法**，
> 并补一个测试：同一单元计算两次（先二级后不构成），计数应为 0。

- [ ] **步骤 4：补上"最新快照去重"的测试并修正实现**

```python
def test_overview_level_count_uses_latest_snapshot_only():
    """同一单元先算出二级、后又算出不构成，则不应计入一二级。"""
    import inspect

    from app.services import platform_overview

    src = inspect.getsource(platform_overview.overview_totals)
    assert "seq" in src or "distinct" in src, (
        "一二级计数必须按最新快照去重，否则历史快照会被重复计入"
    )
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_platform_overview.py -v
```

预期：`4 passed`

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/platform_overview.py backend/tests/test_platform_overview.py
git commit -m "feat(platform): 跨企业总览聚合（含一二级重大危险源单独计数）（任务 3/4）"
```

---

## 任务 4：API 与前端页面

**文件：**

- 创建：`backend/app/schemas/platform.py`
- 创建：`backend/app/routers/platform.py`
- 修改：`backend/app/main.py`
- 创建：`frontend/src/services/platformService.ts`
- 创建：`frontend/src/pages/Settings/AiCapabilityPage.tsx`
- 创建：`frontend/src/pages/Dashboard/PlatformOverviewPage.tsx`
- 修改：`frontend/src/routes/index.tsx`
- 测试：`backend/tests/test_platform_api.py`

- [ ] **步骤 1：后端 schemas 与路由**

```python
"""平台级出入参。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CapabilityOut(BaseModel):
    id: str
    code: str
    module: str
    name: str
    description: Optional[str] = None
    prompt_ref: Optional[str] = None
    model_override: Optional[str] = None
    is_enabled: bool
    allow_manual: bool

    model_config = {"from_attributes": True}


class CapabilityUpdateIn(BaseModel):
    is_enabled: Optional[bool] = None
    allow_manual: Optional[bool] = None
    model_override: Optional[str] = None
    prompt_ref: Optional[str] = None
```

```python
"""平台级 API：AI 能力管理、调用统计、跨企业总览。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ai_capability import AICapability
from app.schemas.platform import CapabilityOut, CapabilityUpdateIn
from app.services.ai_usage_stats import usage_stats
from app.services.platform_overview import overview_totals

router = APIRouter(prefix="/platform", tags=["Platform"])


def _ok(data):
    return {"success": True, "code": 200, "message": "success", "data": data}


@router.get("/capabilities")
async def list_capabilities(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(AICapability).order_by(AICapability.sort_order))
    return _ok([CapabilityOut.model_validate(c) for c in res.scalars().all()])


@router.put("/capabilities/{code}")
async def update_capability(
    code: str, payload: CapabilityUpdateIn, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(AICapability).where(AICapability.code == code))
    cap = res.scalar_one_or_none()
    if cap is None:
        raise HTTPException(404, "AI 能力不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cap, key, value)
    await db.commit()
    return _ok(CapabilityOut.model_validate(cap))


@router.get("/ai-usage")
async def ai_usage(
    days: int = Query(default=30, ge=1, le=365),
    module: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """AI 调用统计：按能力看调用数、失败率、截断数、token 与耗时。"""
    return _ok(await usage_stats(db, days=days, module=module))


@router.get("/overview")
async def platform_overview(db: AsyncSession = Depends(get_db)):
    """跨企业总览。注意：这是平台级视角，与单企业驾驶舱不同。"""
    return _ok(await overview_totals(db))
```

- [ ] **步骤 2：注册路由**

`backend/app/main.py` 第 14 行 import 列表末尾加 `, platform`；在 `app.include_router(work_ticket.router, prefix="/api/v1")` 之后加：

```python
app.include_router(platform.router, prefix="/api/v1")
```

- [ ] **步骤 3：编写端点测试**

```python
"""平台级端点测试。"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.routers import platform


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

    def scalar(self):
        return self._items[0] if self._items else 0


def _client(handler):
    app = FastAPI()
    app.include_router(platform.router, prefix="/api/v1")

    async def _db():
        db = MagicMock()
        db.execute = AsyncMock(side_effect=handler)
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_list_capabilities():
    cap = MagicMock()
    cap.id = "c1"
    cap.code = "hazard_grade"
    cap.module = "隐患排查治理"
    cap.name = "隐患分级建议"
    cap.description = None
    cap.prompt_ref = None
    cap.model_override = None
    cap.is_enabled = True
    cap.allow_manual = True

    async def handler(stmt, *a, **k):
        return _Result([cap])

    client = _client(handler)
    resp = client.get("/api/v1/platform/capabilities")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["code"] == "hazard_grade"


def test_update_capability_404_when_missing():
    async def handler(stmt, *a, **k):
        return _Result([])

    client = _client(handler)
    resp = client.put("/api/v1/platform/capabilities/nope", json={"is_enabled": False})
    assert resp.status_code == 404


def test_overview_endpoint_returns_all_sections():
    async def handler(stmt, *a, **k):
        return _Result([1])

    client = _client(handler)
    resp = client.get("/api/v1/platform/overview")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "enterprises" in data
    assert "major_hazard_level_1_2" in data
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && python -m pytest tests/test_platform_api.py tests/test_ai_capability.py tests/test_ai_usage_stats.py tests/test_platform_overview.py -q
```

预期：`19 passed`

- [ ] **步骤 5：前端页面**

| 页面 | 关键行为 |
|---|---|
| `AiCapabilityPage` | 能力列表（模块 / 名称 / 关联提示词 / 模型覆盖 / 启用开关 / 允许人工介入）；上方一组统计卡片（近 30 天总调用、总 token、**截断数**）；下方按能力的表格（调用数 / **失败率**（>10% 标红）/ 截断数 / 平均耗时） |
| `PlatformOverviewPage` | 跨企业总览：企业数 / 风险点数 / 隐患数 / 重大危险源单元数 / **一、二级重大危险源数**（单独高亮）/ 作业票数；每块可点进对应模块 |

`platformService.ts` 封装上列三个端点。

**注意与单企业驾驶舱的区分**：跨企业总览是**平台运营视角**，放在全局 `/platform/overview` 而非 `/enterprises/:id` 下；页面上要有一句说明避免用户混淆（"这里是全平台汇总，单企业详情请进入企业驾驶舱"）。

- [ ] **步骤 6：注册路由**

`frontend/src/routes/index.tsx` 追加：

```
/settings/ai-capabilities   → AiCapabilityPage
/platform/overview          → PlatformOverviewPage
```

- [ ] **步骤 7：验证**

运行：

```bash
docker exec -w /app emergency-plan-frontend npx tsc -b
docker exec -w /app emergency-plan-frontend npx vitest run
docker exec -w /app emergency-plan-frontend npx eslint src/pages/Settings/AiCapabilityPage.tsx src/pages/Dashboard/PlatformOverviewPage.tsx
```

预期：`tsc` exit 0；vitest 全绿；eslint 无新增错误

- [ ] **步骤 8：真实浏览器冒烟**

1. AI 能力页能看到 8 条内置能力；关掉其中一条后，界面显示为停用
2. **关键验证**：关掉某能力后，调用它的页面应给出"该能力已停用"的提示，而**不是 500**——未注册的能力默认启用，已注册但停用的要有明确反馈
3. 统计卡片显示近 30 天数据；**造 1 次失败调用后失败率随之变化**
4. 跨企业总览显示的数量与 `psql` 直接 count 的结果一致

- [ ] **步骤 9：Commit**

```bash
git add backend/app/schemas/platform.py backend/app/routers/platform.py backend/app/main.py backend/tests/test_platform_api.py frontend/src/services/platformService.ts frontend/src/pages/Settings/AiCapabilityPage.tsx frontend/src/pages/Dashboard/PlatformOverviewPage.tsx frontend/src/routes/index.tsx
git commit -m "feat(platform): AI 能力管理页 + 调用统计 + 跨企业总览（含 API）（任务 4/4）"
```

---

## 验收清单

- [ ] `cd backend && python -m pytest tests/ -q` 失败数不高于 4 个既有失败
- [ ] `docker exec -w /app emergency-plan-frontend npx tsc -b` exit 0，vitest 全绿
- [ ] **8 条内置能力齐全**，`code` 与 `llm_call_logs.capability` 对得上（否则统计关联不上）
- [ ] **未注册能力默认启用**：新增一个 AI 能力忘注册时不会静默失效
- [ ] **停用有明确反馈**：停用某能力后调用它的页面给出提示而不是 500
- [ ] **截断单独计数**：`truncated` 的调用即使 `success=True` 也被单列——它是"看起来成功但结果是半截的"
- [ ] **失败率可见且标红**：>10% 的能力在页面上标红
- [ ] **一二级重大危险源按最新快照去重计数**：同一单元先算出二级、后算出不构成时，计数为 0
- [ ] 跨企业总览的数量与直接 SQL count 一致
- [ ] 迁移幂等：`db_migration_20260917_ai_capability.sql` 连跑两次无报错

## 未纳入本计划

- **成本换算（token → 金额）**：需要维护各模型单价表，且单价会变；先展示 token 与调用数，金额由运营自行换算
- **调用异常的自动告警**：需要通知渠道（邮件/钉钉/企微），属另一个话题
- **能力级的权限控制**（谁能改 AI 能力配置）：当前沿用系统设置页的既有权限，未细粒度化
- **跨企业总览的导出与定时报告**：价值明确但优先级低
