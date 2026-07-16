"""法规数据同步引擎 — AI解析 + 入库 + 废止 + 文件提取 + 历史日志。"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from io import BytesIO

import yaml

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TEXTS_DIR = os.path.join(DATA_DIR, "texts")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
HISTORY_PATH = os.path.join(DATA_DIR, "history.jsonl")
INDEX_PATH = os.path.join(DATA_DIR, "index.yaml")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_id():
    import uuid
    return uuid.uuid4().hex[:12]


# ── 文件提取 ──

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """PyMuPDF 提取PDF纯文本。"""
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        t = page.get_text()
        if t:
            text_parts.append(t)
    doc.close()
    return "\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """python-docx 提取Word纯文本。"""
    import docx
    doc = docx.Document(BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(file_bytes: bytes, filename: str) -> str:
    """根据文件扩展名自动选择提取方式。"""
    fn = filename.lower()
    if fn.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif fn.endswith(".docx") or fn.endswith(".doc"):
        return extract_text_from_docx(file_bytes)
    elif fn.endswith(".md") or fn.endswith(".markdown") or fn.endswith(".txt"):
        return file_bytes.decode("utf-8")
    else:
        raise ValueError(f"不支持的文件格式: {filename}")


# ── 源文件存储 ──

def save_source_file(regulation_id: str, file_bytes: bytes, filename: str) -> str:
    """保存源文件到 data/uploads/{reg_id}/。返回保存路径。"""
    reg_dir = os.path.join(UPLOADS_DIR, regulation_id)
    os.makedirs(reg_dir, exist_ok=True)

    # 加时间戳避免重名覆盖
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = f"{ts}_{filename}"
    fpath = os.path.join(reg_dir, safe_name)
    with open(fpath, "wb") as f:
        f.write(file_bytes)
    logger.info("源文件已保存: %s", fpath)
    return fpath


def get_source_files(regulation_id: str) -> list[dict]:
    """获取某法规的所有源文件。"""
    reg_dir = os.path.join(UPLOADS_DIR, regulation_id)
    if not os.path.isdir(reg_dir):
        return []
    files = []
    for fn in sorted(os.listdir(reg_dir), reverse=True):
        fpath = os.path.join(reg_dir, fn)
        stat = os.stat(fpath)
        files.append({
            "filename": fn,
            "size": stat.st_size,
            "uploaded_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "path": fpath,
        })
    return files


# ── 历史日志 ──

def log_event(regulation_id: str, action: str, operator: str,
              detail: dict = None) -> str:
    """追加一条事件到 history.jsonl。返回 event_id。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    event = {
        "event_id": _event_id(),
        "timestamp": _now(),
        "regulation_id": regulation_id,
        "action": action,
        "operator": operator,
        "detail": detail or {},
    }
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event["event_id"]


def get_history(regulation_id: str = None, action: str = None,
                limit: int = 50, offset: int = 0) -> dict:
    """读取变更日志，支持筛选 + 分页。"""
    if not os.path.exists(HISTORY_PATH):
        return {"items": [], "total": 0}

    events = []
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                if regulation_id and evt.get("regulation_id") != regulation_id:
                    continue
                if action and evt.get("action") != action:
                    continue
                events.append(evt)
            except json.JSONDecodeError:
                continue

    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    total = len(events)
    return {"items": events[offset:offset + limit], "total": total}


# ── AI 解析 ──

PARSE_PROMPT = """你是一位安全生产法规数据库录入助手。请从以下法规/标准全文文本中提取结构化信息。

输入文本：
{raw_text}

请仔细提取以下字段。注意：编号、日期、替代关系、上位法依据是必须精确提取的核心字段！

1. 法规编号（核心字段）：从文本开头或标题附近查找，常见格式有：
   - 国家标准：GB/T 29639-2020、GB 18218-2018 等
   - 主席令：主席令第88号、中华人民共和国主席令第XX号
   - 部门规章：应急管理部令第X号、安监总局令第XX号
   - 行业标准：AQ/T 9002-2006 等
   如果文本中确实没有编号，则写"未提供"，但务必仔细查找！

2. 法规全称：文本开头或标题行的完整名称

3. 发布机关：发布日期前的发文机关全称

4. 发布日期：常见格式如"2020年3月6日发布"、"二〇二〇年三月六日"

5. 施行日期（核心字段）：常见格式"自2020年10月1日起施行"、"2021年6月1日实施"

6. 替代关系（核心字段）：查找"替代"、"代替"、"废止"等关键词，列出被替代的法规编号
   例：["GB/T 29639-2013", "AQ/T 9002-2006"]

7. 上位法依据（核心字段）：通常在"依据"、"根据"后列出，如"根据《中华人民共和国安全生产法》"等

8. 适用主题标签：必须从以下标准列表中选择1-5个最匹配的：
   风险评估、危险辨识、危险化学品、重大危险源、事故分类、
   应急管理、应急预案、应急预案编制、应急演练、应急响应、
   应急救援、应急救援物资、应急资源、应急资源调查、
   消防安全、灭火器、特殊作业、安全培训、安全评价、
   职业健康、特种设备、备案、演练、评估

9. 法规类型：law（法律）、standard（标准）、policy（政策）

10. 条文清单：按条款编号逐条提取，每条标注"第X条"编号和完整原文，不要合并或省略

只返回纯JSON，不要任何解释文字：
{
  "code": "GB/T 29639-2020",
  "full_name": "生产经营单位生产安全事故应急预案编制导则",
  "issuing_body": "国家市场监督管理总局、国家标准化管理委员会",
  "issue_date": "2020年9月29日",
  "effective_date": "2021年4月1日",
  "replaces": ["GB/T 29639-2013"],
  "based_on": ["中华人民共和国安全生产法", "生产安全事故应急预案管理办法"],
  "node_type": "standard",
  "topics": ["应急预案编制", "应急管理", "应急演练"],
  "articles": [{"number": "第一条", "text": "..."}, {"number": "第二条", "text": "..."}]
}"""


async def ai_parse(raw_text: str, ai_config) -> dict:
    """调用 AI API 解析法规全文。"""
    import httpx

    from app.routers.generation import _decrypt_api_key
    try:
        api_key = _decrypt_api_key(ai_config.api_key_encrypted)
    except Exception:
        raise Exception("API Key 解密失败，请前往 设置->AI配置 重新输入并保存 API Key")

    base = ai_config.base_url or {
        "openai": "https://api.openai.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }.get(ai_config.provider, "")

    prompt = PARSE_PROMPT.replace("{raw_text}", raw_text)

    payload = {
        "model": ai_config.model_name,
        "messages": [
            {"role": "system", "content": "你是一个精确的JSON数据提取器。只输出JSON，不要解释。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": ai_config.max_tokens,
        
    }

    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(
            f"{base}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code != 200:
            detail = resp.text[:500]
            if "Invalid API Key" in detail or "invalid" in detail.lower():
                raise Exception("DeepSeek API Key 无效，请前往 设置->AI配置 输入正确的 API Key")
            raise Exception(f"AI API 错误 (HTTP {resp.status_code}): {detail}")

        data = resp.json()
        logger.info("DeepSeek response status: %s, model: %s", resp.status_code, data.get("model", ""))
        text = data["choices"][0]["message"]["content"]

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 提取 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?[\s]*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 提取第一个 { ... } 对象
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("AI raw response (first 500 chars): %s", text[:500])
        raise Exception("AI 返回内容不是合法 JSON，请重试。如持续失败，可能是 API Key 无效或余额不足")


# ── 入库 ──

def ingest_regulation(parsed: dict, regulation_id: str,
                      operator: str = "admin",
                      source_file_bytes: bytes = None,
                      source_filename: str = None) -> str:
    """
    确认入库一条法规：
    1. 保存源文件（如有）
    2. 写入 texts/*.md 条文原文
    3. 写入 graph.json 节点 + 关系边
    4. 写入 history.jsonl
    """
    from app.regulations import get_graph

    graph = get_graph()
    os.makedirs(TEXTS_DIR, exist_ok=True)

    # 1. 保存源文件
    source_path = None
    if source_file_bytes and source_filename:
        source_path = save_source_file(regulation_id, source_file_bytes, source_filename)

    # 2. 写入条文原文 Markdown
    lines = [f"# {parsed['code']} {parsed['full_name']}", ""]
    lines.append(f"- 发布机关：{parsed.get('issuing_body', '未提供')}")
    lines.append(f"- 发布日期：{parsed.get('issue_date', '未提供')}")
    lines.append(f"- 施行日期：{parsed.get('effective_date', '未提供')}")
    if parsed.get("replaces"):
        lines.append(f"- 替代：{', '.join(parsed['replaces'])}")
    if parsed.get("based_on"):
        lines.append(f"- 上位法依据：{', '.join(parsed['based_on'])}")
    if parsed.get("topics"):
        lines.append(f"- 适用主题：{', '.join(parsed['topics'])}")
    lines.append("")
    lines.append("---")
    lines.append("")
    for art in parsed.get("articles", []):
        lines.append(f"## {art['number']}")
        lines.append("")
        lines.append(art['text'])
        lines.append("")

    md_path = os.path.join(TEXTS_DIR, f"{regulation_id}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 3. 写入图谱节点
    node = {
        "id": regulation_id,
        "label": parsed["code"],
        "full_name": parsed["full_name"],
        "node_type": parsed.get("node_type", "standard"),
        "code": parsed["code"],
        "version": parsed.get("version", ""),
        "effective_date": parsed.get("effective_date", ""),
        "issuing_body": parsed.get("issuing_body", ""),
        "status": "effective",
        "topics": parsed.get("topics", []),
        "ai_topics": parsed.get("topics", []),
        "article_count": len(parsed.get("articles", [])),
        "source": "ai_parsed",
    }
    graph.add_node(node)

    # 4. 添加关系边
    for replaced_code in parsed.get("replaces", []):
        for nid, ndata in graph._g.nodes(data=True):
            if ndata.get("code") == replaced_code:
                graph.add_edge(regulation_id, nid, relation="替代")
                graph.abolish(nid, replaced_by=regulation_id)
                break

    for based_code in parsed.get("based_on", []):
        for nid, ndata in graph._g.nodes(data=True):
            if ndata.get("code") == based_code or ndata.get("label") == based_code:
                graph.add_edge(regulation_id, nid, relation="下位法")
                break

    for topic in parsed.get("topics", []):
        topic_id = f"topic_{topic}"
        if topic_id not in graph._g:
            graph.add_node({"id": topic_id, "label": topic, "node_type": "topic"})
        graph.add_edge(regulation_id, topic_id, relation="适用")

    # 5. 历史日志
    log_event(regulation_id, "created", operator, {
        "via": "upload" if source_path else "paste",
        "filename": source_filename,
        "file_size": len(source_file_bytes) if source_file_bytes else 0,
        "article_count": len(parsed.get("articles", [])),
    })

    logger.info("法规入库完成: %s (%d条条文)", regulation_id, len(parsed.get("articles", [])))
    return regulation_id


# ── 索引管理 ──

async def rebuild_index_with_ai(ai_config) -> dict:
    """使用 AI API 的 embedding 重建向量索引。"""
    import httpx

    from app.routers.generation import _decrypt_api_key
    try:
        api_key = _decrypt_api_key(ai_config.api_key_encrypted)
    except Exception:
        raise Exception("API Key 解密失败，请前往 设置->AI配置 重新输入并保存 API Key")

    base = ai_config.base_url or {
        "openai": "https://api.openai.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
    }.get(ai_config.provider, "")

    async def embedding_fn(texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base}/embeddings",
                json={"model": "text-embedding-3-small", "input": texts},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                raise Exception(f"Embedding失败: {resp.status_code}")
            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    from app.regulations import get_vector_store
    vs = get_vector_store()
    result = vs.rebuild_all(embedding_fn)
    return result
