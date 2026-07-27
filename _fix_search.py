fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\chat_dispatch.py"
with open(fpath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find the article processing loop and add preamble filter
for i, line in enumerate(lines):
    if "if not article_text or len(article_text) < 10:" in line:
        # Insert preamble filter after this line
        filter_code = [
            "            # Skip preamble/metadata blocks (not actual articles)\n",
            "            if len(article_number) > 30 or any(kw in article_number for kw in [\"发布机关\", \"发布日期\", \"施行日期\", \"适用主题\", \"上位法依据\"]):\n",
            "                continue\n",
        ]
        lines[i+1:i+1] = filter_code
        print(f"Preamble filter inserted after line {i+1}")
        break

with open(fpath, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Done")