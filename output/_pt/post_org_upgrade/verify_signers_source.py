"""决定性检查（含成员任职）：导出 docx 的签署页是否真的读「应急组织」新数据源。

步骤：① 建测试成员 → ② 写应急组织单元 + 角色「总指挥」并把成员挂上去 →
     ③ 给 sec_1 填正文 → ④ 导出 docx 并在 XML 里搜成员名 → ⑤ 还原（清组织/正文、删成员）。
"""
import io
import sys
import zipfile

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
UNIT = "应急组织签署页测试单位"
MEMBER = "签署冒烟测试员"
BODY = "<h3>总则</h3><p>验证组织架构升级后的导出与签署页取数。</p>"


def main() -> int:
    with httpx.Client(timeout=180) as c:
        token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                    "password": "test123456"}).json()
                 .get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}
        ok = True
        member_id = None

        r = c.post(f"{BASE}/enterprises/{ENT}/org/members", headers=h,
                   json={"name": MEMBER, "role": "member", "position": "测试岗"})
        print(f"① 建测试成员：HTTP {r.status_code} {r.text[:100]}")
        if r.status_code == 201:
            member_id = (r.json().get("data") or {}).get("id")
        ok &= member_id is not None

        r = c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": [{
            "id": "u1", "name": UNIT, "roles": [
                {"id": "r1", "name": "总指挥", "member_ids": [member_id] if member_id else []},
            ],
        }]})
        print(f"② 写应急组织+角色+任职：HTTP {r.status_code} {r.text[:110]}")
        ok &= r.status_code == 200

        r = c.get(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h)
        data = r.json().get("data") or []
        members_back = [m.get("name") for u in data for role in u.get("roles", [])
                        for m in role.get("members", [])]
        print(f"③ 回读应急组织成员：{members_back}")
        ok &= MEMBER in members_back

        c.put(f"{BASE}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": BODY})
        r = c.post(f"{BASE}/plans/{PLAN}/export/docx", headers=h, json={})
        print(f"④ 导出 docx：HTTP {r.status_code} {len(r.content or b'')} 字节")
        if r.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                joined = "\n".join(z.read(n).decode("utf-8", "ignore")
                                   for n in z.namelist() if n.endswith(".xml"))
            print(f"   签署页含成员名「{MEMBER}」：{MEMBER in joined}")
            print(f"   签署页含单位名「{UNIT}」：{UNIT in joined}")
            ok &= MEMBER in joined
        else:
            print(f"   失败：{r.text[:160]}")
            ok = False

        # ⑤ 还原
        c.put(f"{BASE}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": ""})
        c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
        if member_id:
            r = c.delete(f"{BASE}/enterprises/{ENT}/org/members/{member_id}", headers=h)
            print(f"⑤ 还原：清正文/清组织/删成员 HTTP {r.status_code}")
            ok &= r.status_code == 200

        print("\n" + ("[OK] 签署页确实读「应急组织」新数据源" if ok else "[X] 该路径有问题"))
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
