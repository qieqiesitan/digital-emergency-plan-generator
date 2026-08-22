# Codex Custom Subagents task handoff v1

Task: risk_source_fix_2025

## 任务：风险源扩展端点 NameError 修复 + AI 建议 normalize 兜底

### 项目工作目录（所有文件操作与测试在此执行）

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025`

隔离 git 分支 `codex/accident-types-2025`。命令在 PowerShell 中执行；后端命令在 `backend` 子目录执行。前置依赖已提交：`backend/app/services/accident_types.py`。

### 背景

`backend/app/routers/risk_sources_ext.py` 的 4 处使用了未定义的 `PRESET_RISK_CATEGORIES`（模板下载/AI 提问/AI 生成/导入校验），运行时报 NameError（现存 bug）。需改引共享 27 类。同时 `risk_source_migration_service.py` 创建风险事件时事故类型未经归一化，旧值可能再入库。

### 第 1 步：`backend\app\routers\risk_sources_ext.py`

1. 顶部 import 区新增：`from app.services.accident_types import ACCIDENT_TYPES_2025`
2. 4 处 `PRESET_RISK_CATEGORIES` 全部替换为 `ACCIDENT_TYPES_2025`（约 :183 模板下拉、:309 导入校验 set、:521 AI 提问、:683 AI 生成）

### 第 2 步：`backend\app\services\risk_source_migration_service.py`

1. 顶部 import：`from app.services.accident_types import normalize_accident_type`
2. 约 :82 处 `item["suggested_event"] = ai.get("suggested_accident_type") or ai.get("suggested_event") or item["suggested_event"]` 改为：

```python
item["suggested_event"] = normalize_accident_type(
    ai.get("suggested_accident_type") or ai.get("suggested_event") or item["suggested_event"]
)
```

3. 约 :198 创建 RiskEvent 处：`accident_type=mapping.accident_type` 改为 `accident_type=normalize_accident_type(mapping.accident_type)`

### 第 3 步：编写回归测试 `backend\tests\test_risk_sources_ext.py`

按仓库惯例（参考 test_risk_notice_card_api.py：独立 FastAPI 挂载 router + dependency_overrides）：

```python
"""风险源扩展端点回归：模板下载不再 NameError，类别下拉含 27 类。"""
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.database import get_db
from app.dependencies import get_current_user
from app.routers import risk_sources_ext


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(risk_sources_ext.router, prefix="/api/v1")

    async def _get_enterprise_data(enterprise_id, user_id, db):
        return {"name": "甲公司", "industry": "工贸", "business_scope": "", "building_overview": "", "employee_count": 10, "address": ""}

    monkeypatch.setattr(risk_sources_ext, "_get_enterprise_data", _get_enterprise_data)

    async def _current_user():
        return type("U", (), {"id": "u1", "email": "admin@test.com"})()

    async def _db():
        yield None

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_risk_source_template_uses_2025_categories(client):
    resp = client.get("/api/v1/enterprises/e1/risk-sources/template")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    assert ws["A2"].value == "火灾"
    dv = ws.data_validations.dataValidation[0]
    assert "机械致害" in dv.formula1
    assert "锅炉爆炸" not in dv.formula1
```

### 第 4 步：测试 + 提交

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025\backend
python -m pytest tests/test_risk_sources_ext.py -q
```

预期 PASS（新测试先看到失败：NameError → 修复后通过）。再跑相关既有测试：

```powershell
python -m pytest tests/test_risk_source_migration.py -q
```

若该文件不存在，用 `python -m pytest tests/ -k "migration or risk_source" -q` 替代。全绿后提交：

```powershell
cd C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\accident-types-2025
git add backend/app/routers/risk_sources_ext.py backend/app/services/risk_source_migration_service.py backend/tests/test_risk_sources_ext.py
git commit -m "fix(accident-types): repair risk source template NameError, normalize AI suggestions"
```

### 红线

- 只改动上述 3 个文件；不要做无关重构
- 不要更新 TASKS.md；中文保持 UTF-8
- 遇到意外情况先停下来，以 BLOCKED/NEEDS_CONTEXT 汇报具体错误，不要猜测

### 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 红灯（NameError）与绿灯输出摘要、测试结果
- commit SHA（git log -1 --format=%h）
