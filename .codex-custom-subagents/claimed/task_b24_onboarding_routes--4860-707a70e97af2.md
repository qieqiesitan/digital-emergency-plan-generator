# Codex Custom Subagents task handoff v1

Task: task_b24_onboarding_routes

## 任务：引导接口（candidates / import / import-batch）——易用性优化计划 B2 任务 B2-4

你是一个实现子智能体。严格按以下步骤在指定 worktree 内完成 TDD 实现并提交。不要修改任务范围之外的文件。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`

分支 `codex/usability-overhaul`，当前 HEAD 应包含 B2-3 提交（60f5ba6）。启动时 `cd` 到该目录，git status 确认干净。

### 背景

- `backend/app/routers/onboarding.py` 已存在（B3 创建），含 `GET /enterprises/{id}/completion`（已按用户隔离）。
- `backend/app/services/onboarding_service.py` 已有 `extract_candidates` / `classify_modules` / `generate_org_candidates` / `_get_ai_config_or_400`。
- `backend/app/services/file_parser.py` 已有 `parse_file_text`。
- 本任务追加三个端点：POST /onboarding/candidates、POST /onboarding/import、POST /onboarding/import/batch。

### 步骤 1：编写失败测试（追加到 test_onboarding_extract.py）

在 `backend/tests/test_onboarding_extract.py` 追加：

```python
from app.routers.onboarding import build_candidates_request


def test_build_candidates_request_wraps_overview():
    req = build_candidates_request("企业概况", "生产甲醇、乙醇，有储罐区")
    assert req.answers[0].question == "企业概况"
    assert req.answers[0].answer == "生产甲醇、乙醇，有储罐区"
```

运行确认失败：`cd backend && python -m pytest tests/test_onboarding_extract.py -v`。

### 步骤 2：实现引导路由

在 `backend/app/routers/onboarding.py` 追加（保留 completion 端点）：

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.common import ApiResponse
from app.services.file_parser import parse_file_text
from app.services.onboarding_service import (
    extract_candidates,
    classify_modules,
    generate_org_candidates,
    get_enterprise_brief,
)
from app.routers.hazardous_chemicals import AIGenerateRequest, AIAnswerInput


class CandidatesBody(BaseModel):
    enterprise_id: str
    module: str
    overview: str = ""
    existing_keys: list[str] = []


class ImportResult(BaseModel):
    module: str
    candidates: list[dict]
    source: str


def build_candidates_request(question: str, answer: str) -> AIGenerateRequest:
    """把一句概况包装成现有 AI 生成接口的 answers 结构。"""
    return AIGenerateRequest(answers=[AIAnswerInput(question_id="q0", question=question, answer=answer)])


@router.post("/onboarding/candidates", response_model=ApiResponse[dict])
async def onboarding_candidates(
    body: CandidatesBody,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """统一候选生成：org 走新增生成；其它模块由前端直接调用现有模块生成接口。"""
    if body.module == "org":
        brief = await get_enterprise_brief(body.enterprise_id, db)
        items = await generate_org_candidates(brief, db)
        return ApiResponse(data={"items": items})
    raise HTTPException(400, f"模块 {body.module} 请在前端接入现有生成接口")


@router.post("/onboarding/import", response_model=ApiResponse[ImportResult])
async def onboarding_import(
    module: str = "auto",
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    try:
        text = parse_file_text(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        target = module if module != "auto" else (await classify_modules(text, db))[0]
    except (ValueError, IndexError) as e:
        raise HTTPException(400, str(e) if isinstance(e, ValueError) else "未能识别资料所属模块")
    candidates = await extract_candidates(target, text, db)
    return ApiResponse(data=ImportResult(module=target, candidates=candidates, source=file.filename or ""))


@router.post("/onboarding/import/batch", response_model=ApiResponse[list[ImportResult]])
async def onboarding_import_batch(
    files: list[UploadFile] = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = []
    for file in files:
        data = await file.read()
        try:
            text = parse_file_text(file.filename or "", data)
        except ValueError as e:
            raise HTTPException(400, str(e))
        modules = await classify_modules(text, db)
        if not modules:
            continue
        for mod in modules:
            candidates = await extract_candidates(mod, text, db)
            results.append(ImportResult(module=mod, candidates=candidates, source=file.filename or ""))
    return ApiResponse(data=results)
```

`get_enterprise_brief` 追加到 `backend/app/services/onboarding_service.py`：

```python
async def get_enterprise_brief(enterprise_id: str, db) -> dict:
    from app.models.enterprise import Enterprise
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "企业不存在")
    return {
        "name": ent.name, "industry": ent.industry,
        "business_scope": ent.business_scope, "employee_count": ent.employee_count,
    }
```

注意：
- 现有 onboarding.py 的导入/结构以实际为准，合并导入（勿重复 import）。
- `ImportResult` 的 `candidates: list[dict]` 在 pydantic v2 用 `list[dict]` 合法。
- candidates 端点的 org 分支应校验企业归属（按 current_user 过滤，非本人 404）——参照 completion 端点模式；`get_enterprise_brief` 若在企业归属校验后调用可传已加载实例或直接按 user 过滤查询。实现时确保 org 候选生成不能跨企业。
- 前端计划：org 模块由本端点服务；risk_chemical/resources/surrounding 由前端直接调现有模块生成接口（本端点对非 org 返回 400 提示）。

### 步骤 3：运行测试验证通过

运行：`cd backend && python -m pytest tests/test_onboarding_extract.py -v`

预期：全部 PASS（含新增 build_candidates_request 测试）。

### 步骤 4：全量后端测试 + Commit

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS（与基线一致）。

```bash
git add backend/app/routers/onboarding.py backend/app/services/onboarding_service.py backend/tests/test_onboarding_extract.py
git commit -m "feat(onboarding): candidate orchestration and file import endpoints"
```

## 开始之前

对需求有不清楚的地方，现在就问（报告 NEEDS_CONTEXT），不要猜测。

## 你的工作

1. 先读 onboarding.py / onboarding_service.py 确认现状（completion 端点、helper 签名）
2. 按步骤 TDD 实现
3. 运行测试验证（步骤 3/4）
4. 提交（步骤 4）
5. 自审：org 候选企业归属校验到位？import 错误语义（400）？batch 多文件循环正确？无重复导入？
6. 汇报

## 汇报格式

- 状态：DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- 修改明细、测试结果、提交 SHA、自审发现
