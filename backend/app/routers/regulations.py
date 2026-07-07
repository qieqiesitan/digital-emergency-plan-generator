"""法规库管理 API — CRUD + AI解析 + 废止 + 图谱 + 索引 + 历史 + 源文件。"""

import json
import logging
import os
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.enterprise import AIConfig
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
    indexed_count = vs.collection_count()
    for item in result["items"]:
        item["indexed"] = True  # ponytail: 简化
    result["indexed_articles"] = indexed_count
    return {"code": 0, "data": result}


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
    raw_text: str = Form(None),
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file:
        content = await file.read()
        try:
            raw_text = extract_text(content, file.filename)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if not raw_text or not raw_text.strip():
        raise HTTPException(400, "请粘贴全文或上传 PDF/Word 文件")

    ai_config = await _get_ai_config(current_user.id, db)
    try:
        result = await ai_parse(raw_text, ai_config)
    except Exception as e:
        logger.exception("AI解析失败")
        raise HTTPException(500, f"AI解析失败: {e}")

    return {"code": 0, "data": result}


# ── 入库 ──

@router.post("")
async def create_regulation(
    data: str = Form(...),
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(current_user)
    parsed = json.loads(data)
    code = parsed.get("code", "")
    if not code:
        raise HTTPException(400, "法规编号不能为空")

    # 生成 regulation_id
    import re as _re
    safe = _re.sub(r"[^a-zA-Z0-9_]", "_", code.lower())
    reg_id = f"reg_{safe}"

    file_bytes = None
    filename = None
    if file:
        file_bytes = await file.read()
        filename = file.filename

    try:
        ingest_regulation(parsed, reg_id, operator=current_user.username or "admin",
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
    await _require_admin(current_user)
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

    log_event(regulation_id, "updated", current_user.username or "admin",
              {"changed_fields": list(parsed.keys()), "filename": filename})
    return {"code": 0, "message": "已更新"}


# ── 删除 ──

@router.delete("/{regulation_id}")
async def delete_regulation(
    regulation_id: str,
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    graph = get_graph()
    if not graph.delete_node(regulation_id):
        raise HTTPException(404, "法规不存在")
    vs = get_vector_store()
    vs.delete_regulation(regulation_id)
    log_event(regulation_id, "deleted", current_user.username or "admin", {})
    return {"code": 0, "message": "已删除"}


# ── 废止 ──

@router.post("/{regulation_id}/abolish")
async def abolish_regulation(
    regulation_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    replaced_by = body.get("replaced_by", "")
    graph = get_graph()
    if not graph.abolish(regulation_id, replaced_by):
        raise HTTPException(404, "法规不存在")
    log_event(regulation_id, "abolished", current_user.username or "admin",
              {"replaced_by": replaced_by})
    return {"code": 0, "message": f"已废止，替代为 {replaced_by}"}


# ── 图谱 ──

@router.get("/graph/data")
async def graph_data(_: User = Depends(get_current_user)):
    graph = get_graph()
    return {"code": 0, "data": {
        "nodes": graph.all_nodes(),
        "edges": graph.get_edges(),
    }}


# ── 索引 ──

@router.post("/rebuild-index")
async def rebuild_index(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(current_user)
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
    log_event("_system", "reindexed", current_user.username or "admin", result)
    return {"code": 0, "data": result}


# ── 统计 ──

@router.get("/stats/data")
async def stats(_: User = Depends(get_current_user)):
    graph = get_graph()
    vs = get_vector_store()
    s = graph.stats()
    s["indexed_articles"] = vs.collection_count()
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
