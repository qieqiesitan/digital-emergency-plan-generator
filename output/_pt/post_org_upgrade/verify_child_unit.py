"""对照实验：成员挂「根单元」→ 消费方格式为空；挂「子单元」→ 是否正常？

结论用于判定 build_groups_for_consumers 跳过根单元（parent_id 为空）是设计还是缺陷。
"""
import io
import json
import sys
import zipfile

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
MEMBER = "对照实验测试员"
BODY = "<h3>总则</h3><p>对照实验。</p>"

with httpx.Client(timeout=180) as c:
    token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                               "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    h = {"Authorization": f"Bearer {token}"}

    r = c.post(f"{BASE}/enterprises/{ENT}/org/members", headers=h, json={"name": MEMBER, "role": "member"})
    mid = (r.json().get("data") or {}).get("id")
    print(f"① 建成员 HTTP {r.status_code}")

    # 根单元（无 parent）+ 子单元（挂成员）
    r = c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": [
        {"id": "root", "name": "应急指挥部", "roles": [
            {"id": "r0", "name": "总指挥", "member_ids": [mid]}]},          # 根上挂了人
        {"id": "child", "parent_id": "root", "name": "抢险救援组", "roles": [
            {"id": "r1", "name": "组长", "member_ids": [mid]}]},            # 子单元上也挂了同一个人
    ]})
    print(f"② 写「根+子」两级组织 HTTP {r.status_code}")

    r = c.get(f"{BASE}/enterprises/{ENT}/org-structure", headers=h)
    groups = r.json().get("data") or []
    names = [m.get("name") for g in groups for m in g.get("members", [])]
    print(f"③ 消费方格式：{len(groups)} 组，成员 {names}")
    print(f"   组名：{[g.get('group_name') for g in groups]}")

    c.put(f"{BASE}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": BODY})
    r = c.post(f"{BASE}/plans/{PLAN}/export/docx", headers=h, json={})
    if r.status_code == 200:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            joined = "\n".join(z.read(n).decode("utf-8", "ignore")
                               for n in z.namelist() if n.endswith(".xml"))
        print(f"④ docx 含成员名：{MEMBER in joined}；含子组名：{'抢险救援组' in joined}")
    else:
        print(f"④ 导出失败 HTTP {r.status_code} {r.text[:120]}")

    c.put(f"{BASE}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": ""})
    c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
    c.delete(f"{BASE}/enterprises/{ENT}/org/members/{mid}", headers=h)
    print("⑤ 已清理")
