"""B4 运行时验证：上传体积守卫（413）+ SSRF 守卫（真实 DNS 解析）。"""

import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/app")  # 容器内以脚本方式运行时把应用根目录加入 import 路径

API = "http://localhost:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
U, P = "qa_e2e_test@test.com", "test123456"


def login():
    req = urllib.request.Request(
        API + "/auth/login",
        method="POST",
        data=json.dumps({"email": U, "password": P}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())["data"]["access_token"]


def multipart(path: str, token: str, filename: str, payload: bytes, field: str = "file"):
    boundary = "----B4Boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        API + path,
        method="POST",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()[:160]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()[:160]


token = login()
print("login ok")

# 1) 风险源 Excel 导入：21MB > 20MB 上限 → 期望 413
big = b"x" * (21 * 1024 * 1024)
code, body = multipart(f"/enterprises/{ENT}/risk-sources/import", token, "big.xlsx", big)
print(f"risk-sources/import 21MB -> {code} {body[:80]!r}")

# 2) 资源 Excel 导入：同上
code2, body2 = multipart(f"/enterprises/{ENT}/resources/import", token, "big.xlsx", big)
print(f"resources/import 21MB -> {code2} {body2[:80]!r}")

print(
    "上传守卫结论：",
    "PASS" if code == 413 and code2 == 413 else f"FAIL ({code}/{code2})",
)

# 3) SSRF 守卫（真实 DNS 解析）
from app.services.external_file_store import ExternalDownloadBlocked, assert_url_allowed  # noqa: E402

blocked = []
for url in ["http://127.0.0.1/x", "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd"]:
    try:
        assert_url_allowed(url)
        blocked.append(f"未拦截:{url}")
    except ExternalDownloadBlocked:
        pass
try:
    assert_url_allowed("https://www.baidu.com/robots.txt")
    public_ok = True
except ExternalDownloadBlocked as exc:  # noqa: BLE001
    public_ok = False
    blocked.append(f"误拦公网地址: {exc}")
print("SSRF 守卫结论：", "PASS" if not blocked and public_ok else f"FAIL {blocked}")
