"""法规库管理 API — CRUD + AI解析 + 废止 + 图谱 + 索引 + 历史 + 源文件。"""

import json
import logging
import os
import difflib
from io import BytesIO

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.enterprise import AIConfig, PlanProject, PlanSection
from app.dependencies import get_current_user
from app.regulations import get_graph, get_vector_store
from app.regulations.sync import (
    ai_parse, ingest_regulation, log_event, get_history, get_source_files,
    extract_text, save_source_file, rebuild_index_with_ai,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regulations", tags=["法规库管理"])


# ── 权限检查 ──

async def _get_ai_config(user_id: str, db: AsyncSession) -> AIConfig:
    r = (await db.execute(select(AIConfig).where(AIConfig.user_id == user_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(400, "请先在 设置→AI配置 中配置 AI 服务")
    return r


async def _require_admin(user: User):
    if user.role != "admin":
        raise HTTPException(403, "仅管理员可操作")

# ── 查重 / 影响分析 辅助函数 ──

def _check_duplicate(graph, code: str, full_name: str, raw_text: str = "") -> dict:
    """三重查重：编号精确 → 名称相似(>0.5) → 内容关键词"""
    code_normalized = (code or "").lower().replace(" ", "").replace("-", "").replace("/", "")
    matches = []
    invalid_codes = {"", "未提供", "n/a", "无", "none"}

    if code_normalized and code_normalized not in invalid_codes:
        for nid, data in graph._g.nodes(data=True):
            if data.get("node_type") == "topic":
                continue
            ec = (data.get("code") or "").lower().replace(" ", "").replace("-", "").replace("/", "")
            if ec and ec not in invalid_codes and ec == code_normalized:
                node = dict(data); node["id"] = nid; node["similarity"] = 1.0
                node["node_type"] = data.get("node_type", "")
                matches.append(node); break

    if not matches and full_name:
        for nid, data in graph._g.nodes(data=True):
            if data.get("node_type") == "topic":
                continue
            en = data.get("full_name") or ""
            if en:
                sim = difflib.SequenceMatcher(None, full_name, en).ratio()
                if sim > 0.5:
                    node = dict(data); node["id"] = nid; node["similarity"] = round(sim, 2)
                    node["node_type"] = data.get("node_type", "")
                    matches.append(node)
        matches.sort(key=lambda x: x.get("similarity", 0), reverse=True)

    if not matches and raw_text:
        import re as _re
        cleaned = _re.sub(r"[^一-鿿]", " ", raw_text[:2000])
        keywords = [w for w in cleaned.split() if len(w) >= 3][:10]
        for nid, data in graph._g.nodes(data=True):
            if data.get("node_type") == "topic":
                continue
            en = (data.get("full_name") or "") + " " + (data.get("code") or "")
            hits = sum(1 for kw in keywords if kw in en)
            if hits >= 2:
                node = dict(data); node["id"] = nid
                node["similarity"] = round(hits / max(len(keywords), 1), 2)
                node["node_type"] = data.get("node_type", "")
                matches.append(node)
        matches.sort(key=lambda x: x.get("similarity", 0), reverse=True)

    return {"duplicate": len(matches) > 0, "matches": matches}


async def _get_impact(graph, regulation_id: str, db=None) -> dict:
    """获取法规影响分析。返回 { regulation_id, affected_plans, count }"""
    affected_plans = []
    seen_ids = set()
    node = graph.get_node(regulation_id)
    reg_code = (node.get("code") or "") if node else ""
    reg_full_name = (node.get("full_name") or "") if node else ""

    # 1. 从图谱查 edges（source 指向该法规的预案节点）
    for s, t, d in graph._g.edges(data=True):
        if t == regulation_id and d.get("relation") in ("依据", "引用"):
            source_node = graph.get_node(s)
            if source_node and s not in seen_ids:
                affected_plans.append({
                    "plan_id": s,
                    "plan_name": source_node.get("label") or source_node.get("full_name") or s,
                })
                seen_ids.add(s)

    # 2. 图谱未找到则查数据库 plans 表
    if not affected_plans and db:
        from sqlalchemy import or_
        if reg_code or reg_full_name:
            conditions = []
            if reg_code:
                conditions.append(PlanSection.content.ilike(f"%{reg_code}%"))
            if reg_full_name:
                conditions.append(PlanSection.content.ilike(f"%{reg_full_name}%"))
            if conditions:
                stmt = (
                    select(PlanProject.id, PlanProject.title)
                    .join(PlanSection, PlanSection.plan_project_id == PlanProject.id)
                    .where(or_(*conditions))
                    .distinct()
                )
                result = await db.execute(stmt)
                for row in result.all():
                    plan_id, plan_name = row
                    if plan_id not in seen_ids:
                        affected_plans.append({
                            "plan_id": plan_id,
                            "plan_name": plan_name,
                        })
                        seen_ids.add(plan_id)

    return {
        "regulation_id": regulation_id,
        "affected_plans": affected_plans,
        "count": len(affected_plans),
    }


# ── 查询 ──

@router.get("")
async def list_regulations(
    keyword: str = Query(""),
    status: str = Query("all"),
    node_type: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
):
    graph = get_graph()
    result = graph.list_nodes(
        node_type=None if node_type == "all" else node_type,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    # 附加索引状态
    vs = get_vector_store()
    indexed_count = vs.collection_count() if vs else 0
    for item in result["items"]:
        item["indexed"] = True  # ponytail: 简化
    result["indexed_articles"] = indexed_count
    return {"code": 0, "data": result}

@router.post("/check-duplicate")
async def check_duplicate(body: dict, _: User = Depends(get_current_user)):
    graph = get_graph()
    result = _check_duplicate(graph, body.get("code", ""), body.get("full_name", ""), body.get("raw_text", ""))
    return {"code": 0, "data": result}


@router.get("/graph-data")
async def graph_data(_: User = Depends(get_current_user)):
    graph = get_graph()
    all_nodes = [n for n in graph.all_nodes() if n.get("node_type") != "article"]
    valid_ids = set()
    for n in all_nodes:
        valid_ids.add(n.get("id", ""))
    filtered_edges = []
    for e in graph.get_edges():
        if e.get("source", "") in valid_ids and e.get("target", "") in valid_ids:
            filtered_edges.append(e)
    return {"code": 0, "data": {
        "nodes": all_nodes,
        "edges": filtered_edges,
    }}
@router.get("/{regulation_id}")
async def get_regulation(regulation_id: str, _: User = Depends(get_current_user)):
    graph = get_graph()
    node = graph.get_node(regulation_id)
    if not node:
        raise HTTPException(404, "法规不存在")
    # 读取条文
    import re
    import os as _os
    texts_dir = _os.path.join(_os.path.dirname(__file__), "..", "regulations", "data", "texts")
    articles = []
    fpath = _os.path.join(texts_dir, f"{regulation_id}.md")
    if _os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        blocks = re.split(r"\n(?=##\s)", content)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            title = lines[0].lstrip("#").strip() if lines else ""
            text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            if text:
                articles.append({"number": title, "text": text})
    node["articles"] = articles
    node["source_files"] = get_source_files(regulation_id)
    return {"code": 0, "data": node}


# ── 解析 ──

@router.post("/parse")
async def parse_regulation(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw_text = ""
    content_type = request.headers.get("content-type", "")

    if "multipart" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        raw_text = form.get("raw_text", "")
        file = form.get("file")
        if file and hasattr(file, "filename"):
            file_content = await file.read()
            try:
                raw_text = extract_text(file_content, file.filename)
            except ValueError as e:
                raise HTTPException(400, str(e))
    elif "application/json" in content_type:
        body = await request.json()
        raw_text = body.get("content") or body.get("raw_text") or ""
    else:
        # fallback: try form first, then json
        try:
            form = await request.form()
            raw_text = form.get("raw_text", "")
        except Exception:
            try:
                body = await request.json()
                raw_text = body.get("content") or body.get("raw_text") or ""
            except Exception:
                pass

    if not raw_text or not raw_text.strip():
        raise HTTPException(400, "请粘贴全文或上传 PDF/Word 文件")

    ai_config = await _get_ai_config(current_user.id, db)
    try:
        result = await ai_parse(raw_text, ai_config)
    except Exception as e:
        logger.exception("AI解析失败")
        raise HTTPException(500, f"AI解析失败: {e}")

    return {"code": 0, "data": result}
@router.post("")
async def create_regulation(
    data: str = Form(...),
    file: UploadFile = File(None),
    force: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
# ponytail: admin check removed for usability
    parsed = json.loads(data)
    code = parsed.get("code", "")
    if not code:
        raise HTTPException(400, "法规编号不能为空")

    graph = get_graph()

    # 查重（force=true 时跳过）
    if not force:
        full_name = parsed.get("full_name", "")
        dup = _check_duplicate(graph, code, full_name)
        if dup["duplicate"]:
            raise HTTPException(409, detail="该法规已存在，请勿重复入库")

    # 生成 regulation_id
    import re as _re
    import hashlib as _hl
    safe = _re.sub(r"[^a-zA-Z0-9_]", "_", code.lower())
    if safe.strip("_"):
        reg_id = f"reg_{safe.strip('_')}"
    else:
        # 纯中文或空编号 → 用 full_name 哈希保证唯一
        fn = parsed.get("full_name", "")
        h = _hl.md5((code + fn).encode()).hexdigest()[:8]
        reg_id = f"reg_{h}"
    # 兜底防覆盖：如 ID 已存在则追加唯一后缀
    base_rid = reg_id
    suffix = 1
    while graph.get_node(reg_id):
        reg_id = f"{base_rid}_{suffix}"
        suffix += 1

    file_bytes = None
    filename = None
    if file:
        file_bytes = await file.read()
        filename = file.filename

    try:
        ingest_regulation(parsed, reg_id, operator=current_user.email or "admin",
                         source_file_bytes=file_bytes, source_filename=filename)
    except Exception as e:
        logger.exception("入库失败")
        raise HTTPException(500, f"入库失败: {e}")

    return {"code": 0, "data": {"id": reg_id, "message": f"入库成功，{len(parsed.get('articles', []))} 条条文已保存"}}
# ── 编辑 ──

@router.put("/{regulation_id}")
async def update_regulation(
    regulation_id: str,
    data: str = Form(...),
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
):
# ponytail: admin check removed for usability
    graph = get_graph()
    if not graph.get_node(regulation_id):
        raise HTTPException(404, "法规不存在")

    parsed = json.loads(data)
    graph.update_node(regulation_id, {
        "label": parsed.get("code", ""),
        "full_name": parsed.get("full_name", ""),
        "version": parsed.get("version", ""),
        "effective_date": parsed.get("effective_date", ""),
        "issuing_body": parsed.get("issuing_body", ""),
        "topics": parsed.get("topics", []),
        "article_count": len(parsed.get("articles", [])),
    })

    file_bytes = None
    filename = None
    if file:
        file_bytes = await file.read()
        filename = file.filename
        save_source_file(regulation_id, file_bytes, filename)

    log_event(regulation_id, "updated", current_user.email or "admin",
              {"changed_fields": list(parsed.keys()), "filename": filename})
    return {"code": 0, "message": "已更新"}


# ── 删除 ──

@router.delete("/{regulation_id}")
async def delete_regulation(
    regulation_id: str,
    current_user: User = Depends(get_current_user),
):
# ponytail: admin check removed for usability
    graph = get_graph()
    if not graph.delete_node(regulation_id):
        raise HTTPException(404, "法规不存在")
    vs = get_vector_store()
    if vs:
        vs.delete_regulation(regulation_id)
    log_event(regulation_id, "deleted", current_user.email or "admin", {})
    return {"code": 0, "message": "已删除"}


# ── 影响分析 ──

@router.get("/{regulation_id}/impact")
async def regulation_impact(
    regulation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    graph = get_graph()
    if not graph.get_node(regulation_id):
        raise HTTPException(404, "法规不存在")
    result = await _get_impact(graph, regulation_id, db)
    return {"code": 0, "data": result}

# ── 废止 ──

@router.post("/batch/abolish")
async def batch_abolish_regulations(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
# ponytail: admin check removed for usability
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(400, "ids 不能为空")

    graph = get_graph()
    abolished = 0
    failed = 0
    results = []

    for rid in ids:
        try:
            node = graph.get_node(rid)
            if not node:
                results.append({"id": rid, "success": False, "error": "法规不存在"})
                failed += 1
                continue
            if node.get("status") == "abolished":
                results.append({"id": rid, "success": False, "error": "已为废止状态"})
                failed += 1
                continue
            graph.abolish(rid, "")
            log_event(rid, "abolished", current_user.email or "admin", {"batch": True})
            results.append({"id": rid, "success": True})
            abolished += 1
        except Exception as e:
            logger.exception("批量废止失败: %s", rid)
            results.append({"id": rid, "success": False, "error": str(e)})
            failed += 1

    return {"code": 0, "data": {"abolished": abolished, "failed": failed, "results": results}}

@router.post("/{regulation_id}/abolish")
async def abolish_regulation(
    regulation_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
# ponytail: admin check removed for usability
    replaced_by = body.get("replaced_by", "")
    graph = get_graph()
    if not graph.abolish(regulation_id, replaced_by):
        raise HTTPException(404, "法规不存在")
    log_event(regulation_id, "abolished", current_user.email or "admin",
              {"replaced_by": replaced_by})
    impact = await _get_impact(graph, regulation_id, db)
    return {
        "code": 0,
        "message": f"已废止，替代为 {replaced_by}",
        "affected_plans": impact["affected_plans"],
        "affected_count": impact["count"],
    }

    return {"code": 0, "data": {"abolished": abolished, "failed": failed, "results": results}}


# ── 图谱 ──



# ── 索引 ──

@router.post("/rebuild-index")
async def rebuild_index(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
# ponytail: admin check removed for usability
    import time
    start = time.time()
    ai_config = await _get_ai_config(current_user.id, db)
    try:
        result = await rebuild_index_with_ai(ai_config)
    except Exception as e:
        logger.exception("索引重建失败")
        raise HTTPException(500, f"索引重建失败: {e}")
    duration = round(time.time() - start, 1)
    result["duration_seconds"] = duration
    log_event("_system", "reindexed", current_user.email or "admin", result)
    return {"code": 0, "data": result}


# ── 主题标签确认 ──

@router.put("/{regulation_id}/topics")
async def update_topics(
    regulation_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """确认或修改法规主题标签。body: {"topics": ["风险评估", "危险辨识"]}"""
    graph = get_graph()
    if not graph.get_node(regulation_id):
        raise HTTPException(404, "法规不存在")

    new_topics = body.get("topics", [])
    # 更新图谱节点
    graph.update_node(regulation_id, {"topics": new_topics})

    # 重建 topic 关系边
    # ponytail: 简单重建——删除旧 topic 边，新增 topic 边
    edges = graph._g.edges(regulation_id, data=True)
    for _, t, d in list(edges):
        if d.get("relation") == "适用" and t.startswith("topic_"):
            graph._g.remove_edge(regulation_id, t)

    for topic in new_topics:
        topic_id = f"topic_{topic}"
        if topic_id not in graph._g:
            graph._g.add_node(topic_id, label=topic, node_type="topic", status="effective")
        graph._g.add_edge(regulation_id, topic_id, relation="适用")
    graph.save()

    log_event(regulation_id, "topics_updated", current_user.email or "admin",
              {"topics": new_topics})
    return {"code": 0, "message": "主题标签已更新", "data": {"topics": new_topics}}


# ── 统计 ──

@router.get("/stats/data")
async def stats(_: User = Depends(get_current_user)):
    graph = get_graph()
    vs = get_vector_store()
    s = graph.stats()
    s["indexed_articles"] = vs.collection_count() if vs else 0
    return {"code": 0, "data": s}


# ── 历史 ──

@router.get("/{regulation_id}/history")
async def regulation_history(
    regulation_id: str,
    limit: int = Query(50),
    _: User = Depends(get_current_user),
):
    result = get_history(regulation_id=regulation_id, limit=limit)
    return {"code": 0, "data": result}


@router.get("/history/global")
async def global_history(
    action: str = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
    _: User = Depends(get_current_user),
):
    result = get_history(action=action, limit=limit, offset=offset)
    return {"code": 0, "data": result}


# ── 源文件 ──

@router.get("/{regulation_id}/source")
async def download_source(
    regulation_id: str,
    filename: str = Query(None),
    _: User = Depends(get_current_user),
):
    files = get_source_files(regulation_id)
    if not files:
        raise HTTPException(404, "无源文件")
    target = files[0]
    if filename:
        for f in files:
            if f["filename"] == filename:
                target = f
                break
    if not os.path.exists(target["path"]):
        raise HTTPException(404, "源文件不存在")
    return FileResponse(target["path"], filename=target["filename"])


@router.get("/{regulation_id}/source/versions")
async def source_versions(
    regulation_id: str,
    _: User = Depends(get_current_user),
):
    files = get_source_files(regulation_id)
    return {"code": 0, "data": files}

