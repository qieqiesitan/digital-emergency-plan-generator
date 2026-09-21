"""B5 运行时验证：法规源文件名净化（`../` 不再越出 uploads 目录）。"""

import os
import shutil
import sys

sys.path.insert(0, "/app")

from app.regulations import sync as reg_sync  # noqa: E402

REG_ID = "b5_probe_reg"
saved = []
for name in ["../../evil_probe.txt", "/tmp/evil_abs.txt", "..\\..\\evil_win.txt", "正常名称.pdf"]:
    path = reg_sync.save_source_file(REG_ID, b"x", name)
    saved.append((name, path))

uploads_root = os.path.realpath(reg_sync.UPLOADS_DIR)
print("uploads 根:", uploads_root)
ok = True
for name, path in saved:
    real = os.path.realpath(path)
    inside = real.startswith(uploads_root + os.sep)
    ok = ok and inside
    print(f"  {name!r:28s} -> {os.path.relpath(real, os.path.dirname(uploads_root))}  inside={inside}")

leaked = [p for p in ("/app/uploads/evil_probe.txt", "/tmp/evil_abs.txt") if os.path.exists(p)]
print("越界文件残留:", leaked or "无")
print("结论：", "PASS" if ok and not leaked else "FAIL")

# 清理探针数据
shutil.rmtree(os.path.join(reg_sync.UPLOADS_DIR, REG_ID), ignore_errors=True)
print("已清理探针目录:", os.path.join(reg_sync.UPLOADS_DIR, REG_ID))
