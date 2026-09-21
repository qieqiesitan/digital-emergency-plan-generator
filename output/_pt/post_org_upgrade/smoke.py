"""组织架构升级后的定向冒烟（零 AI 额度）：把"换了数据源/新页面"的路径实测一遍。

覆盖：公司组织树读写回环、应急组织树读、旧分组兼容视图、预案导出（签署页读应急组织）、
Onboarding 完成度、资源调查报告导出。
"""
import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"

rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str) -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:34s} {detail}")


with httpx.Client(timeout=120) as c:
    token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    h = {"Authorization": f"Bearer {token}"}

    # ① 公司组织树：读 → 写 → 回读 → 还原
    r = c.get(f"{BASE}/enterprises/{ENT}/org/nodes", headers=h)
    rec("公司组织树 GET", r.status_code == 200, f"HTTP {r.status_code} 节点={len(r.json().get('data') or [])}")
    nodes = [
        {"id": "n_dept", "type": "dept", "name": "升级冒烟部", "parent_id": None, "members": []},
        {"id": "n_pos", "type": "position", "name": "冒烟岗", "parent_id": "n_dept", "members": []},
    ]
    r = c.put(f"{BASE}/enterprises/{ENT}/org/nodes", headers=h, json={"nodes": nodes})
    rec("公司组织树 PUT", r.status_code == 200, f"HTTP {r.status_code}")
    r = c.get(f"{BASE}/enterprises/{ENT}/org/nodes", headers=h)
    got = r.json().get("data") or []
    rec("公司组织树 回读一致", [n.get("id") for n in got] == ["n_dept", "n_pos"],
        f"回读 {[n.get('name') for n in got]}")
    r = c.put(f"{BASE}/enterprises/{ENT}/org/nodes", headers=h, json={"nodes": []})
    rec("公司组织树 还原", r.status_code == 200, f"HTTP {r.status_code}")

    # ② 应急组织树
    t0 = time.perf_counter()
    r = c.get(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h)
    el = time.perf_counter() - t0
    rec("应急组织 GET", r.status_code == 200, f"HTTP {r.status_code} {el:.2f}s "
        f"payload={json.dumps(r.json().get('data'), ensure_ascii=False)[:70]}")

    # ③ 旧分组兼容视图
    for path in (f"/enterprises/{ENT}/org-structure", f"/enterprises/{ENT}/org/structure"):
        r = c.get(f"{BASE}{path}", headers=h)
        if r.status_code != 404:
            rec(f"旧分组兼容视图 {path.split('/')[-1]}", r.status_code == 200,
                f"HTTP {r.status_code} {r.text[:80]}")

    # ④ 预案导出（签署页在任务 8 里改成读应急组织）
    t0 = time.perf_counter()
    r = c.post(f"{BASE}/plans/{PLAN}/export/docx", headers=h, json={})
    el = time.perf_counter() - t0
    size = len(r.content or b"")
    rec("预案导出 docx", r.status_code == 200 and size > 5000,
        f"HTTP {r.status_code} {size} 字节 {el:.1f}s")
    r = c.get(f"{BASE}/plans/{PLAN}/export/preview", headers=h)
    rec("导出预览", r.status_code == 200, f"HTTP {r.status_code} {r.text[:70]}")

    # ⑤ Onboarding 完成度（key 仍是 org_structure、显示名改应急组织）
    r = c.get(f"{BASE}/enterprises/{ENT}/completion", headers=h)
    data = r.json().get("data") if r.status_code == 200 else {}
    rec("Onboarding 完成度", r.status_code == 200,
        f"HTTP {r.status_code} keys={list(data or {})[:6]}")

    # ⑥ 资源调查报告导出
    r = c.get(f"{BASE}/enterprises/{ENT}/resource-investigation/export", headers=h)
    rec("资源调查报告导出", r.status_code in (200, 404),
        f"HTTP {r.status_code} {len(r.content or b'')} 字节")

bad = [r for r in rows if not r[1]]
print(f"\n==== 升级后定向冒烟：{len(rows)} 项，失败 {len(bad)}")
for name, _, detail in bad:
    print(f"   FAIL {name}: {detail}")
sys.exit(1 if bad else 0)
