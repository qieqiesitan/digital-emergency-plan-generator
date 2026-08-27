fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\regulations\sync.py"
with open(fpath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Replace lines 201-210 (the for loop body) with fixed version
new_lines = [
    "    for i, m in enumerate(matches):\n",
    "        # 用 match 对象精确分离编号和正文\n",
    "        number = m.group().strip()\n",
    '        number = _re.sub(r"^[#\\s\\u3000]*", "", number).strip()\n',
    "        start = m.end()\n",
    "        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)\n",
    "        body = text[start:end].strip()\n",
    "        if body and len(body) > 5:\n",
    '            articles.append({"number": number, "text": body[:5000]})\n',
]

lines[201:211] = new_lines
with open(fpath, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Fixed _extract_articles_from_text (lines 201-210)")