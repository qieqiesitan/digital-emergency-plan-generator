fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\regulations\sync.py"
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()

# Find the exact function boundaries
start_marker = "def _extract_articles_from_text(text: str) -> list[dict]:"
end_marker = "async def ai_parse"

idx_start = content.index(start_marker)
idx_end = content.index(end_marker, idx_start)

# Build the correct function
new_func = """def _extract_articles_from_text(text: str) -> list[dict]:
    \"\"\"从法规原文中提取所有条文，逐条编号。\"\"\"
    import re as _re
    articles = []
    # 匹配 "第X条" 模式
    pattern = _re.compile(
        r\"(?:^|\n)[\s\u3000]*(?:#+[\s\u3000]*)?第[\s\u3000]*\"
        r\"(?:[零一二三四五六七八九十百千\d]+)\"
        r\"[\s\u3000]*条\",
        _re.MULTILINE
    )
    matches = list(pattern.finditer(text))
    if not matches:
        # 兜底：按数字编号分割
        pattern2 = _re.compile(r\"(?:^|\n)[\s\u3000]*(?:#+[\s\u3000]*)?(\d+)[.、）]\s*\", _re.MULTILINE)
        matches = list(pattern2.finditer(text))
    if not matches:
        return [{\"number\": \"全文\", \"text\": text.strip()[:5000]}]
    for i, m in enumerate(matches):
        number = m.group().strip()
        number = _re.sub(r\"^[#\s\u3000]*\", \"\", number).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body and len(body) > 5:
            articles.append({\"number\": number, \"text\": body[:5000]})
    return articles

"""

content = content[:idx_start] + new_func + "\n\n" + content[idx_end:]

with open(fpath, "w", encoding="utf-8") as f:
    f.write(content)
print("Complete function replacement done")