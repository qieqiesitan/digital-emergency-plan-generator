fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\regulations\sync.py"
with open(fpath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# PARSE_PROMPT = lines 147-197 (0-indexed)
new_meta = [
    'PARSE_META_PROMPT = """你是一位安全生产法规数据库录入助手。请从以下法规/标准全文文本中提取元数据。\n',
    '\n',
    '输入文本（仅展示开头部分）：\n',
    '{raw_text}\n',
    '\n',
    "请仔细提取以下字段：\n",
    "\n",
    "1. 法规编号：从文本开头或标题附近查找（如 GB/T 29639-2020、主席令第88号等）\n",
    "2. 法规全称：文本开头或标题行的完整名称\n",
    "3. 发布机关：发布日期前的发文机关全称\n",
    "4. 发布日期\n",
    "5. 施行日期\n",
    "6. 替代关系：查找替代、代替、废止等关键词\n",
    "7. 上位法依据：通常在依据、根据后列出\n",
    "8. 适用主题标签：从标准列表中选择1-5个\n",
    "9. 法规类型：law（法律）、standard（标准）、policy（政策）\n",
    "\n",
    "只返回纯JSON，不要任何解释文字：\n",
    '{\n',
    '  "code": "GB/T 29639-2020",\n',
    '  "full_name": "生产经营单位生产安全事故应急预案编制导则",\n',
    '  "issuing_body": "国家市场监督管理总局、国家标准化管理委员会",\n',
    '  "issue_date": "2020年9月29日",\n',
    '  "effective_date": "2021年4月1日",\n',
    '  "replaces": ["GB/T 29639-2013"],\n',
    '  "based_on": ["中华人民共和国安全生产法", "生产安全事故应急预案管理办法"],\n',
    '  "node_type": "standard",\n',
    '  "topics": ["应急预案编制", "应急管理", "应急演练"]\n',
    '}"""\n',
]

# Replace PARSE_PROMPT with PARSE_META_PROMPT
lines[147:198] = new_meta  # 147-197 inclusive, so 198 is exclusive
print(f"Replaced PARSE_PROMPT (lines 147-197) with PARSE_META_PROMPT ({len(new_meta)} lines)")

# Now find async def ai_parse and insert _extract_articles_from_text before it
ai_parse_idx = None
for i, line in enumerate(lines):
    if "async def ai_parse" in line:
        ai_parse_idx = i
        break
print(f"async def ai_parse at line {ai_parse_idx}")

# Insert the extraction function before ai_parse
extract_func = [
    "\n",
    "# ── 条文程序化提取（替代 LLM 提取，解决长文本截断问题）──\n",
    "\n",
    "\n",
    "def _extract_articles_from_text(text: str) -> list[dict]:\n",
    '    """从法规原文中提取所有条文，逐条编号。"""\n',
    "    import re as _re\n",
    "    articles = []\n",
    "    # 匹配第X条模式\n",
    '    pattern = _re.compile(\n',
    '        r"(?:^|\\n)[\\s　]*(?:#+[\\s　]*)?第[\\s　]*"\n',
    '        r"(?:[零一二三四五六七八九十百千\\d]+)"\n',
    '        r"[\\s　]*条",\n',
    "        _re.MULTILINE\n",
    "    )\n",
    "    matches = list(pattern.finditer(text))\n",
    "    if not matches:\n",
    '        # 兜底：按数字编号分割\n',
    '        pattern2 = _re.compile(r"(?:^|\\n)[\\s　]*(?:#+[\\s　]*)?(\\d+)[.、）]\\s*", _re.MULTILINE)\n',
    "        matches = list(pattern2.finditer(text))\n",
    "    if not matches:\n",
    '        return [{"number": "全文", "text": text.strip()[:5000]}]\n',
    "    for i, m in enumerate(matches):\n",
    "        start = m.start()\n",
    "        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)\n",
    "        block = text[start:end].strip()\n",
    "        if not block:\n",
    "            continue\n",
    '        lines_b = block.split("\\n", 1)\n',
    '        number = _re.sub(r"^[#\\s　]*", "", lines_b[0]).strip()\n',
    "        body = lines_b[1].strip() if len(lines_b) > 1 else \"\"\n",
    "        if body and len(body) > 5:\n",
    '            articles.append({"number": number, "text": body[:5000]})\n',
    "    return articles\n",
    "\n",
    "\n",
]

lines[ai_parse_idx:ai_parse_idx] = extract_func
print(f"Inserted _extract_articles_from_text before line {ai_parse_idx} ({len(extract_func)} lines)")
# Update ai_parse_idx
ai_parse_idx += len(extract_func)

# Now modify the ai_parse function body
# Find the line with "prompt = PARSE_PROMPT.replace"
prompt_line = None
for i in range(ai_parse_idx, min(ai_parse_idx + 50, len(lines))):
    if 'PARSE_PROMPT.replace' in lines[i]:
        prompt_line = i
        break
print(f"PARSE_PROMPT.replace at line {prompt_line}")

# Find the end of the function (next function def or EOF)
func_end = None
for i in range(ai_parse_idx, len(lines)):
    if lines[i].startswith("def ") or lines[i].startswith("async def ") and i > ai_parse_idx:
        func_end = i
        break
if func_end is None:
    func_end = len(lines)
print(f"Function ends at line {func_end}")

new_body = [
    '    # ── 两阶段解析：AI 提取元数据 + 程序化提取条文 ──\n',
    '    preview = raw_text[:5000]\n',
    '    prompt = PARSE_META_PROMPT.replace("{raw_text}", preview)\n',
    '\n',
    '    payload = {\n',
    '        "model": ai_config.model_name,\n',
    '        "messages": [\n',
    '            {"role": "system", "content": "你是一个精确的JSON数据提取器。只输出JSON，不要解释。"},\n',
    '            {"role": "user", "content": prompt},\n',
    '        ],\n',
    '        "temperature": 0.1,\n',
    '        "max_tokens": min(4096, ai_config.max_tokens or 16384),\n',
    "    }\n",
    "\n",
    "    import httpx\n",
    "    from app.routers.generation import _decrypt_api_key\n",
    "    try:\n",
    "        api_key = _decrypt_api_key(ai_config.api_key_encrypted)\n",
    "    except Exception:\n",
    '        raise Exception("API Key 解密失败，请前往 设置->AI配置 重新输入并保存 API Key")\n',
    "\n",
    "    base = ai_config.base_url or {\n",
    '        "openai": "https://api.openai.com/v1",\n',
    '        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",\n',
    '        "deepseek": "https://api.deepseek.com/v1",\n',
    "    }.get(ai_config.provider, \"\")\n",
    "\n",
    "    async with httpx.AsyncClient(timeout=600) as client:\n",
    '        resp = await client.post(\n',
    '            f"{base}/chat/completions",\n',
    "            json=payload,\n",
    '            headers={"Authorization": f"Bearer {api_key}"},\n',
    "        )\n",
    "        if resp.status_code != 200:\n",
    "            detail = resp.text[:500]\n",
    '            if "Invalid API Key" in detail or "invalid" in detail.lower():\n',
    '                raise Exception("DeepSeek API Key 无效，请前往 设置->AI配置 输入正确的 API Key")\n',
    '            raise Exception(f"AI API 错误 (HTTP {resp.status_code}): {detail}")\n',
    "\n",
    "        data = resp.json()\n",
    '        logger.info("AI parse status: %s, model: %s", resp.status_code, data.get("model", ""))\n',
    '        text = data["choices"][0]["message"]["content"]\n',
    "\n",
    "        # 解析元数据 JSON\n",
    "        import re as _re\n",
    "        import json as _json\n",
    "        metadata = None\n",
    "        for extractor in [\n",
    "            lambda t: _json.loads(t),\n",
    '            lambda t: _json.loads(_re.search(r"```(?:json)?[\\s]*\\n?(.*?)\\n?```", t, _re.DOTALL).group(1)) if _re.search(r"```(?:json)?[\\s]*\\n?(.*?)\\n?```", t, _re.DOTALL) else None,\n',
    '            lambda t: _json.loads(_re.search(r"\\{.*\\}", t, _re.DOTALL).group(0)) if _re.search(r"\\{.*\\}", t, _re.DOTALL) else None,\n',
    "        ]:\n",
    "            try:\n",
    "                metadata = extractor(text)\n",
    "                if metadata:\n",
    "                    break\n",
    "            except (_json.JSONDecodeError, AttributeError, IndexError):\n",
    "                continue\n",
    "\n",
    "        if not metadata:\n",
    '            logger.warning("AI parse failed - raw: %s", text[:300])\n',
    '            raise Exception("AI 返回内容不是合法 JSON，请重试。如持续失败，可能是 API Key 无效或余额不足")\n',
    "\n",
    "    # 第二阶段：程序化提取全部条文\n",
    "    articles = _extract_articles_from_text(raw_text)\n",
    '    metadata["articles"] = articles\n',
    '    logger.info("AI parse done: %d articles extracted (AI metadata + local articles)", len(articles))\n',
    "    return metadata\n",
    "\n",
]

lines[prompt_line:func_end] = new_body

with open(fpath, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Done - file written")