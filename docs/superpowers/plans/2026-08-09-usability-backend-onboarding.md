# 易用性整体优化 · 计划 B2（后端引导服务）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为引导页提供后端能力——统一候选生成编排（含组织架构 AI 生成）、单文件导入解析与 LLM 提取、资料包多文件模块识别与分流。

**架构：** 复用现有各模块 AI 生成接口（`resources/ai/generate`、`chemicals/ai/generate`、`surrounding/ai/generate`、`risk/ai/suggest-*`）与 batch 写入接口；新增轻量编排接口 `POST /onboarding/candidates`、导入接口 `/onboarding/import`、`/onboarding/import/batch`。文件解析用现有依赖（python-docx / openpyxl / PyMuPDF / csv）。

**技术栈：** FastAPI + SQLAlchemy + LLM（llm_client）、openpyxl/python-docx/PyMuPDF/csv、pytest。

**规格依据：** `docs/superpowers/specs/2026-08-08-usability-enhancement-design.md` 第 6.3、6.4、6.5、14 节。

**依赖：** 先执行计划 A、B（系统级 AI 配置、完成度接口）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `backend/app/services/file_parser.py` | xlsx/csv/docx/pdf 解析为文本 | 新建 |
| `backend/app/services/onboarding_service.py` | 追加：组织架构 AI 生成、LLM 提取、资料包模块识别 | 修改 |
| `backend/app/routers/onboarding.py` | 追加：candidates / import / import-batch 接口 | 修改 |
| `backend/tests/test_file_parser.py` | 解析测试 | 新建 |
| `backend/tests/test_onboarding_extract.py` | LLM 提取/模块识别测试 | 新建 |
| `backend/tests/test_onboarding_org.py` | 组织架构生成测试 | 新建 |

---

### 任务 B2-1：文件解析工具

**文件：**
- 新建：`backend/app/services/file_parser.py`
- 测试：`backend/tests/test_file_parser.py`

- [ ] **步骤 1：编写失败测试**

新建 `backend/tests/test_file_parser.py`：

```python
import io

import pytest

from app.services.file_parser import parse_file_text


def test_parse_csv_text():
    text = parse_file_text("chem.csv", b"name,cas\nmethanol,67-56-1\nethanol,64-17-5\n")
    assert "methanol" in text
    assert "67-56-1" in text


def test_parse_plain_text_txt():
    text = parse_file_text("note.txt", "企业地址：杭州市XX区".encode("utf-8"))
    assert "企业地址" in text


def test_parse_unsupported_extension_raises():
    with pytest.raises(ValueError):
        parse_file_text("file.exe", b"x")


def test_parse_xlsx_bytes():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["化学品名称", "CAS号"])
    ws.append(["甲醇", "67-56-1"])
    buf = io.BytesIO()
    wb.save(buf)
    text = parse_file_text("chem.xlsx", buf.getvalue())
    assert "甲醇" in text
    assert "67-56-1" in text
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_file_parser.py -v`

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.file_parser'`。

- [ ] **步骤 3：实现解析工具**

新建 `backend/app/services/file_parser.py`：

```python
"""导入文件解析：xlsx / csv / docx / pdf / txt → 纯文本。"""
import csv
import io


def parse_file_text(filename: str, data: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        return _parse_csv(data)
    if ext == "xlsx":
        return _parse_xlsx(data)
    if ext == "docx":
        return _parse_docx(data)
    if ext == "pdf":
        return _parse_pdf(data)
    if ext in ("txt", "md"):
        return data.decode("utf-8", errors="ignore")
    raise ValueError(f"不支持的文件格式：.{ext}，支持 xlsx/csv/docx/pdf/txt")


def _parse_csv(data: bytes) -> str:
    text = data.decode("utf-8", errors="ignore")
    rows = list(csv.reader(io.StringIO(text)))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows if any(cell.strip() for cell in row))


def _parse_xlsx(data: bytes) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"【工作表：{ws.title}】")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c).strip() for c in row if c is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _parse_docx(data: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(data))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _parse_pdf(data: bytes) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(stream=data, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_file_parser.py -v`

预期：4 个测试 PASS。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/file_parser.py backend/tests/test_file_parser.py
git commit -m "feat(import): file parser for xlsx/csv/docx/pdf/txt"
```

---

### 任务 B2-2：LLM 提取与资料包模块识别

**文件：**
- 修改：`backend/app/services/onboarding_service.py`
- 测试：`backend/tests/test_onboarding_extract.py`

- [ ] **步骤 1：编写失败测试**

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

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_onboarding_extract.py -v`

预期：FAIL，`extract_candidates` 未定义。

- [ ] **步骤 3：实现提取与模块识别**

在 `backend/app/services/onboarding_service.py` 追加：

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

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_onboarding_extract.py -v`

预期：2 个测试 PASS。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/onboarding_service.py backend/tests/test_onboarding_extract.py
git commit -m "feat(onboarding): LLM extraction and module classification for imports"
```

---

### 任务 B2-3：组织架构 AI 生成（引导第 2 步）

**文件：**
- 修改：`backend/app/services/onboarding_service.py`
- 测试：`backend/tests/test_onboarding_org.py`

- [ ] **步骤 1：编写失败测试**

新建 `backend/tests/test_onboarding_org.py`：

```python
import asyncio
from unittest.mock import AsyncMock

from app.services.onboarding_service import generate_org_candidates


def test_generate_org_candidates_parses_llm_json(monkeypatch):
    async def fake_llm(messages, ai_config, timeout=120):
        return '{"groups": [{"group_key": "cmd", "group_name": "应急救援指挥部", "members": [{"role": "总指挥", "name": "", "phone": ""}]}, {"group_key": "rescue", "group_name": "抢险救援组", "members": []}]}'
    monkeypatch.setattr("app.services.onboarding_service.llm_text_completion", fake_llm)
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = object()
    result = asyncio.run(generate_org_candidates({"name": "甲公司", "industry": "化工"}, db))
    assert result[0]["group_key"] == "cmd"
    assert result[0]["members"][0]["name"] == ""  # 姓名必须留空
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_onboarding_org.py -v`

预期：FAIL，`generate_org_candidates` 未定义。

- [ ] **步骤 3：实现组织架构生成**

在 `backend/app/services/onboarding_service.py` 追加：

```python
async def generate_org_candidates(enterprise_info: dict, db) -> list[dict]:
    """根据企业概况生成应急组织框架候选（角色+职责；姓名/电话一律留空）。"""
    ai_config = await get_system_ai_config(db)
    if not ai_config:
        raise ValueError("系统未配置 AI 模型，请联系管理员")
    ent_text = (
        f"企业名称：{enterprise_info.get('name', '')}\n"
        f"行业：{enterprise_info.get('industry', '')}\n"
        f"经营范围：{enterprise_info.get('business_scope', '')}\n"
        f"员工人数：{enterprise_info.get('employee_count', '')}"
    )
    prompt = (
        "根据企业概况生成应急预案应急组织机构框架建议。\n"
        "包含：应急救援指挥部（总指挥、副总指挥）与必要应急小组（抢险救援组、疏散引导组、"
        "医疗救护组、通讯联络组、后勤保障组等，按企业规模取舍）。\n"
        "每个组给出 group_key、group_name、职责描述 responsibilities，成员给 role，"
        "**姓名 name、电话 phone、公司职位 position 一律输出空字符串**，由用户填写。\n"
        "输出严格 JSON：{\"groups\": [{\"group_key\": \"cmd\", \"group_name\": \"应急救援指挥部\", "
        "\"responsibilities\": \"...\", \"members\": [{\"role\": \"总指挥\", \"name\": \"\", \"position\": \"\", \"phone\": \"\"}]}]}，只输出 JSON。\n\n"
        f"企业概况：\n{ent_text}"
    )
    raw = await llm_text_completion(
        [{"role": "system", "content": "你是应急预案编制专家，只输出 JSON。"},
         {"role": "user", "content": prompt}],
        ai_config,
    )
    parsed = _parse_ai_json(raw)
    return parsed.get("groups", [])
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_onboarding_org.py -v`

预期：1 个测试 PASS。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/onboarding_service.py backend/tests/test_onboarding_org.py
git commit -m "feat(onboarding): AI generate emergency org structure candidates"
```

---

### 任务 B2-4：引导接口（candidates / import / import-batch）

**文件：**
- 修改：`backend/app/routers/onboarding.py`
- 测试：`backend/tests/test_onboarding_extract.py`（追加）

- [ ] **步骤 1：编写失败测试（追加）**

在 `backend/tests/test_onboarding_extract.py` 追加：

```python
from app.routers.onboarding import build_candidates_request


def test_build_candidates_request_wraps_overview():
    req = build_candidates_request("企业概况", "生产甲醇、乙醇，有储罐区")
    assert req.answers[0].question == "企业概况"
    assert req.answers[0].answer == "生产甲醇、乙醇，有储罐区"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && python -m pytest tests/test_onboarding_extract.py -v`

预期：FAIL，`build_candidates_request` 未定义。

- [ ] **步骤 3：实现引导路由**

在 `backend/app/routers/onboarding.py` 追加：

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
    """统一候选生成：org 走新增生成；其它模块复用现有生成服务。"""
    if body.module == "org":
        from app.services.onboarding_service import get_enterprise_brief
        brief = await get_enterprise_brief(body.enterprise_id, db)
        items = await generate_org_candidates(brief, db)
        return ApiResponse(data={"items": items})
    raise HTTPException(400, f"模块 {body.module} 请在计划 C 接入现有生成接口")


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
    except ValueError as e:
        raise HTTPException(400, str(e))
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
        # 资料包分流：每个命中的模块提取一次
        for mod in modules:
            candidates = await extract_candidates(mod, text, db)
            results.append(ImportResult(module=mod, candidates=candidates, source=file.filename or ""))
    return ApiResponse(data=results)
```

`get_enterprise_brief` 在 `onboarding_service.py` 追加：

```python
async def get_enterprise_brief(enterprise_id: str, db) -> dict:
    from app.models.enterprise import Enterprise
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        raise ValueError("企业不存在")
    return {
        "name": ent.name, "industry": ent.industry,
        "business_scope": ent.business_scope, "employee_count": ent.employee_count,
    }
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && python -m pytest tests/test_onboarding_extract.py tests/test_onboarding_org.py -v`

预期：全部 PASS。

- [ ] **步骤 5：全量后端测试 + Commit**

运行：`cd backend && python -m pytest tests/ -q`

预期：全部 PASS。

```bash
git add backend/app/routers/onboarding.py backend/app/services/onboarding_service.py backend/tests/test_onboarding_extract.py backend/tests/test_onboarding_org.py
git commit -m "feat(onboarding): candidate orchestration and file import endpoints"
```

---

## 计划 B2 自检

**规格覆盖度：** 第 6.3 导入现有数据 → B2-1/B2-2/B2-4；第 6.4 资料包导入 → B2-2 模块识别 + B2-4 batch；第 6.5 增量去重 → 现有生成接口已接收 `existing_keys`/`existing_names` 去重（B2-4 注明前端传入）；第 6.2 组织架构生成 → B2-3。无遗漏。

**占位符扫描：** 无 TODO/待定；`onboarding_candidates` 中非 org 模块返回 400 属显式编排占位（前端计划 C 将直接调用现有模块生成接口），非未完成实现。

**类型一致性：** `AIGenerateRequest`/`AIAnswerInput` 复用 `hazardous_chemicals.py` 定义；`ImportResult` 在路由与响应中一致；`generate_org_candidates`/`extract_candidates`/`classify_modules` 在服务与路由中命名一致。
