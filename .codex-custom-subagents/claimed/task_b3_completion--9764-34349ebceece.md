# Codex Custom Subagents task handoff v1

Task: task_b3_completion

## 任务：企业数据完成度聚合（易用性优化计划 B 任务 B3）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 B2 提交（e9a4074）。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：编写失败测试

新建 `backend/tests/test_onboarding_completion.py`：

```python
import asyncio
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.onboarding_service import compute_completion


def test_completion_all_done_returns_100():
    db = AsyncMock()
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = "地址"; ent.industry = "化工"
    ent.org_structure = [{"group_key": "cmd", "group_name": "指挥部",
                          "members": [{"name": "张三", "role": "chief", "phone": "138"}]}]
    ent.surrounding_info = {"nearby_units": [{"name": "加油站"}], "sensitive_targets": []}
    ent.risk_method_config = None

    def fake_execute(stmt):
        res = AsyncMock()
        text = str(stmt)
        if "risk_events" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="e1", chemical_id="c1")]
        elif "hazardous_chemicals" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="c1")]
        elif "emergency_resources" in text:
            res.scalars.return_value.all.return_value = [MagicMock(id="r1")]
        elif "risk_assessment_reports" in text:
            res.scalars.return_value.all.return_value = [MagicMock(status="completed")]
        elif "resource_investigation_reports" in text:
            res.scalars.return_value.all.return_value = [MagicMock(status="completed")]
        else:
            res.scalars.return_value.all.return_value = []
        return res

    db.execute.side_effect = fake_execute
    result = asyncio.run(compute_completion("e1", db))
    assert result["percent"] == 100
    assert all(m["done"] for m in result["modules"])


def test_completion_empty_enterprise():
    db = AsyncMock()
    ent = MagicMock()
    ent.name = "甲公司"; ent.address = ""; ent.industry = ""
    ent.org_structure = []
    ent.surrounding_info = {"nearby_units": [], "sensitive_targets": []}
    ent.risk_method_config = None
    db.execute.side_effect = lambda stmt: AsyncMock(
        scalars=lambda: AsyncMock(all=lambda: [])
    )
    result = asyncio.run(compute_completion("e1", db))
    assert result["percent"] == 0
```

运行确认失败：`cd backend && python -m pytest tests/test_onboarding_completion.py -v`。

### 步骤 2：实现完成度服务

新建 `backend/app/services/onboarding_service.py`：

```python
"""企业数据完成度聚合（6 模块加权）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enterprise import Enterprise
from app.models.risk_management import RiskEvent
from app.models.hazardous_chemicals import HazardousChemical
from app.models.enterprise import EmergencyResource
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport

MODULE_WEIGHTS = {
    "enterprise_info": 10,
    "org_structure": 15,
    "risk_chemical": 30,
    "resources": 15,
    "surrounding": 10,
    "reports": 20,
}

MODULE_LABELS = {
    "enterprise_info": "企业信息",
    "org_structure": "组织架构",
    "risk_chemical": "风险与危化品",
    "resources": "应急资源",
    "surrounding": "周边环境",
    "reports": "报告",
}


async def compute_completion(enterprise_id: str, db: AsyncSession) -> dict:
    """返回 {percent, modules: [{key,label,weight,done}]}。"""
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        raise ValueError("企业不存在")

    done = {}
    done["enterprise_info"] = bool(ent.name and ent.address and ent.industry)
    done["org_structure"] = _org_done(ent.org_structure)

    events = (await db.execute(select(RiskEvent).where(RiskEvent.enterprise_id == enterprise_id))).scalars().all()
    chemicals = (await db.execute(select(HazardousChemical).where(HazardousChemical.enterprise_id == enterprise_id))).scalars().all()
    done["risk_chemical"] = bool(events) or bool(chemicals)

    resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == enterprise_id))).scalars().all()
    done["resources"] = bool(resources)

    surrounding = ent.surrounding_info or {}
    done["surrounding"] = bool(surrounding.get("nearby_units")) or bool(surrounding.get("sensitive_targets"))

    ra = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id,
        RiskAssessmentReport.status == "completed",
    ))).scalars().all()
    ri = (await db.execute(select(ResourceInvestigationReport).where(
        ResourceInvestigationReport.enterprise_id == enterprise_id,
        ResourceInvestigationReport.status == "completed",
    ))).scalars().all()
    done["reports"] = bool(ra) and bool(ri)

    total = 0
    modules = []
    for key, weight in MODULE_WEIGHTS.items():
        d = done[key]
        if d:
            total += weight
        modules.append({"key": key, "label": MODULE_LABELS[key], "weight": weight, "done": d})
    return {"percent": total, "modules": modules}


def _org_done(org_structure: list | None) -> bool:
    for group in org_structure or []:
        for member in group.get("members", []):
            if member.get("name"):
                return True
    return False
```

注意：`RiskEvent` 是否直接有 `enterprise_id` 列——先读 `backend/app/models/risk_management.py` 确认。若 RiskEvent 无 enterprise_id（通过 RiskObject 间接归属企业），则查询改为：

```python
from app.models.risk_management import RiskEvent, RiskObject
events = (await db.execute(
    select(RiskEvent).join(RiskObject, RiskEvent.object_id == RiskObject.id).where(RiskObject.enterprise_id == enterprise_id)
)).scalars().all()
```

按实际模型调整并保持测试可过（测试的 fake_execute 只按 "risk_events" 字符串匹配，join 查询的 str 仍含 "risk_events" 表名）。

### 步骤 3：新增 completion 接口 + 企业列表扩展

新建 `backend/app/routers/onboarding.py`：

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import ApiResponse
from app.services.onboarding_service import compute_completion

router = APIRouter(tags=["Onboarding"])


@router.get("/enterprises/{enterprise_id}/completion", response_model=ApiResponse[dict])
async def get_enterprise_completion(
    enterprise_id: str,
    _=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await compute_completion(enterprise_id, db)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return ApiResponse(data=data)
```

`backend/app/routers/enterprises.py` 的 `list_enterprises`：为每行计算完成度并写入响应：

```python
from app.services.onboarding_service import compute_completion
items = []
for e in rows:
    item = _build_response(e, event_counts.get(e.id, 0))
    item.completion = await compute_completion(e.id, db)
    items.append(item)
```

`backend/app/schemas/enterprise.py` 的 `EnterpriseResponse` 增加 `completion: dict | None = None`。

注意：检查 `_build_response` 返回的是 ORM 还是 dict——若返回 dict，需要把 completion 放进 dict；若返回 pydantic 模型，用 `item.completion = ...`。按实际调整。还需确认 `onboarding.py` 是否已存在（B2-4 会扩展它，本任务先创建基础版；若已存在则追加）。检查 main.py 是否注册该 router（若无则注册）。

### 步骤 4：运行测试验证通过

运行：`cd backend && python -m pytest tests/test_onboarding_completion.py -v`

预期：2 个测试 PASS。

### 步骤 5：全量后端测试 + Commit

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（与基线一致）。

```bash
git add backend/app/services/onboarding_service.py backend/app/routers/onboarding.py backend/app/routers/enterprises.py backend/app/schemas/enterprise.py backend/tests/test_onboarding_completion.py backend/app/main.py
git commit -m "feat(onboarding): enterprise data completion aggregation endpoint"
```

## 上下文

- B1/B2 已完成（AI 配置系统级、危化品关联）。onboarding_service.py 是新建（B2-2/B2-4 会继续扩展它）。
- 现有代码：Enterprise 模型（name/address/industry/org_structure/surrounding_info）、RiskEvent/RiskObject（risk_management.py）、HazardousChemical、EmergencyResource、RiskAssessmentReport/ResourceInvestigationReport（ReportBase：enterprise_id/status）。
- 企业列表接口 enterprises.py list_enterprises 已有 `_build_response(e, risk_events_count)`。

## 开始之前

对需求/方案/依赖有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述 TDD 实现（先确认 RiskEvent 是否有 enterprise_id 再定查询）
2. 运行测试验证（步骤 4/5）
3. 提交（步骤 5）
4. 自审：完成度算法与规格 6.6 权重一致？接口/列表 completion 字段可用？onboarding router 已注册？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、测试结果、提交 SHA、自审发现、任何疑虑
