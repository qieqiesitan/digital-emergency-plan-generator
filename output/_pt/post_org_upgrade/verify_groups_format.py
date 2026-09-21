"""用 HTTP 复现：/emergency-org 有成员，但消费方格式（旧分组/兼容视图）是否为空？"""
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
MEMBER = "分组格式测试员"
UNIT = "分组格式测试单位"

with httpx.Client(timeout=120) as c:
    token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                               "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    h = {"Authorization": f"Bearer {token}"}

    r = c.post(f"{BASE}/enterprises/{ENT}/org/members", headers=h,
               json={"name": MEMBER, "role": "member"})
    mid = (r.json().get("data") or {}).get("id")
    print(f"① 建成员 HTTP {r.status_code} id={mid}")

    r = c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": [{
        "id": "u1", "name": UNIT,
        "roles": [{"id": "r1", "name": "总指挥", "member_ids": [mid]}],
    }]})
    print(f"② 写应急组织 HTTP {r.status_code}")

    r = c.get(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h)
    tree = r.json().get("data") or []
    names = [m.get("name") for u in tree for role in u.get("roles", []) for m in role.get("members", [])]
    print(f"③ /emergency-org 成员：{names}")

    for path in (f"/enterprises/{ENT}/org-structure",):
        r = c.get(f"{BASE}{path}", headers=h)
        print(f"④ 消费方格式 {path}：HTTP {r.status_code} "
              f"{json.dumps(r.json().get('data'), ensure_ascii=False)[:220]}")

    # 清理
    c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
    if mid:
        r = c.delete(f"{BASE}/enterprises/{ENT}/org/members/{mid}", headers=h)
        print(f"⑤ 清理 HTTP {r.status_code}")

    ok = MEMBER in names
    print(f"\n结论：/emergency-org 读得到成员 = {ok}")
