import pathlib
file_path = pathlib.Path(r"C:\Users\55061\Documents\数字化预案自动生成 2\backend\app\services\risk_assessment_service.py")

# The file was double-encoded: original UTF-8 → read as GBK by PowerShell → written as UTF-8
# Reverse: read as UTF-8 bytes → decode as UTF-8 string → encode as GBK → decode as UTF-8
raw_bytes = file_path.read_bytes()
# Skip BOM if present
if raw_bytes[:3] == b'\xef\xbb\xbf':
    raw_bytes = raw_bytes[3:]
    
try:
    # Decode current content as UTF-8 (how it was written)
    garbled = raw_bytes.decode("utf-8")
    # Reverse: encode as GBK (how PowerShell read it), then decode as UTF-8 (how it originally was)
    fixed = garbled.encode("gbk", errors="replace").decode("utf-8", errors="replace")
    # Check if the fix worked by looking for known pattern
    if 'raise ValueError("' in fixed and fixed.count('raise ValueError("') > 1:
        print("FIX_OK: double-encoding reversed successfully")
    else:
        print("FIX_PARTIAL: some corruption may remain")
except Exception as e:
    print(f"FIX_FAILED: {e}")
    # Fallback: try reading as is
    fixed = raw_bytes.decode("utf-8-sig")
    
# Now insert the missing functions before the chapter batch engine separator
new_funcs = '''# L/S value normalizers
_LS_TEXT_MAP = {"\u9ad8": 4, "\u4e2d": 3, "\u4f4e": 2, "\u8f83\u9ad8": 4, "\u8f83\u4f4e": 2, "\u5f88\u9ad8": 5, "\u5f88\u4f4e": 1}

def _to_l_num(val):
    if isinstance(val, int):
        return max(1, min(5, val))
    if isinstance(val, str):
        v = val.strip()
        if v.isdigit():
            return max(1, min(5, int(v)))
        for k, num in sorted(_LS_TEXT_MAP.items(), key=lambda x: -len(x[0])):
            if k in v:
                return num
    return 3

def _to_s_num(val):
    if isinstance(val, int):
        return max(1, min(5, val))
    if isinstance(val, str):
        v = val.strip()
        if v.isdigit():
            return max(1, min(5, int(v)))
        for k, num in sorted(_LS_TEXT_MAP.items(), key=lambda x: -len(x[0])):
            if k in v:
                return num
    return 3


'''

separator = "# ============================================================\n"
idx = fixed.find(separator)
if idx == -1:
    print("ERROR: separator not found in fixed content")
    # Try without the trailing newline
    idx = fixed.find("# ============================================================")
    
if idx >= 0:
    # Check if functions already exist
    if "_to_l_num" not in fixed:
        fixed = fixed[:idx] + new_funcs + fixed[idx:]
        print("Functions inserted")
    else:
        print("Functions already exist")
    file_path.write_text(fixed, encoding="utf-8")
    print("File written successfully")
else:
    print("ERROR: could not find insertion point")
