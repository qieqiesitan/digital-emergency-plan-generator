# 智能体优化阶段 2（能力深化 0.4.1）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 四个能力深化模块：语义法规检索接线、生成后 AI 自检修订循环、报告数据面扩充、企业画像问答（RAG）。

**架构：** 聊天法规检索改接已构建的 ChromaDB 向量库（`vector_store.search_articles` + 图谱补全 + 关键词 fallback）；新增 `plan_review_service`（规则审查 + LLM 修订，修订前存版本快照可回退）；`_generate_report` 按主题扩展采集器；新增 `enterprise_knowledge_service`（企业画像向量化 + 语义问答工具 + 数据变更增量重建）。

**技术栈：** Python 3.11 / FastAPI / SQLAlchemy async / PostgreSQL / ChromaDB（已装已构建）；React + AntD + Vite + tsc。

**规格依据：** `docs/superpowers/specs/2026-08-31-agent-optimization-design.md`（v2.0）阶段 2（模块 7-10）。D2 决策：审查修订默认自动执行 + 可回退。

---

## 文件结构

**新建：**
- `backend/app/services/plan_review_service.py` — 预案审查（规则 + LLM 修订）
- `backend/app/services/enterprise_knowledge_service.py` — 企业画像向量化 + 语义检索
- `backend/app/routers/review.py` — 审查报告/应用修订端点
- `backend/tests/test_chat_regulation_search.py` — 语义法规检索测试
- `backend/tests/test_plan_review_service.py` — 审查服务测试
- `backend/tests/test_plan_review_routes.py` — 审查路由测试
- `backend/tests/test_chat_report_data.py` — 报告采集器测试
- `backend/tests/test_enterprise_knowledge.py` — 画像服务测试
- `backend/tests/test_chat_enterprise_knowledge.py` — 聊天画像工具测试

**修改：**
- `backend/app/services/chat_dispatch.py` — 法规检索重写、报告采集器、画像工具注册
- `backend/app/routers/chat.py` — CHAT_TOOLS 新增 `query_enterprise_knowledge`
- `backend/app/main.py` — 注册 review 路由
- `frontend/src/pages/Plan/PlanEditorPage.tsx` 与移动端预案页 — 审查报告展示 + 应用/回退入口
- 风险源/评估/资源写服务 — 画像增量重建挂点

**职责边界：** `plan_review_service.py` 只做审查/修订；`enterprise_knowledge_service.py` 只做画像索引/检索；`chat_dispatch.py` 只做工具编排；`review.py` 只做 HTTP 暴露。

---

### 任务 1：聊天法规检索改接语义向量（模块 7，落地 C1）

**文件：**
- 修改：`backend/app/services/chat_dispatch.py`
- 测试：`backend/tests/test_chat_regulation_search.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_regulation_search.py — 语义检索 + 图谱补全 + fallback。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _search_regulation_articles


@pytest.mark.asyncio
async def test_vector_hit_with_graph_enrichment():
    hits = [{
        "text": "储存危险化学品应当设置明显标志。",
        "metadata": {"regulation_id": "aq3013_2008", "article_number": "第七条"},
        "distance": 0.12,
    }]
    node = {"full_name": "危险化学品从业单位安全标准化通用规范", "code": "AQ3013-2008", "status": "active"}
    with patch("app.services.chat_dispatch.get_vector_store") as mock_vs, \
         patch("app.services.chat_dispatch.get_graph") as mock_graph:
        mock_vs.return_value.search_articles.return_value = hits
        mock_graph.return_value.get_node.return_value = node
        out = await _search_regulation_articles(AsyncMock(), MagicMock(id="u1"),
                                                {"query": "危化品储存标志", "top_k": 8})
    assert out["source"] == "vector"
    assert out["count"] == 1
    assert out["articles"][0]["regulation_full_name"].startswith("危险化学品")
    assert out["articles"][0]["article_number"] == "第七条"


@pytest.mark.asyncio
async def test_fallback_when_vector_empty():
    with patch("app.services.chat_dispatch.get_vector_store") as mock_vs:
        mock_vs.return_value.search_articles.return_value = []
        out = await _search_regulation_articles(AsyncMock(), MagicMock(id="u1"),
                                                {"query": "安全生产法 第一条", "top_k": 8})
    assert out["source"] == "graph_fallback"


@pytest.mark.asyncio
async def test_fallback_when_vector_raises():
    with patch("app.services.chat_dispatch.get_vector_store") as mock_vs:
        mock_vs.return_value.search_articles.side_effect = RuntimeError("chroma down")
        out = await _search_regulation_articles(AsyncMock(), MagicMock(id="u1"),
                                                {"query": "消防通道要求", "top_k": 8})
    assert out["source"] == "graph_fallback"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_regulation_search.py -q`
预期：FAIL（现实现无 source=vector 分支）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/services/chat_dispatch.py` 中 `_search_regulation_articles` 重写为：

```python
async def _search_regulation_articles(db, user, args):
    """法规条文检索：向量语义优先，图谱关键词+子串兜底。"""
    query = args.get("query", "")
    if not query:
        return {"error": "请提供 query"}
    top_k = _parse_int(args.get("top_k", 8)) or 8
    top_k = max(3, min(top_k, 15))
    try:
        store = get_vector_store()
        hits = store.search_articles(query, top_k=top_k)
        if hits:
            graph = get_graph()
            articles = []
            for hit in hits:
                meta = hit.get("metadata") or {}
                reg_id = meta.get("regulation_id", "")
                node = graph.get_node(reg_id) if reg_id else None
                if not node or node.get("status") == "abolished":
                    continue
                articles.append({
                    "article_text": hit.get("text", ""),
                    "article_number": meta.get("article_number", ""),
                    "regulation_full_name": node.get("full_name", node.get("title", "")),
                    "regulation_code": node.get("code", ""),
                    "status": node.get("status", ""),
                    "similarity_score": round(1 - float(hit.get("distance", 0)), 4),
                })
            if articles:
                return {"articles": articles[:top_k], "count": len(articles[:top_k]),
                        "source": "vector"}
    except Exception as e:
        logger.warning("向量法规检索失败，回退关键词: %s", e)
    return await _regulation_keyword_fallback(query, top_k)
```

把现有关键词+子串检索逻辑原样抽为 `_regulation_keyword_fallback(query, top_k) -> dict`，返回结构增加 `"source": "graph_fallback"`（其余字段不变，保持 chat 系统提示词兼容）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_chat_regulation_search.py -q`
预期：3 passed

- [ ] **步骤 5：回归 + Commit**

运行：`cd backend && pytest tests/test_chat_dispatch.py -q`
预期：无新增失败

```bash
git add backend/app/services/chat_dispatch.py backend/tests/test_chat_regulation_search.py
git commit -m "feat(chat): 法规检索接向量语义（图谱补全+关键词fallback）"
```

**验收（后续 Docker 演练记录）**：用 10 组真实法规问题（危化品储存距离、有限空间作业审批、消防通道、应急预案备案等）对比新旧检索 top-8 命中率，语义命中率 ≥ 图谱检索且能召回语义近义条文。

---

### 任务 2：plan_review_service 规则审查（模块 8，落地 C3 前半）

**文件：**
- 创建：`backend/app/services/plan_review_service.py`
- 测试：`backend/tests/test_plan_review_service.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_plan_review_service.py — 规则审查。"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.plan_review_service import review_plan


def _section(key, title, content):
    s = MagicMock(section_key=key, title=title, content=content,
                  diagram_svgs={}, mermaid_svgs=None, ai_generated=True)
    return s


def test_review_detects_empty_and_placeholder():
    plan = MagicMock(plan_type="comprehensive")
    ent = MagicMock(address="西安市高新区软件园", legal_representative="张三",
                    safety_officer="李四")
    sections = [
        _section("sec_1", "总则", ""),
        _section("sec_2", "事故风险描述", "<p>风险内容（待补充）</p>"),
    ]
    out = review_plan(plan, ent, sections)
    keys = [i["section_key"] for i in out["issues"]]
    assert "sec_1" in keys          # 空章节
    assert any("待补充" in w["warning"] for w in out["warnings"])


def test_review_detects_fake_regulation():
    plan = MagicMock(plan_type="comprehensive")
    ent = MagicMock(address="西安市高新区软件园", legal_representative="张三",
                    safety_officer="李四")
    sections = [_section("sec_1", "总则", "<p>依据《不存在的假法规》编制。</p>")]
    with patch("app.services.plan_review_service._regulation_exists", return_value=False):
        out = review_plan(plan, ent, sections)
    assert any("法规" in i["issue"] for i in out["issues"])


def test_review_clean_plan_no_issues():
    plan = MagicMock(plan_type="comprehensive")
    ent = MagicMock(address="西安市高新区软件园", legal_representative="张三",
                    safety_officer="李四")
    sections = [_section("sec_1", "总则", "<p>依据《中华人民共和国安全生产法》编制。</p>")]
    with patch("app.services.plan_review_service._regulation_exists", return_value=True):
        out = review_plan(plan, ent, sections)
    assert out["issues"] == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_plan_review_service.py -q`
预期：FAIL（`plan_review_service` 不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/services/plan_review_service.py`：

```python
"""预案 AI 审查服务：规则审查（占位符/空章节/法规引用真实性/档案一致性/章节完整性）。"""
import re
from app.services.plan_quality_service import check_plan
from app.regulations import get_graph


def _extract_regulation_names(text: str) -> list[str]:
    return re.findall(r"《([^》]{2,60})》", text or "")


def _regulation_exists(name: str) -> bool:
    """法规名是否存在于知识图谱（模糊匹配全称/简称）。"""
    graph = get_graph()
    name_l = name.lower()
    for nid, data in graph._g.nodes(data=True):
        full = (data.get("full_name") or "").lower()
        label = (data.get("label") or "").lower()
        if name_l and (name_l in full or name_l in label or full in name_l):
            return True
    return False


def review_plan(plan, enterprise, sections) -> dict:
    """返回 {"issues": [...], "warnings": [...]}。
    issue 字段：section_key/section_title/issue；warning 字段：section_key/section_title/warning/evidence。
    """
    rules = check_plan(plan, enterprise, sections)
    issues = list(rules.get("issues", []))
    warnings = list(rules.get("warnings", []))

    # 法规引用真实性：正文引用的法规名必须在图谱中存在（防编造）
    for s in sections:
        text = re.sub(r"<[^>]+>", "", s.content or "")
        for name in _extract_regulation_names(text):
            if not _regulation_exists(name):
                issues.append({
                    "section_key": s.section_key,
                    "section_title": s.title,
                    "issue": f"疑似编造法规引用：{name}（法规库中未找到）",
                })
    return {"issues": issues, "warnings": warnings}
```

（`check_plan` 已覆盖空章节/占位符/档案一致性/跨章节人物一致性等规则，直接复用。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_plan_review_service.py -q`
预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/plan_review_service.py backend/tests/test_plan_review_service.py
git commit -m "feat(review): plan_review_service 规则审查（复用质量检查+法规引用真实性）"
```

---

### 任务 3：GET /plans/{id}/review 审查路由

**文件：**
- 创建：`backend/app/routers/review.py`
- 修改：`backend/app/main.py`（注册路由）
- 测试：`backend/tests/test_plan_review_routes.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_plan_review_routes.py — 审查路由。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.routers.review import get_plan_review


@pytest.mark.asyncio
async def test_get_plan_review_requires_ownership():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    with pytest.raises(Exception):
        await get_plan_review("p1", MagicMock(id="u1"), db)


@pytest.mark.asyncio
async def test_get_plan_review_returns_issues():
    db = AsyncMock()
    plan = MagicMock(id="p1", user_id="u1", plan_type="comprehensive")
    ent = MagicMock()
    sec = MagicMock(section_key="sec_1", title="总则", content="")
    result = MagicMock()
    result.scalar_one_or_none.side_effect = [plan, ent]
    result.scalars.return_value.all.return_value = [sec]
    db.execute.return_value = result
    with patch("app.routers.review.review_plan",
               return_value={"issues": [{"section_key": "sec_1", "issue": "章节内容为空"}],
                             "warnings": []}):
        out = await get_plan_review("p1", MagicMock(id="u1"), db)
    assert out["issues"][0]["section_key"] == "sec_1"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_plan_review_routes.py -q`
预期：FAIL（`review` 模块不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/routers/review.py`：

```python
"""预案 AI 审查路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import PlanProject, PlanSection, Enterprise
from app.services.plan_review_service import review_plan

router = APIRouter(prefix="/plans", tags=["Plan Review"])


@router.get("/{plan_id}/review")
async def get_plan_review(plan_id: str, current_user=Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    sections = (await db.execute(select(PlanSection).where(
        PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()
    result = review_plan(p, ent, sections)
    return {"plan_id": plan_id, "title": p.title, **result}
```

`backend/app/main.py` 追加：

```python
from app.routers import review
app.include_router(review.router, prefix="/api/v1")
```

- [ ] **步骤 4：运行测试验证通过 + 回归**

运行：`cd backend && pytest tests/test_plan_review_routes.py -q`，预期 2 passed
运行：`cd backend && pytest tests/test_main_imports.py tests/test_app_routes.py -q 2>$null`（若存在），无新增失败

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/review.py backend/app/main.py backend/tests/test_plan_review_routes.py
git commit -m "feat(review): GET /plans/{id}/review 审查端点"
```

---

### 任务 4：POST /plans/{id}/review/apply 应用修订（规则 + LLM，快照可回退）

**文件：**
- 修改：`backend/app/routers/review.py`
- 测试：`backend/tests/test_plan_review_routes.py`（追加）

- [ ] **步骤 1：编写失败的测试**

```python
"""追加到 test_plan_review_routes.py"""
@pytest.mark.asyncio
async def test_apply_review_rules_fixes_placeholder():
    from app.routers.review import apply_plan_review
    db = AsyncMock()
    plan = MagicMock(id="p1", user_id="u1", plan_type="comprehensive",
                     current_version=1, style_preference=None,
                     advanced_prompt_overrides=None)
    sec = MagicMock(section_key="sec_1", title="总则", content="<p>（待补充）</p>")
    result = MagicMock()
    result.scalar_one_or_none.side_effect = [plan, None]
    result.scalars.return_value.all.return_value = [sec]
    db.execute.return_value = result
    db.add = MagicMock()
    with patch("app.routers.review.review_plan", return_value={
        "issues": [{"section_key": "sec_1", "section_title": "总则",
                    "issue": "存在待补充占位符"}],
        "warnings": []}), \
         patch("app.routers.review._apply_llm_revision",
               new=AsyncMock(return_value="<p>修订后内容</p>")):
        out = await apply_plan_review("p1", MagicMock(id="u1"), db, mode="llm")
    assert out["applied"] == ["sec_1"]
    assert sec.content == "<p>修订后内容</p>"
    db.commit.assert_awaited()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_plan_review_routes.py -q`
预期：FAIL（`apply_plan_review` 不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/routers/review.py` 追加：

```python
from pydantic import BaseModel
from app.routers.versions import _build_snapshot
from app.models.enterprise import PlanVersion


class ReviewApplyRequest(BaseModel):
    mode: str = "auto"        # auto=仅规则修复；llm=含 LLM 重写
    section_keys: list[str] | None = None


async def _apply_llm_revision(section, issue_text, plan, ent_data, db) -> str:
    """LLM 重写章节：构造修订提示词 → 流式收集 → 返回新 HTML 内容。"""
    from app.routers.generation import _stream_llm
    from app.services.ai_config_service import get_system_ai_config
    cfg = await get_system_ai_config(db)
    if not cfg:
        raise HTTPException(400, "系统未配置 AI 模型")
    prompt = (
        "你是应急预案编制专家。以下章节存在质量问题，请仅重写该章节正文（输出 HTML），"
        "保留章节标题语义，修正问题，不得编造企业数据。\n"
        f"【问题】{issue_text}\n"
        f"【原内容】{section.content or ''}\n"
        f"【企业上下文】{str(ent_data)[:800]}\n"
        "直接输出修订后的章节 HTML："
    )
    return await _stream_llm(prompt, cfg, plan.plan_type)


@router.post("/{plan_id}/review/apply")
async def apply_plan_review(plan_id: str, current_user=Depends(get_current_user),
                            db: AsyncSession = Depends(get_db),
                            body: ReviewApplyRequest | None = None):
    body = body or ReviewApplyRequest()
    p = (await db.execute(select(PlanProject).where(
        PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    sections = (await db.execute(select(PlanSection).where(
        PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()
    result = review_plan(p, ent, sections)
    target_keys = set(body.section_keys or [s.section_key for s in sections])
    issue_map = {}
    for it in result["issues"]:
        if it.get("section_key") in target_keys:
            issue_map.setdefault(it["section_key"], []).append(it.get("issue", ""))

    applied = []
    if issue_map:
        # 修订前保存版本快照（可回退）
        snapshot = _build_snapshot(p, sections)
        new_ver = p.current_version + 1
        db.add(PlanVersion(plan_project_id=plan_id, version_number=new_ver,
                           created_by="ai_review", description="AI 审查修订前快照",
                           snapshot=snapshot))
        p.current_version = new_ver
        for s in sections:
            if s.section_key not in issue_map:
                continue
            issue_text = "；".join(issue_map[s.section_key])
            if body.mode == "llm":
                s.content = await _apply_llm_revision(s, issue_text, p, ent, db)
                s.ai_generated = True
            else:
                # auto 模式：占位符替换为明确标记（不编造）
                s.content = (s.content or "").replace("（待补充）", "（待补充——请人工补充）")
            applied.append(s.section_key)
        await db.commit()
    return {"plan_id": plan_id, "applied": applied, "snapshot_version": p.current_version}
```

（`ent` 直接传给 `_apply_llm_revision` 作为上下文；若 `_stream_llm` 签名不符以 generation.py 实际为准，保留"企业上下文截断注入"语义。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_plan_review_routes.py -q`
预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/routers/review.py backend/tests/test_plan_review_routes.py
git commit -m "feat(review): POST /plans/{id}/review/apply 应用修订（快照可回退+LLM重写）"
```

---

### 任务 5：前端审查报告展示（桌面 + 移动端）

**文件：**
- 修改：`frontend/src/pages/Plan/PlanEditorPage.tsx`
- 修改：移动端预案页（`frontend/src/mobile/screens/` 下对应预案编辑/详情页）
- 修改：`frontend/src/services/planService.ts`（新增 review API）

- [ ] **步骤 1：planService.ts 新增 API**

```ts
export interface PlanReviewIssue {
  section_key: string;
  section_title: string;
  issue?: string;
  warning?: string;
  evidence?: string;
}

export async function fetchPlanReview(planId: string): Promise<{ issues: PlanReviewIssue[]; warnings: PlanReviewIssue[] }> {
  const res = await api.get(`/plans/${planId}/review`);
  return res.data.data;
}

export async function applyPlanReview(planId: string, mode: "auto" | "llm", sectionKeys?: string[]): Promise<{ applied: string[] }> {
  const res = await api.post(`/plans/${planId}/review/apply`, { mode, section_keys: sectionKeys ?? null });
  return res.data.data;
}
```

- [ ] **步骤 2：PlanEditorPage 增加审查面板**

工具栏加「AI 审查」按钮 → 调 `fetchPlanReview` → 展示 issues/warnings 列表（按章节分组，红色=issue、橙色=warning）；「应用修订（LLM）」按钮调 `applyPlanReview(planId, "llm")` → 成功后重新加载章节 + message.success；「回退」复用既有版本回退入口（versions API 已存在）。

- [ ] **步骤 3：移动端同步**

移动端预案详情页加「审查」入口 + 结果列表 + 应用按钮（同样的 API 调用）。

- [ ] **步骤 4：类型检查**

运行：`cd frontend && npx tsc -b`，预期 exit 0

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/services/planService.ts frontend/src/pages/Plan/PlanEditorPage.tsx <移动端预案页>
git commit -m "feat(review): 前端 AI 审查面板（展示+应用修订+回退入口）"
```

---

### 任务 6：报告数据面扩充（模块 9，落地 C2）

**文件：**
- 修改：`backend/app/services/chat_dispatch.py`
- 测试：`backend/tests/test_chat_report_data.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_report_data.py — 报告主题采集器。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _collect_risk_distribution, _collect_resource_coverage


@pytest.mark.asyncio
async def test_collect_risk_distribution_groups_by_level():
    ctx = {"risk_sources": [
        {"name": "锅炉", "risk_level": "重大风险"},
        {"name": "配电柜", "risk_level": "重大风险"},
        {"name": "化学品库", "risk_level": "较大风险"},
    ]}
    with patch("app.services.chat_dispatch.build_risk_management_context",
               new=AsyncMock(return_value=ctx)):
        out = await _collect_risk_distribution(AsyncMock(), MagicMock(id="u1"))
    assert out["重大风险"] == 2
    assert out["较大风险"] == 1


@pytest.mark.asyncio
async def test_collect_resource_coverage_counts_categories():
    rows = [MagicMock(category="灭火器"), MagicMock(category="灭火器"),
            MagicMock(category="急救箱")]
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result
    out = await _collect_resource_coverage(db, MagicMock(id="u1"))
    assert out["灭火器"] == 2
    assert out["急救箱"] == 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_report_data.py -q`
预期：FAIL（采集函数不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/services/chat_dispatch.py` 新增采集器：

```python
async def _collect_risk_distribution(db, user, args=None):
    """风险源按等级分布（跨企业汇总）。"""
    ents = (await db.execute(select(Enterprise).where(
        Enterprise.user_id == user.id).limit(50))).scalars().all()
    dist: dict[str, int] = {}
    for ent in ents:
        ctx = await build_risk_management_context(ent.id, db)
        for rs in ctx.get("risk_sources", []):
            lvl = rs.get("risk_level") or "未分级"
            dist[lvl] = dist.get(lvl, 0) + 1
    return dist


async def _collect_resource_coverage(db, user, args=None):
    """应急资源按类别统计。"""
    rows = (await db.execute(
        select(EmergencyResource).join(Enterprise)
        .where(Enterprise.user_id == user.id))).scalars().all()
    dist: dict[str, int] = {}
    for r in rows:
        cat = r.category or "未分类"
        dist[cat] = dist.get(cat, 0) + 1
    return dist
```

`_generate_report` 增加主题路由（在 data_context 组装处）：

```python
REPORT_EXTRA_COLLECTORS = {
    "风险分布": _collect_risk_distribution,
    "资源覆盖": _collect_resource_coverage,
    "法规合规": _collect_regulation_compliance,   # 见步骤 4
}

# 在 _generate_report 内：
collector = REPORT_EXTRA_COLLECTORS.get(topic)
if collector:
    extra = await collector(db, user, {})
    data_context = json.dumps({"dashboard": dash, "extra": extra},
                              ensure_ascii=False, indent=2)
else:
    data_context = json.dumps({...既有逻辑...}, ensure_ascii=False, indent=2)
```

- [ ] **步骤 4：法规合规采集器**

```python
async def _collect_regulation_compliance(db, user, args=None):
    """法规库统计 + 用户预案引用概况（轻量）。"""
    stats = await _get_regulation_stats(db, user, {})
    plans = (await db.execute(select(PlanProject).where(
        PlanProject.user_id == user.id))).scalars().all()
    return {"regulation_stats": stats, "plan_total": len(plans)}
```

- [ ] **步骤 5：运行测试验证通过 + 回归**

运行：`cd backend && pytest tests/test_chat_report_data.py -q`，预期 2 passed
运行：`cd backend && pytest tests/test_chat_dispatch.py -q`，无新增失败

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/chat_dispatch.py backend/tests/test_chat_report_data.py
git commit -m "feat(chat): 报告按主题扩展采集器（风险分布/资源覆盖/法规合规）"
```

**验收**：6 个主题报告（系统概览/企业分析/预案进度/风险分布/资源覆盖/法规合规）均能生成且数据面含风险/资源/法规维度。

---

### 任务 7：enterprise_knowledge_service 企业画像索引（模块 10，落地 C4 前半）

**文件：**
- 创建：`backend/app/services/enterprise_knowledge_service.py`
- 测试：`backend/tests/test_enterprise_knowledge.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_enterprise_knowledge.py — 企业画像索引。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.enterprise_knowledge_service import (
    _build_enterprise_text, EnterpriseKnowledgeStore,
)


def test_build_enterprise_text_assembles_sections():
    context = {"risk_sources": [
        {"name": "锅炉", "risk_level": "重大风险", "control_measures": "定期检测"},
    ]}
    text = _build_enterprise_text("企业A", context, [], [])
    assert "企业A" in text
    assert "锅炉" in text
    assert "重大风险" in text


def test_store_delete_then_add_is_idempotent():
    store = EnterpriseKnowledgeStore.__new__(EnterpriseKnowledgeStore)
    store._client = MagicMock()
    store._collection = MagicMock()
    store._collection.delete.return_value = None
    store._collection.add.return_value = None
    store.index_enterprise("e1", ["片段1", "片段2"])
    store._collection.delete.assert_called_once()
    store._collection.add.assert_called_once()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_enterprise_knowledge.py -q`
预期：FAIL（模块不存在）

- [ ] **步骤 3：编写最少实现代码**

`backend/app/services/enterprise_knowledge_service.py`：

```python
"""企业画像知识库：风险/评估/资源上下文向量化 + 语义检索。"""
import logging
import os

logger = logging.getLogger(__name__)

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "regulations", "data", "chroma_db")
COLLECTION_NAME = "enterprise_knowledge"


def _build_enterprise_text(name: str, risk_context: dict, reports: list, resources: list) -> str:
    parts = [f"企业：{name}"]
    for rs in risk_context.get("risk_sources", []):
        parts.append(
            f"风险源：{rs.get('name')}，等级：{rs.get('risk_level')}，"
            f"事故类型：{rs.get('accident_type')}，管控措施：{rs.get('control_measures')}"
        )
    for r in reports:
        parts.append(f"报告：{r}")
    for res in resources:
        parts.append(f"资源：{res.get('name')}，类别：{res.get('category')}，数量：{res.get('quantity')}{res.get('unit')}")
    return "\n".join(parts)


class EnterpriseKnowledgeStore:
    """独立封装企业画像 collection（metadata 按 enterprise_id 过滤）。"""

    def __init__(self):
        import chromadb
        self._client = chromadb.PersistentClient(
            path=os.path.abspath(CHROMA_DIR),
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    def index_enterprise(self, enterprise_id: str, texts: list[str]) -> int:
        """先删旧向量再写入（幂等重建）。"""
        self._collection.delete(where={"enterprise_id": enterprise_id})
        ids = [f"{enterprise_id}_{i}" for i in range(len(texts))]
        metas = [{"enterprise_id": enterprise_id} for _ in texts]
        self._collection.add(ids=ids, documents=texts, metadatas=metas)
        return len(texts)

    def search(self, enterprise_id: str, question: str, top_k: int = 6) -> list[dict]:
        if self._collection.count() == 0:
            return []
        results = self._collection.query(
            query_texts=[question], n_results=min(top_k, self._collection.count()),
            where={"enterprise_id": enterprise_id})
        out = []
        if results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                out.append({"text": doc, "distance": results["distances"][0][i]})
        return out


async def build_enterprise_index(enterprise_id: str, db) -> int:
    """从风险上下文/评估报告/资源调查组装文本并写入向量库。"""
    from app.models.enterprise import Enterprise, EmergencyResource
    from app.models.risk_assessment import RiskAssessmentReport
    from app.services.risk_context_builder import build_risk_management_context
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        return 0
    ctx = await build_risk_management_context(enterprise_id, db)
    resources = (await db.execute(select(EmergencyResource).where(
        EmergencyResource.enterprise_id == enterprise_id))).scalars().all()
    reports = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id))).scalars().all()
    texts = [_build_enterprise_text(
        ent.name, ctx,
        [f"{r.title or '评估报告'}：{(r.summary or '')[:300]}" for r in reports],
        [{"name": r.name, "category": r.category, "quantity": r.quantity, "unit": r.unit}
         for r in resources])]
    if not texts[0].strip() or len(texts[0]) < 20:
        return 0
    return EnterpriseKnowledgeStore().index_enterprise(enterprise_id, texts)
```

（`select`/`Enterprise` 等 import 以文件顶部为准；`RiskAssessmentReport.summary` 字段若不存在则改用 `conclusion` 或跳过——以模型实际字段为准。）

- [ ] **步骤 4：运行测试验证通过**

运行：`cd backend && pytest tests/test_enterprise_knowledge.py -q`
预期：2 passed

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/enterprise_knowledge_service.py backend/tests/test_enterprise_knowledge.py
git commit -m "feat(agent): 企业画像向量索引服务（幂等重建）"
```

---

### 任务 8：query_enterprise_knowledge 聊天工具 + 增量挂点

**文件：**
- 修改：`backend/app/services/chat_dispatch.py`
- 修改：`backend/app/routers/chat.py`（CHAT_TOOLS）
- 测试：`backend/tests/test_chat_enterprise_knowledge.py`（新建）

- [ ] **步骤 1：编写失败的测试**

```python
"""test_chat_enterprise_knowledge.py — 聊天画像问答工具。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_dispatch import _query_enterprise_knowledge


@pytest.mark.asyncio
async def test_query_requires_ownership():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    out = await _query_enterprise_knowledge(db, MagicMock(id="u1"),
                                            {"enterprise_id": "e1", "question": "有哪些重大风险"})
    assert "error" in out


@pytest.mark.asyncio
async def test_query_returns_snippets():
    db = AsyncMock()
    ent = MagicMock(id="e1", user_id="u1", name="企业A")
    result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    db.execute.return_value = result
    with patch("app.services.chat_dispatch.EnterpriseKnowledgeStore") as mock_store:
        mock_store.return_value.search.return_value = [
            {"text": "风险源：锅炉，等级：重大风险", "distance": 0.1}]
        out = await _query_enterprise_knowledge(db, MagicMock(id="u1"),
                                                {"enterprise_id": "e1", "question": "有哪些重大风险"})
    assert out["hits"][0]["text"].startswith("风险源")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd backend && pytest tests/test_chat_enterprise_knowledge.py -q`
预期：FAIL（工具不存在）

- [ ] **步骤 3：实现工具**

`backend/app/services/chat_dispatch.py`：

```python
async def _query_enterprise_knowledge(db, user, args):
    """基于企业画像（风险/评估/资源）语义问答。"""
    from app.services.enterprise_knowledge_service import EnterpriseKnowledgeStore
    ent_id = args.get("enterprise_id", "")
    question = args.get("question", "")
    if not ent_id or not question:
        return {"error": "请提供 enterprise_id 和 question"}
    ent = (await db.execute(select(Enterprise).where(
        Enterprise.id == ent_id, Enterprise.user_id == user.id))).scalar_one_or_none()
    if not ent:
        return {"error": "企业不存在或无权访问", "verified": False}
    try:
        hits = EnterpriseKnowledgeStore().search(ent_id, question, top_k=6)
    except Exception as e:
        logger.warning("企业画像检索失败: %s", e)
        hits = []
    if not hits:
        return {"enterprise_id": ent_id, "hits": [],
                "message": "该企业暂无画像数据（请先完成风险辨识或生成评估报告）", "verified": True}
    return {"enterprise_id": ent_id, "hits": [{"text": h["text"][:500],
                                               "similarity": round(1 - float(h["distance"]), 4)}
                                              for h in hits],
            "message": "已检索到相关画像片段", "verified": True}
```

`_FUNCTIONS` 注册 `"query_enterprise_knowledge": _query_enterprise_knowledge`。

`backend/app/routers/chat.py` 的 `CHAT_TOOLS` 追加：

```python
    {"type": "function", "function": {"name": "query_enterprise_knowledge",
     "description": "基于企业画像（风险分级管控、评估报告、应急资源）语义问答。用户询问某企业风险状况、管控措施、资源配备时使用",
     "parameters": {"type": "object",
                    "properties": {"enterprise_id": {"type": "string", "description": "企业ID(必填)"},
                                   "question": {"type": "string", "description": "问题(必填)"}},
                    "required": ["enterprise_id", "question"]}}},
```

- [ ] **步骤 4：增量挂点（风险源/评估/资源写操作后重建画像）**

在 `chat_dispatch.py` 的 `_create_resource`/`_update_resource` 成功提交后、以及风险源/评估写入对应服务成功后，追加：

```python
    import asyncio
    from app.services.enterprise_knowledge_service import build_enterprise_index
    asyncio.ensure_future(build_enterprise_index(ent_id, async_session()))
```

（挂点以不阻塞主流程为原则；若写服务与 chat_dispatch 分离，则在其 commit 后调用。范围以「风险源/评估/资源任一写操作后触发重建」为准，具体挂点由实现者按既有服务结构落点。）

- [ ] **步骤 5：运行测试验证通过 + 回归**

运行：`cd backend && pytest tests/test_chat_enterprise_knowledge.py -q`，预期 2 passed
运行：`cd backend && pytest tests/test_chat_dispatch.py -q`，无新增失败

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/chat_dispatch.py backend/app/routers/chat.py backend/tests/test_chat_enterprise_knowledge.py
git commit -m "feat(chat): 企业画像问答工具 + 增量重建挂点"
```

**验收（Docker 演练）**：对含风险源样本企业问「这家企业有哪些重大风险」→ 回答引用真实风险源；无画像企业返回引导文案；权限隔离验证（非本人企业 error）。

---

### 任务 9：阶段 2 全量门禁

**文件：** 无（验证；若发现必须修复的回归按门禁修复）

- [ ] **步骤 1：后端全量**

运行：`cd backend && pytest tests/ -q`
预期：全绿（基线 1183 + 新增用例）；`third_party_config` 5 个环境失败若存在则说明（本地 .env 真实 key，与本次无关）

- [ ] **步骤 2：前端类型**

运行：`cd frontend && npx tsc -b`，预期 exit 0

- [ ] **步骤 3：代码卫生**

运行：`git show --check HEAD` 与 `git diff --check`，预期无空白错误

- [ ] **步骤 4：Commit（如有修复）**

```bash
git add <修复文件>
git commit -m "test(agent): 阶段2门禁修复"
```

---

### 任务 10：0.4.1 打包与验收演练

**文件：** `scripts/package-release.sh`（不改，沿用）

- [ ] **步骤 1：构建前端 + 打包**

运行：容器 node:22 构建 dist（沿用阶段 1 流程）→ `bash scripts/package-release.sh --system`

- [ ] **步骤 2：Docker 验收演练（隔离环境）**

对照设计文档第 10 节阶段 2 验收矩阵：
- 10 组法规问题语义命中率对比记录
- 构造 5 类缺陷样本预案 → 审查全命中 → 应用修订 → 回退快照恢复
- 6 主题报告数据面达标
- 企业画像问答命中真实风险源 + 权限隔离

- [ ] **步骤 3：交付说明**

整理 0.4.1 交付说明（新路由/工具/迁移（无新表）/前端改动），更新 TASKS.md，向用户汇报。

---

## 计划自检记录

**1. 规格覆盖度（对照设计文档模块 7-10）：**
- 模块 7 语义法规检索 → 任务 1 ✓
- 模块 8 自检修订循环 → 任务 2/3/4/5 ✓（规则审查 + 端点 + LLM 修订 + 前端）
- 模块 9 报告数据面 → 任务 6 ✓
- 模块 10 企业画像问答 → 任务 7/8 ✓（索引 + 工具 + 挂点）
- 门禁/打包 → 任务 9/10 ✓

**2. 占位符扫描：** 无 TODO/待定；任务 8 步骤 4 的挂点位置以既有服务结构落点（明确范围，非占位）。

**3. 类型一致性：** `review_plan(plan, enterprise, sections)` 与任务 2/3 一致；`apply_plan_review(plan_id, user, db, mode)` 与任务 4 测试一致；`EnterpriseKnowledgeStore().search(enterprise_id, question, top_k)` 与任务 7/8 一致；`_query_enterprise_knowledge` 返回 hits/verified 与任务 8 断言一致。

**4. 依赖已核实：** `vector_store.search_articles` 返回 `{text, metadata, distance}`；`graph.get_node` 存在；`check_plan` 返回 issues/warnings；`_build_snapshot`/`PlanVersion` 可复用（任务 4 快照回退）；`PlanSection.ai_generated` 存在（不新增 reviewed 字段）；`build_risk_management_context` 返回 risk_sources（含 risk_level/control_measures）。
