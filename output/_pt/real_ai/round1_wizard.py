"""真实额度 ① 智能引导：POST /ai/setup-wizard（3 次模型调用）→ 检查三块建议质量。"""
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
ENT = "10e11995-e682-405a-9035-fbde13cca213"
U, P = "qa_e2e_test@test.com", "test123456"
OUT = "/app/exports/_preview"


def main() -> int:
    with httpx.Client(timeout=300) as c:
        token = (c.post(f"{BASE}/auth/login", json={"email": U, "password": P}).json()
                 .get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}
        t0 = time.perf_counter()
        r = c.post(f"{BASE}/enterprises/{ENT}/hazard-inspection/ai/setup-wizard",
                   headers=h,
                   json={"industry": "化工 / 危险化学品仓储经营",
                         "areas": "甲醇储罐区、汽车装卸区、危废暂存间",
                         "employee_count": "120",
                         "frequency_preference": "标准"})
        el = time.perf_counter() - t0
        print(f"HTTP {r.status_code}  耗时 {el:.1f}s")
        if r.status_code != 200:
            print(r.text[:400])
            return 1
        data = r.json().get("data") or {}
        with open(os.path.join(OUT, "real-wizard-result.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)

        print(f"available={data.get('available')}  note={data.get('note')!r}")
        org = data.get("org_suggestion") or {}
        nodes = org.get("nodes") or []
        print(f"\n【组织架构】available={org.get('available')} 节点数={len(nodes)}")
        for n in nodes[:12]:
            print(f"   - {n.get('type'):8s} {n.get('name')}  (parent={n.get('parent_id')})")

        plans = (data.get("plans_suggestion") or {}).get("plans") or []
        print(f"\n【排查计划】available={(data.get('plans_suggestion') or {}).get('available')} 计划数={len(plans)}")
        for p in plans:
            print(f"   - {p.get('name')} | {p.get('category')}/{p.get('frequency')} "
                  f"| 星期={p.get('weekdays')} | 责任人={p.get('responsible_user_name')} "
                  f"| 分区={p.get('zone_names')}")

        items = (data.get("checklist_suggestion") or {}).get("items") or []
        print(f"\n【检查表】available={(data.get('checklist_suggestion') or {}).get('available')} 条目数={len(items)}")
        for it in items[:15]:
            print(f"   - {it.get('content')}  ｜要求：{it.get('expected_note')}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
