"""决定性检查：导出 docx 的签署页是否真的读「应急组织」新数据源（零 AI 额度）。

步骤：① 写一条应急组织单元 → ② 给 sec_1 填一章正文 → ③ 导出 docx →
     ④ 在 docx 的 XML 里搜这条单元名 → ⑤ 还原（清正文、清应急组织）。
"""
import io
import sys
import zipfile

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
MARK = "应急组织签署页测试单位"
BODY = "<h3>总则</h3><p>本预案用于验证组织架构升级后的导出与签署页取数。</p>"


def main() -> int:
    with httpx.Client(timeout=180) as c:
        token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                    "password": "test123456"}).json()
                 .get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}
        ok = True

        r = c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h,
                  json={"units": [{"id": "u1", "name": MARK, "roles": []}]})
        print(f"① 写应急组织：HTTP {r.status_code} {r.text[:90]}")
        ok &= r.status_code == 200

        r = c.put(f"{BASE}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": BODY})
        print(f"② 填章节正文：HTTP {r.status_code}")
        ok &= r.status_code == 200

        r = c.post(f"{BASE}/plans/{PLAN}/export/docx", headers=h, json={})
        print(f"③ 导出 docx：HTTP {r.status_code} {len(r.content or b'')} 字节")
        if r.status_code != 200:
            print(f"   失败原因：{r.text[:200]}")
            ok = False
        else:
            hit = False
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                for name in z.namelist():
                    if name.endswith(".xml") and MARK in z.read(name).decode("utf-8", "ignore"):
                        hit = True
                        break
            print(f"④ docx 里是否出现应急组织单元名「{MARK}」：{hit}")
            ok &= hit

        c.put(f"{BASE}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": ""})
        r = c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
        print(f"⑤ 还原：清正文 + 清应急组织 HTTP {r.status_code}")
        ok &= r.status_code == 200

        print("\n" + ("[OK] 签署页确实读新数据源（应急组织）" if ok else "[X] 该路径有问题，见上"))
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
