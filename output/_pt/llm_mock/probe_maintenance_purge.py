"""验证维护端点带上了四色图临时文件回收（N-34）。"""
import json

import httpx

BASE = "http://127.0.0.1:8000/api/v1"

with httpx.Client(timeout=120) as c:
    token = (c.post(f"{BASE}/auth/login",
                    json={"email": "qa_e2e_test@test.com", "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    r = c.post(f"{BASE}/admin/maintenance/run-scans", headers={"Authorization": f"Bearer {token}"})
    print("HTTP", r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False)[:400])
