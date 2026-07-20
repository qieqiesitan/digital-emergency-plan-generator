import re as _re

fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\regulations\sync.py"
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()

# ── Step 1: Split PARSE_PROMPT into PARSE_META_PROMPT + remove articles instruction ──
old_prompt_start = 'PARSE_PROMPT = """你是一位安全生产法规数据库录入助手。请从以下法规/标准全文文本中提取结构化信息。'
old_prompt_end = '  "articles": [{"number": "第一条", "text": "..."}, {"number": "第二条", "text": "..."}]\n}"""'
new_prompt = """PARSE_META_PROMPT = \"\"\"你是一位安全生产法规数据库录入助手。请从以下法规/标准全文文本中提取元数据。

输入文本（仅展示开头部分）：
{raw_text}

请仔细提取以下字段：

1. 法规编号：从文本开头或标题附近查找（如 GB/T 29639-2020、主席令第88号等）
2. 法规全称：文本开头或标题行的完整名称
3. 发布机关：发布日期前的发文机关全称
4. 发布日期
5. 施行日期
6. 替代关系：查找"替代"、"代替"、"废止"等关键词
7. 上位法依据：通常在"依据"、"根据"后列出
8. 适用主题标签：从 [风险评估、危险辨识、危险化学品、重大危险源、事故分类、应急管理、应急预案、应急预案编制、应急演练、应急响应、应急救援、应急救援物资、应急资源、应急资源调查、消防安全、灭火器、特殊作业、安全培训、安全评价、职业健康、特种设备、备案、演练、评估] 中选择1-5个
9. 法规类型：law（法律）、standard（标准）、policy（政策）

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
  "topics": ["应急预案编制", "应急管理", "应急演练"]
}\"\"\" """

# Find old PARSE_PROMPT and replace with META only
old_prompt_re = r"PARSE_PROMPT = .*?  \"articles\": \[.*?\}\]\n\}""""
# Actually easier: split by boundaries
old_start = "PARSE_PROMPT = \"\"\"你是一位安全生产法规数据库录入助手。请从以下法规/标准全文文本中提取结构化信息。"
old_end = '  "articles": [{"number": "第一条", "text": "..."}, {"number": "第二条", "text": "..."}]\n}"""'

assert old_start in content, "PARSE_PROMPT start not found"
assert old_end in content, "PARSE_PROMPT end not found"

old_prompt_full = content[content.index(old_start):content.index(old_end) + len(old_end)]
content = content.replace(old_prompt_full, new_prompt.strip(), 1)
print("Step 1: PARSE_PROMPT replaced with PARSE_META_PROMPT")

# ── Step 2: Add _extract_articles_from_text function ──
func_code = '''

# ── 条文程序化提取（替代 LLM 提取，解决长文本截断问题）──

def _extract_articles_from_text(text: str) -> list[dict]:
    """从法规原文中提取所有条文，逐条编号。"""
    articles = []
    # 匹配 "第X条" 模式（支持中文数字、阿拉伯数字、空格变体）
    # 例：第一条、第1条、第 一 条、第一百二十条
    pattern = _re.compile(
        r"(?:^|\\n)[\\s　]*(?:#+[\\s　]*)?第[\\s　]*"
        r"(?:[零一二三四五六七八九十百千\d]+)"
        r"[\\s　]*条",
        _re.MULTILINE
    )
    
    # Find all article positions
    matches = list(pattern.finditer(text))
    if not matches:
        # Fallback 1: try "X." or "X）" numbered list pattern
        pattern2 = _re.compile(r"(?:^|\\n)[\\s　]*(?:#+[\\s　]*)?(\\d+)[.、）]\\s*", _re.MULTILINE)
        matches = list(pattern2.finditer(text))
    
    if not matches:
        # Fallback 2: treat the whole text as one article
        return [{"number": "全文", "text": text.strip()[:5000]}]
    
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if not block:
            continue
        lines = block.split("\\n", 1)
        number = _re.sub(r"^[#\\s　]*", "", lines[0]).strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if body and len(body) > 5:
            articles.append({"number": number, "text": body[:5000]})
    
    return articles
'''

# Insert after the PARSE_META_PROMPT definition (before ai_parse function)
insert_point = "async def ai_parse(raw_text: str, ai_config) -> dict:"
content = content.replace(insert_point, func_code + "\\n\\n" + insert_point, 1)
print("Step 2: _extract_articles_from_text added")

# ── Step 3: Replace ai_parse body ──
old_body_start = '    prompt = PARSE_PROMPT.replace("{raw_text}", raw_text)'
old_body_end = '        raise Exception("AI 返回内容不是合法 JSON，请重试。如持续失败，可能是 API Key 无效或余额不足")'

new_body = '''    # ── 两阶段解析：AI 提取元数据 + 程序化提取条文 ──
    # 元数据 prompt（仅取前 5000 字符，避免超长文本导致 max_tokens 不足）
    preview = raw_text[:5000]
    prompt = PARSE_META_PROMPT.replace("{raw_text}", preview)

    payload = {
        "model": ai_config.model_name,
        "messages": [
            {"role": "system", "content": "你是一个精确的JSON数据提取器。只输出JSON，不要解释。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": min(4096, ai_config.max_tokens or 16384),
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
        logger.info("AI parse status: %s, model: %s", resp.status_code, data.get("model", ""))
        text = data["choices"][0]["message"]["content"]

        # 解析元数据 JSON
        metadata = None
        for extractor in [
            lambda t: json.loads(t),
            lambda t: json.loads(_re.search(r"```(?:json)?[\\s]*\\n?(.*?)\\n?```", t, _re.DOTALL).group(1).strip()) if _re.search(r"```(?:json)?[\\s]*\\n?(.*?)\\n?```", t, _re.DOTALL) else None,
            lambda t: json.loads(_re.search(r"\{.*\}", t, _re.DOTALL).group(0)) if _re.search(r"\{.*\}", t, _re.DOTALL) else None,
        ]:
            try:
                metadata = extractor(text)
                if metadata:
                    break
            except (json.JSONDecodeError, AttributeError, IndexError):
                continue

        if not metadata:
            logger.warning("AI parse failed - raw: %s", text[:300])
            raise Exception("AI 返回内容不是合法 JSON，请重试。如持续失败，可能是 API Key 无效或余额不足")

    # 第二阶段：程序化提取全部条文
    articles = _extract_articles_from_text(raw_text)
    metadata["articles"] = articles
    logger.info("AI parse done: %d articles extracted (AI metadata + local articles)", len(articles))
    return metadata'''

content = content.replace(old_body_start, new_body, 1)
print("Step 3: ai_parse body replaced")

with open(fpath, "w", encoding="utf-8") as f:
    f.write(content)
print("Done - file written")