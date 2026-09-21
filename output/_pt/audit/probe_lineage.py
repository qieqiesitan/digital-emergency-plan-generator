"""容器内探针（零 AI）：法规体系链端点 —— 上位法链与直接下级。"""
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:36s} {detail}", flush=True)


with httpx.Client(timeout=60) as c:
    token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                               "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    h = {"Authorization": f"Bearer {token}"}

    # 真实数据里：生产安全事故应急条例 --下位法--> 中华人民共和国安全生产法
    r = c.get(f"{BASE}/regulations/policy_emergency_regulation_2019/lineage", headers=h)
    rec("端点 200", r.status_code == 200, f"HTTP {r.status_code}")
    data = r.json().get("data") or {}
    up = data.get("up") or []
    print("   self =", json.dumps(data.get("self"), ensure_ascii=False)[:110])
    print("   up   =", json.dumps(up, ensure_ascii=False)[:200])
    print("   down =", json.dumps(data.get("down"), ensure_ascii=False)[:160])
    rec("上位法链含安全生产法", any(x["id"] == "law_safety_production_2021" for x in up),
        f"{len(up)} 级")
    rec("链里不含自身", all(x["id"] != "policy_emergency_regulation_2019" for x in up))
    rec("节点带展示字段", bool(up) and all({"title", "code", "status"} <= set(x) for x in up))

    # 安全生产法应有一批下级
    r2 = c.get(f"{BASE}/regulations/law_safety_production_2021/lineage", headers=h)
    down = (r2.json().get("data") or {}).get("down") or []
    rec("安全生产法有直接下级", len(down) > 0, f"{len(down)} 部")
    rec("下级不含自环", all(x["id"] != "law_safety_production_2021" for x in down))

    r3 = c.get(f"{BASE}/regulations/not_exist_xyz/lineage", headers=h)
    rec("不存在的法规 404", r3.status_code == 404, f"HTTP {r3.status_code}")

bad = [r for r in rows if not r[1]]
print(f"\n==== 法规体系链端点：{len(rows)} 项，失败 {len(bad)}")
sys.exit(1 if bad else 0)
