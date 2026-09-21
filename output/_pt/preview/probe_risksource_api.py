"""核实：旧「风险源」接口是否仍然可用（决定那 2 个 UI 文件是"坏代码"还是"没入口"）。"""
import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"

with httpx.Client(timeout=30) as c:
    token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    h = {"Authorization": f"Bearer {token}"}
    for method, path in [
        ("GET", f"/enterprises/{ENT}/risk-sources?page_size=5"),
        ("GET", f"/enterprises/{ENT}/risk-sources/template"),
    ]:
        r = c.request(method, BASE + path, headers=h)
        body = r.text[:160].replace("\n", " ")
        print(f"{r.status_code} {method} {path}\n     {body}")
