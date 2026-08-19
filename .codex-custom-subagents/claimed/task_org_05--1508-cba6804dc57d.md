# Codex Custom Subagents task handoff v1

Task: task_org_05

## 目标

实现「企业组织与成员管理」计划任务 5：AI 建树端点（文本通道，不依赖图像识别），按 TDD 完成并提交。

## 工作目录

- **代码与 git 提交目录**：`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\dual-prevention`（分支 `codex/dual-prevention`，HEAD=`9e46acb`）。
- **任务池目录（认领/完成命令 cwd）**：`C:\Users\55061\Documents\数字化预案自动生成 2`。

## 文件

- 修改：`backend/app/services/enterprise_org_service.py`（suggest_org_tree）
- 修改：`backend/app/routers/enterprise_org.py`（POST /org/ai-suggest）
- 测试：`backend/tests/test_enterprise_org.py`（追加，mock LLM）

## 步骤（TDD）

- [ ] **步骤 1：失败测试**（追加）

```python
import json
import pytest
from unittest.mock import AsyncMock, patch
from app.services.enterprise_org_service import suggest_org_tree

@pytest.mark.asyncio
async def test_ai_suggest_org_tree_ok():
    fake = {"nodes": [
        {"id": "d1", "type": "dept", "name": "生产部", "parent_id": None, "members": [{"name": "张三", "position": "班组长"}]},
        {"id": "t1", "type": "team", "name": "甲班", "parent_id": "d1", "members": []},
    ]}
    with patch("app.services.enterprise_org_service.llm_text_completion",
               AsyncMock(return_value=json.dumps(fake, ensure_ascii=False))):
        out = await suggest_org_tree({"industry": "化工", "employee_count": 120}, None)
    assert out["available"] is True
    assert out["nodes"][0]["type"] == "dept"

@pytest.mark.asyncio
async def test_ai_suggest_org_tree_fallback():
    with patch("app.services.enterprise_org_service.llm_text_completion",
               AsyncMock(side_effect=Exception("timeout"))):
        out = await suggest_org_tree({"industry": "化工"}, None)
    assert out["available"] is False
```

- [ ] **步骤 2：确认失败（ModuleNotFoundError 或函数不存在）**
- [ ] **步骤 3：实现**

`suggest_org_tree(enterprise_info, ai_config)`：

- prompt：输入企业基础信息（行业/人数/现有 org_structure 摘要）→ 输出 `{nodes:[{id,type,name,parent_id,members:[{name,position}]}]}`；**不猜邮箱**（members 无邮箱字段）；
- 调 `llm_text_completion(messages, ai_config, timeout=60)` → `_parse_ai_json` 解析 → 缺 `nodes` 抛错 → 异常兜底 `{"available": False, "note": "AI 不可用，请手动维护组织架构"}`；
- 返回 `{"available": True, "nodes": [...]}`。

`POST /enterprises/{id}/org/ai-suggest`：写权限 `_get_owned_ent` → `_get_ai_config`（失败转 None，参考 `risk_ai_service._get_ai_config` 的调用方式）→ 组装 enterprise_info（industry/employee_count/org_structure 摘要）→ 返回 `ApiResponse(data=result)`；`available:false` 仍 200。

- [ ] **步骤 4：通过 + 全量回归**（`python -m pytest tests/test_enterprise_org.py -v` + `tests/ -q`）
- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/enterprise_org_service.py backend/app/routers/enterprise_org.py backend/tests/test_enterprise_org.py
git commit -m "feat(org): AI org tree suggestion (text-only)"
```

不要提交 TASKS.md；消息精确匹配；`git diff --check` 干净。

## 完成协议

最终回复前在任务池目录执行：

```bash
python "C:\Users\55061\.codex\skills\codex-custom-subagents\scripts\claim_task.py" --workspace "C:\Users\55061\Documents\数字化预案自动生成 2" complete --task-id task_org_05 --claim-id <claim_id> --exit-code 0 --summary "AI建树端点完成"
```

最终回复报告：task_id、claim_id、commit SHA、测试结果、自审结论。

## 规则

- 严格 TDD；用 `apply_patch` 编辑；只改列出的 3 个文件；阻塞时停下汇报。
