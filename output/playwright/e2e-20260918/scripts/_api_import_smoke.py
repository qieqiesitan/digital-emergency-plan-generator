"""后端运行时导入烟测：遍历 OpenAPI 里的 GET 接口并实际调用，确认批量清理未使用导入后无 500。

只做只读 GET；参数化接口用 QA 账号自己的企业/预案 id 代入。
"""

import json
import urllib.error
import urllib.request

API = "http://localhost:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
U, P = "qa_e2e_test@test.com", "test123456"


def call(path, token=None, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001
        return -1, f"{type(exc).__name__}: {exc}".encode()


status, tok = call("/auth/login", method="POST", body={"email": U, "password": P})
token = json.loads(tok)["data"]["access_token"]
print("login", status)

with urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=20) as resp:
    spec = json.loads(resp.read().decode())

# OpenAPI 里的 path 已含 /api/v1 前缀（call() 会再拼一次），这里先剥离
prefix = "/api/v1"
spec_paths = {p[len(prefix):] if p.startswith(prefix) else p: ops
              for p, ops in spec["paths"].items()}

# 1) 无参 GET 端点全量调用
no_param = [
    path for path, ops in spec_paths.items()
    if "get" in ops and "{" not in path
]
# 2) 参数化 GET：把已知 id 代入（企业 / 预案两类占位符）
param_paths = []
for path, ops in spec_paths.items():
    if "get" not in ops or "{" not in path:
        continue
    filled = (path.replace("{enterprise_id}", ENT).replace("{id}", ENT)
                  .replace("{plan_id}", PLAN).replace("{method_id}", "x")
                  .replace("{section_key}", "overview").replace("{object_id}", "x")
                  .replace("{ticket_id}", "x").replace("{regulation_id}", "x")
                  .replace("{version_id}", "x").replace("{user_id}", "x")
                  .replace("{node_id}", "x").replace("{zone_id}", "x")
                  .replace("{item_id}", "x").replace("{record_id}", "x")
                  .replace("{conversation_id}", "x").replace("{task_id}", "x"))
    if "{" not in filled:
        param_paths.append(filled)

targets = sorted(set(no_param + param_paths))
rows = []
for path in targets:
    code, body = call(path, token=token)
    rows.append({"path": path, "status": code, "body": body[:120].decode("utf-8", "replace")})

five = [r for r in rows if r["status"] >= 500 or r["status"] == -1]
ok = [r for r in rows if 200 <= r["status"] < 400]
auth = [r for r in rows if r["status"] in (401, 403, 404, 405, 422)]
print(f"\n接口总数 {len(rows)}：2xx/3xx {len(ok)}，401/403/404/405/422 {len(auth)}，5xx/异常 {len(five)}")
for r in five:
    print(f"  5XX {r['status']} {r['path']} :: {r['body'][:100]}")
with open("/app/exports/e2e-20260918/summary-b1-api-smoke.json", "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=1)
print("明细已写入 exports/e2e-20260918/summary-b1-api-smoke.json")
