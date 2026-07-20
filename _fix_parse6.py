fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\regulations\sync.py"
with open(fpath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Lines 200-201: remove the duplicate for and fix body
lines[200] = "        # 用 match 对象精确分离编号和正文\n"
lines[201] = "        number = m.group().strip()\n"
lines[202] = '        number = _re.sub(r"^[#\\s\\u3000]*", "", number).strip()\n'
lines[203] = "        start = m.end()\n"
lines[204] = "        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)\n"
lines[205] = "        body = text[start:end].strip()\n"
lines[206] = "        if body and len(body) > 5:\n"
lines[207] = '            articles.append({"number": number, "text": body[:5000]})\n'

# Remove the duplicate for line at original index 200
# The correct structure should be:
# 199: for i, m in enumerate(matches):
# 200:     # 用 match 对象...
# ...
# So I need to keep lines[199] as is and start body at 200

with open(fpath, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Fixed")