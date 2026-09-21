"""直接验证 PUT /plans/{id} 的 style_preference 是否落库（绕过 UI）。"""

import json
import urllib.error
import urllib.request

API = "http://localhost:8000/api/v1"


def call(path, method="GET", body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:200]


status, tok = call("/auth/login", "POST", {"email": "qa_e2e_test@test.com", "password": "test123456"})
print("login", status)
token = tok["data"]["access_token"]

status, plans = call("/plans?page=1&page_size=1", token=token)
plan = plans["data"]["items"][0]
pid = plan["id"]
print("plan", pid, "before:", plan.get("style_preference"))

status, resp = call(
    f"/plans/{pid}",
    "PUT",
    {
        "style_preference": {
            "formality": "practical",
            "detail_level": "balanced",
            "table_preference": "moderate",
            "diagram_preference": "mermaid",
            "mode": "panel",
        }
    },
    token,
)
print("PUT", status, str(resp)[:200])

status, one = call(f"/plans/{pid}", token=token)
print("GET after:", one["data"].get("style_preference"))
