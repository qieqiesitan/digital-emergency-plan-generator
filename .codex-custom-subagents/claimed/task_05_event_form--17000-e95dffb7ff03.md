# Codex Custom Subagents task handoff v1

Task: task_05_event_form

## 目标

实现「风险分级管控增强（A 阶段）」任务 5：风险事件表单双参数区块（固有/现有）+ 管控层级 + 自动折算参考（先补后端端点，再接前端），按 TDD 完成并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，当前 HEAD=`09d5b0a`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 背景（已核实）

- 任务 3 已给 `RiskEventCreate/Update/Response` 加 `inherent_risk_level/inherent_risk_score/control_level`，路由已持久化并校验；
- 任务 4 已实现 `risk_conversion_service`（parse_score/combine_factor/conversion_reference）与 `level_from_score`，但**没有端点**；
- `MethodPreviewRequest` 当前为 `{method_id, params}`，预览端点调用 `compute_risk`；
- 前端项目约定：vitest 仅覆盖 service/store/utils（无 jsdom），组件靠 tsc/lint + 手工冒烟。

## 文件

### 后端
- 修改：`backend/app/schemas/risk_management.py`（MethodPreviewRequest 加 scenario）
- 修改：`backend/app/routers/risk_management.py`（预览端点透传 scenario；新增 conversion-reference 端点）
- 测试：`backend/tests/test_risk_dual_level.py` 或新文件 `backend/tests/test_risk_conversion_api.py`（端点测试）

### 前端
- 修改：`frontend/src/types/riskManagement.ts`（RiskEvent/RiskEventFormValues 加 3 字段）
- 修改：`frontend/src/services/riskManagementService.ts`（previewRiskMethod 加 scenario；新增 previewRiskConversion）
- 修改：`frontend/src/services/riskManagementService.test.ts`
- 修改：`frontend/src/components/enterprise/RiskEventForm.tsx`（固有区块 + 管控层级 + 折算参考按钮）

## 步骤（后端先，TDD）

- [ ] **步骤 1：端点失败测试**

在 `backend/tests/test_risk_conversion_api.py` 写端点测试（复用项目 API 测试模式：独立 FastAPI app + dependency_overrides；`get_dict_map` 用 monkeypatch 成 `AsyncMock` 返回 `{"engineering": {"value": {"factor": 0.5}}, "mode": {"value": {"mode": "min"}}}`；event 查询返回 `RiskEvent(method_type="LS", inherent_risk_score="R=20")`；方法配置返回 `{"risk_thresholds": [{"min":1,"max":9,"level":"低"},{"min":10,"max":14,"level":"一般"},{"min":15,"max":19,"level":"较大"},{"min":20,"max":25,"level":"重大"}]}`）：

```python
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.database import get_db
from app.dependencies import get_current_user
from app.models.risk_management import RiskEvent
from app.routers import risk_management
from app.services import data_dict_service

def _app(event, factors):
    app = FastAPI()
    app.include_router(risk_management.router, prefix="/api/v1")
    async def _db():
        db = MagicMock()
        async def execute(stmt, *a, **k):
            res = MagicMock()
            text = str(stmt)
            if "risk_events" in text and "id =" in text:
                res.scalar_one_or_none.return_value = event
            elif "enterprises" in text:
                ent = MagicMock(); ent.id = "e1"; ent.user_id = "u1"
                res.scalar_one_or_none.return_value = ent
            else:
                res.scalar_one_or_none.return_value = None
            return res
        db.execute = AsyncMock(side_effect=execute)
        db.get = AsyncMock(return_value=event)
        return db
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="u1")
    return TestClient(app)

def test_conversion_reference_endpoint(monkeypatch):
    event = RiskEvent(id="ev1", accident_type="火灾", method_type="LS",
                      method_params={"l": 4, "s": 5}, risk_level="重大", risk_score="R=20",
                      inherent_risk_level="重大", inherent_risk_score="R=20")
    factors = {"engineering": {"value": {"factor": 0.5}},
               "mode": {"value": {"mode": "min"}}}
    monkeypatch.setattr(data_dict_service, "get_dict_map", AsyncMock(return_value=factors))
    client = _app(event, factors)
    resp = client.get("/api/v1/enterprises/e1/risk-management/events/ev1/conversion-reference")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["factor"] == 0.5
    assert data["reference_score"] == 10.0
    assert data["reference_level"] == "一般"
```

- [ ] **步骤 2：运行测试验证失败**

在 `backend` 目录 `python -m pytest tests/test_risk_conversion_api.py -v`
预期：FAIL（端点不存在，404）

- [ ] **步骤 3：实现端点与 scenario**

`backend/app/schemas/risk_management.py`：`MethodPreviewRequest` 加 `scenario: str = "current"`。

`backend/app/routers/risk_management.py`：

- 预览端点把 `body.scenario` 透传（当前 `compute_risk` 不区分固有/现有，scenario 仅作透传保留，为任务 11 AI 建议预留；如无消费点可先在响应加 `scenario` 回显或忽略，保持向后兼容）；
- 新增端点：

```python
@router.get("/events/{event_id}/conversion-reference", response_model=ApiResponse[dict])
async def event_conversion_reference(enterprise_id: str, event_id: str,
                                     current_user=Depends(get_current_user), db=Depends(get_db)):
    await _get_ent(enterprise_id, current_user.id, db)
    event = (await db.execute(select(RiskEvent).where(RiskEvent.id == event_id))).scalar_one_or_none()
    if not event:
        raise HTTPException(404, "风险事件不存在")
    from app.services.data_dict_service import get_dict_map
    from app.services.risk_conversion_service import conversion_reference
    factors = await get_dict_map(db, enterprise_id, "measure_factors")
    mode = (factors.get("mode") or {}).get("value", {}).get("mode", "min")
    factor_map = {code: entry["value"]["factor"]
                  for code, entry in factors.items() if code != "mode" and entry.get("value", {}).get("factor") is not None}
    config = await get_active_method_config(db, enterprise_id, event.method_type)
    thresholds = (config or {}).get("risk_thresholds", [])
    result = conversion_reference(event.inherent_risk_score or "", factor_map, mode, thresholds, event.method_type)
    return ApiResponse(data=result)
```

- [ ] **步骤 4：运行测试验证通过**

在 `backend` 目录 `python -m pytest tests/test_risk_conversion_api.py tests/test_risk_conversion.py -v`，预期全部 PASS；`python -m pytest tests/ -q` 无回归。

## 步骤（前端）

- [ ] **步骤 5：类型与 service**

`frontend/src/types/riskManagement.ts`：`RiskEvent` 与 `RiskEventFormValues` 增加 `inherent_risk_level: string | null; inherent_risk_score: string | null; control_level: string | null`。

`frontend/src/services/riskManagementService.ts`：

```typescript
export async function previewRiskMethod(enterpriseId: string, payload: { method_id: string; params: Record<string, number>; scenario?: "inherent" | "current" }) {
  return api.post(`/enterprises/${enterpriseId}/risk-management/methods/preview`, payload);
}
export async function previewRiskConversion(enterpriseId: string, eventId: string) {
  return api.get(`/enterprises/${enterpriseId}/risk-management/events/${eventId}/conversion-reference`);
}
```

（按现有 api 封装风格调整；`previewRiskMethod` 保持既有签名兼容，scenario 可选。）

`frontend/src/services/riskManagementService.test.ts`：给 previewRiskMethod 补「scenario 透传」断言；给 previewRiskConversion 补「请求 URL 正确」断言。

- [ ] **步骤 6：事件表单**

`frontend/src/components/enterprise/RiskEventForm.tsx`（先读现有表单结构，按其模式扩展）：

- 评估方法为 LS/LEC/COAL_LS 时：在现有参数区上方新增「固有风险（不考虑管控措施）」参数组（同字段命名规则，如 `inherentL/inherentS` 或 `inherentL/inherentE/inherentC`，按方法渲染），提交时组装为 `inherent_params` 与现有 params 一起保存；后端保存逻辑沿用任务 3（inherent_risk_level/score 由后端计算或表单回传，按现有事件提交契约实现，保证保存后 response 含固有等级）；
- DIRECT 方法：渲染「固有等级」Select（重大/较大/一般/低）；
- 「管控层级」Select（企业/部门/班组/岗位），placeholder「按现有等级自动映射」；
- 「自动折算参考」按钮：调 `previewRiskConversion`，结果卡片展示 factor/reference_score/reference_level，「采用为现有风险」把参考等级/分值填入现有区块（用户仍可改）；接口失败提示降级文案。

若表单提交契约与后端 Create 不匹配（如等级由后端计算），以「保存后能持久化 inherent_* 与 control_level 且回显正确」为准实现，必要时同步调整后端 create/update 的字段接收（不改变已通过的校验行为）。

- [ ] **步骤 7：前端门禁**

在 `frontend` 目录：`npx tsc -b`、`npx eslint src/components/enterprise/RiskEventForm.tsx src/services/riskManagementService.ts src/types/riskManagement.ts`、`npx vitest run src/services/riskManagementService.test.ts`，全部通过。

## Commit（可分两个：后端、前端）

在 `.worktrees\dual-prevention` 内：

```bash
git add backend/app/schemas/risk_management.py backend/app/routers/risk_management.py backend/tests/test_risk_conversion_api.py
git commit -m "feat(risk): add conversion-reference endpoint and preview scenario"

git add frontend/src/types/riskManagement.ts frontend/src/services/riskManagementService.ts frontend/src/services/riskManagementService.test.ts frontend/src/components/enterprise/RiskEventForm.tsx
git commit -m "feat(risk): dual-parameter inherent/current form with conversion reference"
```

不要提交 TASKS.md；`git diff --check` 干净。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_05_event_form --claim-id <claim_id> --exit-code 0 --summary "事件表单双区块+折算参考完成"
```

最终回复报告：task_id、claim_id、commit SHA（两个）、测试结果、门禁结果、自审结论。

## 规则

- 严格 TDD（后端）；用 `apply_patch` 编辑；只改列出的文件；阻塞时停下汇报。
