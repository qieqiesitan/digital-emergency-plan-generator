"""看清导出的 400 到底在说什么（空预案？还是真的坏了？）。"""
import httpx

BASE = "http://127.0.0.1:8000/api/v1"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"

with httpx.Client(timeout=120) as c:
    token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    h = {"Authorization": f"Bearer {token}"}
    r = c.post(f"{BASE}/plans/{PLAN}/export/docx", headers=h, json={})
    print("docx:", r.status_code, r.text[:300])
    r2 = c.post(f"{BASE}/plans/{PLAN}/export/validate", headers=h, json={})
    print("validate:", r2.status_code, r2.text[:400])
