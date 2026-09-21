"""B6 运行时验证：文件名安全化 + 导出链路仍可用。"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/app")

from app.config import settings  # noqa: E402
from app.services.filename_safety import safe_filename  # noqa: E402

API = "http://localhost:8000/api/v1"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
U, P = "qa_e2e_test@test.com", "test123456"

malicious = ["../../../../tmp/pwn", "..\\..\\tmp\\pwn2", "/etc/passwd", "正常企业名称"]
export_root = os.path.realpath(settings.EXPORT_DIR)
ok = True
for raw in malicious:
    safe = safe_filename(raw, fallback="企业")
    path = os.path.realpath(os.path.join(settings.EXPORT_DIR, f"{safe}_事故风险评估报告.docx"))
    inside = path.startswith(export_root + os.sep)
    ok = ok and inside and "/" not in safe and "\\" not in safe
    print(f"  {raw!r:26s} -> {safe!r:22s} inside={inside}")
print("文件名安全化结论：", "PASS" if ok else "FAIL")

# 导出链路回归：DOCX 导出仍能正常返回（文件名走 safe_filename）
req = urllib.request.Request(
    API + "/auth/login",
    method="POST",
    data=json.dumps({"email": U, "password": P}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=20) as resp:
    token = json.loads(resp.read())["data"]["access_token"]

def _auth(path, token, method="GET", data=None):
    req = urllib.request.Request(
        API + path,
        method=method,
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=60)


# 选一个"有章节内容"的预案，否则导出会被 W4 的空内容守卫合法拦截（400）
with _auth("/plans?page=1&page_size=20", token) as resp:
    plans = json.loads(resp.read())["data"]["items"]
candidates = [p for p in plans if (p.get("completed_sections") or 0) > 0]
target = candidates[0]["id"] if candidates else PLAN
print("导出目标预案:", target, "（有内容预案数：%d）" % len(candidates))

req = urllib.request.Request(
    f"{API}/plans/{target}/export/docx",
    method="POST",
    data=b"{}",
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
)
try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = resp.read()
        ctype = resp.headers.get("content-type", "")
        print(f"导出回归：status={resp.status} bytes={len(body)} content-type={ctype}")
        print(
            "导出结论：",
            "PASS" if resp.status == 200 and len(body) > 10_000 else "FAIL",
        )
except urllib.error.HTTPError as exc:
    print("导出结论： FAIL", exc.code, exc.read()[:200])
