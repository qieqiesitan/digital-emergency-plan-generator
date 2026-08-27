fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\regulations\sync.py"
with open(fpath, "r", encoding="utf-8") as f:
    content = f.read()

old_func = '''    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if not block:
            continue
        lines_b = block.split("\\n", 1)
        number = _re.sub(r"^[#\\s\\u3000]*", "", lines_b[0]).strip()
        body = lines_b[1].strip() if len(lines_b) > 1 else ""
        if body and len(body) > 5:
            articles.append({"number": number, "text": body[:5000]})'''

new_func = '''    for i, m in enumerate(matches):
        # 使用 match 对象精确分离编号和正文
        number = m.group().strip()
        number = _re.sub(r"^[#\\s\\u3000]*", "", number).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body and len(body) > 5:
            articles.append({"number": number, "text": body[:5000]})'''

assert old_func in content, "Could not find old function body"
content = content.replace(old_func, new_func, 1)
with open(fpath, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed _extract_articles_from_text")