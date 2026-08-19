# Codex Custom Subagents task handoff v1

Task: task_11_ai_suggestion

## 目标

实现「风险分级管控增强（A 阶段）」任务 11：AI 双等级参数建议（文本通道，不依赖图像识别），按 TDD 完成并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD 以任务 10 复审后实际为准）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 背景

- 规格 A §5.2 方式三：AI 双等级参数建议（文本进/出，DeepSeek `llm_text_completion`）；失败降级不阻塞；
- 任务 5 已实现 conversion-reference 端点并加了事件归属校验（risk_events 无 enterprise_id 列，用 object/unit 链校验）——本端点复用同样模式；
- `_get_ai_config`/`_parse_ai_json` 在 `risk_ai_service`；`llm_text_completion` 在 `llm_client`；
- 前端 service 惯例：箭头函数 + `.then(r => r.data.data)` 解包；表单已有折算参考按钮（任务 5）。

## 文件

- 创建：`backend/app/services/risk_dual_ai_service.py`
- 修改：`backend/app/routers/risk_management.py`（AI 建议端点）
- 修改：`frontend/src/components/enterprise/RiskEventForm.tsx`（「AI 建议参数」按钮）
- 修改：`frontend/src/services/riskManagementService.ts`（getAiDualLevelSuggestion）
- 测试：`backend/tests/test_risk_dual_level.py`（追加）+ 前端 service 测试（可选）

## 步骤（TDD）

- [ ] **步骤 1：失败测试（mock LLM）**（`backend/tests/test_risk_dual_level.py` 追加）

```python
import json
import pytest
from unittest.mock import AsyncMock, patch
from app.services.risk_dual_ai_service import suggest_dual_level

@pytest.mark.asyncio
async def test_suggest_dual_level_ok():
    fake = {"inherent": {"risk_level": "重大", "risk_score": "D=270"},
            "current": {"risk_level": "一般", "risk_score": "D=21"}, "note": "报警器+联锁降低L"}
    with patch("app.services.risk_dual_ai_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(fake, ensure_ascii=False))):
        out = await suggest_dual_level("储罐区可燃气体泄漏，已配报警器与联锁", {}, None)
    assert out["available"] is True
    assert out["current"]["risk_level"] == "一般"

@pytest.mark.asyncio
async def test_suggest_dual_level_fallback():
    with patch("app.services.risk_dual_ai_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await suggest_dual_level("描述", {}, None)
    assert out["available"] is False
```

- [ ] **步骤 2：运行测试验证失败**

在 `backend` 目录 `python -m pytest tests/test_risk_dual_level.py::test_suggest_dual_level_ok -v`
预期：FAIL（模块不存在）

- [ ] **步骤 3：实现服务**（`backend/app/services/risk_dual_ai_service.py`）

按计划文本实现 `suggest_dual_level(description, measures_text, ai_config)`：拼 prompt（固有/现有参数与等级 JSON）、调 `llm_text_completion(messages, ai_config, timeout=60)`、`_parse_ai_json` 解析、缺键抛错、异常兜底返回 `{"available": False, "note": "AI 不可用，请手动评估或使用自动折算参考"}`。

- [ ] **步骤 4：实现端点**（`backend/app/routers/risk_management.py`）

`POST /events/{event_id}/ai-dual-level-suggestion`：

- `_get_ent` 企业归属校验；
- 事件查询 + **归属校验**（复用任务 5 conversion-reference 的 object/unit 链校验模式：事件无 enterprise_id 列，经 object/unit 链确认属于该企业，否则 404「风险事件不存在」；如已有可复用辅助函数则调用）；
- `ai_config = await _get_ai_config(current_user.id, db)`（失败/未配置由服务兜底）；
- `measures_text` 由 `event.measures` 拼接（measure_category:description）；
- 返回 `ApiResponse(data=result)`；
- 测试：端点成功（mock `suggest_dual_level` 或 LLM）、跨企业 404、AI 失败降级（`available: false` 仍 200）。

- [ ] **步骤 5：前端接入**

`riskManagementService.ts`（按惯例箭头函数 + 解包）：

```typescript
export const getAiDualLevelSuggestion = (enterpriseId: string, eventId: string) =>
  api.post(`/enterprises/${enterpriseId}/risk-management/events/${eventId}/ai-dual-level-suggestion`).then(r => r.data.data);
```

`RiskEventForm.tsx`：在折算参考按钮旁加「AI 建议参数」按钮（无 eventId 时禁用并提示先保存）；点击调接口 → Modal 展示固有/现有建议对比（等级+分值+note）→「采用」把建议固有/现有等级填入对应区块（用户仍可改，沿用任务 5 的采用路径）；`available === false` 时展示降级文案（不阻塞表单）。

- [ ] **步骤 6：门禁**

后端：`python -m pytest tests/test_risk_dual_level.py tests/test_risk_conversion_api.py -v` 全部 PASS；`python -m pytest tests/ -q` 无回归。
前端：`npx tsc -b`、eslint（改动文件）、`npx vitest run` 全部通过；`git diff --check` 干净。

- [ ] **步骤 7：Commit**

```bash
git add backend/app/services/risk_dual_ai_service.py backend/app/routers/risk_management.py backend/tests/test_risk_dual_level.py frontend/src/components/enterprise/RiskEventForm.tsx frontend/src/services/riskManagementService.ts
git commit -m "feat(risk): AI dual-level parameter suggestion (text-only)"
```

不要提交 TASKS.md；消息精确匹配。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_11_ai_suggestion --claim-id <claim_id> --exit-code 0 --summary "AI双等级参数建议完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试/门禁结果、自审结论。

## 规则

- 严格 TDD；用 `apply_patch` 编辑；只改列出的文件；阻塞时停下汇报。
