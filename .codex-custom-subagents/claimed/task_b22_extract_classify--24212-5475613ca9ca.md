# Codex Custom Subagents task handoff v1

Task: task_b22_extract_classify

## 任务：LLM 提取与资料包模块识别（易用性优化计划 B2 任务 B2-2）

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 B2-1 提交（83466ed）。启动时 `cd` 到该目录，git status 确认干净。

### 步骤 1：编写失败测试

新建 `backend/tests/test_onboarding_extract.py`：

```python
import asyncio
from unittest.mock import AsyncMock

from app.services.onboarding_service import extract_candidates, classify_modules


def test_extract_candidates_parses_llm_json(monkeypatch):
    async def fake_llm(messages, ai_config, timeout=120):
        return '{"items": [{"name": "甲醇", "cas_no": "67-56-1"}]}'
    monkeypatch.setattr("app.services.onboarding_service.llm_text_completion", fake_llm)
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = object()  # 系统配置存在
    result = asyncio.run(extract_candidates("chemical", "文本内容", db))
    assert result == [{"name": "甲醇", "cas_no": "67-56-1"}]


def test_classify_modules_parses_llm_json(monkeypatch):
    async def fake_llm(messages, ai_config, timeout=120):
        return '{"modules": ["enterprise_info", "risk_chemical"]}'
    monkeypatch.setattr("app.services.onboarding_service.llm_text_completion", fake_llm)
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = object()
    result = asyncio.run(classify_modules("含企业信息和危化品台账的文档", db))
    assert result == ["enterprise_info", "risk_chemical"]
```

运行确认失败：`cd backend && python -m pytest tests/test_onboarding_extract.py -v`。

### 步骤 2：在 onboarding_service.py 追加提取与模块识别

在 `backend/app/services/onboarding_service.py` 末尾追加（保留现有 compute_completion）：

```python
"""LLM 提取与资料包模块识别。"""
from app.services.ai_config_service import get_system_ai_config
from app.services.llm_client import llm_text_completion
from app.services.risk_ai_service import _parse_ai_json


MODULE_SCHEMA_HINTS = {
    "enterprise_info": "企业名称/统一社会信用代码/法定代表人/地址/行业/经营范围/员工人数等",
    "org_structure": "应急指挥部/总指挥/副总指挥/应急小组及组长成员（姓名电话留空由用户填）",
    "risk_chemical": "风险区域/对象/单元/事件（事故类型、风险等级、触发条件、后果）与危险化学品（名称/CAS/闪点/储量）",
    "resources": "应急物资（类别/名称/规格/数量/位置/责任人）与外部救援力量（单位/距离/电话）",
    "surrounding": "周边单位与敏感目标（名称/方位/距离/类型/主要风险）",
}


async def extract_candidates(module: str, text: str, db) -> list[dict]:
    """按模块 schema 从文本提取候选。返回候选 list[dict]。"""
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise ValueError("系统未配置 AI 模型，请联系管理员")
    hint = MODULE_SCHEMA_HINTS.get(module, "")
    prompt = (
        "你是企业应急预案数据提取助手。请从以下资料中提取结构化数据。\n"
        f"提取目标（模块：{module}）：{hint}\n"
        "要求：只提取资料中明确出现的信息，不得编造；姓名/电话如无明确内容则留空。\n"
        "输出严格 JSON：{\"items\": [...]}，不要输出其他文字。\n\n"
        f"资料内容：\n{text[:12000]}"
    )
    raw = await llm_text_completion(
        [{"role": "system", "content": "你是结构化数据提取器，只输出 JSON。"},
         {"role": "user", "content": prompt}],
        ai_config,
    )
    parsed = _parse_ai_json(raw)
    return parsed.get("items", [])


async def classify_modules(text: str, db) -> list[str]:
    """判断资料文本属于哪些模块，返回模块 key 列表。"""
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise ValueError("系统未配置 AI 模型，请联系管理员")
    known = "、".join(MODULE_SCHEMA_HINTS.keys())
    prompt = (
        "判断以下企业资料属于哪些数据模块。可选模块：" + known + "。\n"
        "输出严格 JSON：{\"modules\": [\"module_key\", ...]}，只输出 JSON。\n\n"
        f"资料内容：\n{text[:12000]}"
    )
    raw = await llm_text_completion(
        [{"role": "system", "content": "你是企业资料分类器，只输出 JSON。"},
         {"role": "user", "content": prompt}],
        ai_config,
    )
    parsed = _parse_ai_json(raw)
    return [m for m in parsed.get("modules", []) if m in MODULE_SCHEMA_HINTS]
```

注意：模块级导入位置按文件实际结构调整（避免循环导入——onboarding_service 不应导入会反向依赖它的模块；若 risk_ai_service 或 llm_client 与 onboarding_service 无循环依赖则模块级导入，否则函数内导入）。

### 步骤 3：运行测试验证通过

运行：`cd backend && python -m pytest tests/test_onboarding_extract.py -v`

预期：2 个测试 PASS。

### 步骤 4：全量后端测试 + Commit

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（与基线一致）。

```bash
git add backend/app/services/onboarding_service.py backend/tests/test_onboarding_extract.py
git commit -m "feat(onboarding): LLM extraction and module classification for imports"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 严格按任务描述 TDD 实现
2. 运行测试验证（步骤 3/4）
3. 提交（步骤 4）
4. 自审：提取/分类函数可用？模块 key 与 MODULE_WEIGHTS 一致？无循环导入？系统配置未配置时报错明确？
5. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、测试结果、提交 SHA、自审发现
