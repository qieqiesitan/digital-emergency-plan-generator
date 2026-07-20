fpath = r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\regulations\sync.py"
with open(fpath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find PARSE_PROMPT boundaries (from line with "PARSE_PROMPT =" to line with final """)
parse_start = None
parse_end = None
for i, line in enumerate(lines):
    if 'PARSE_PROMPT =' in line:
        parse_start = i
    elif parse_start is not None and '"""' in line and i > parse_start + 1:
        parse_end = i
        break

print(f"PARSE_PROMPT lines {parse_start} to {parse_end}")
print(f"First line: {lines[parse_start].rstrip()}")
print(f"Last line: {lines[parse_end].rstrip()}")