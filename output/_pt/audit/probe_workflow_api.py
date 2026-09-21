"""容器内探针（零 AI）：预案页「生成并复核」的后端三端点。

**不点确认**——确认会真的触发 AI 生成（耗时 + 花额度）。门控语义用"确认错误的步骤名"间接验证。
"""
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:38s} {detail}", flush=True)


with httpx.Client(timeout=60) as c:
    token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                               "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    h = {"Authorization": f"Bearer {token}"}

    r = c.post(f"{BASE}/plans/{PLAN}/workflows/generate-review", headers=h, json={})
    data = r.json().get("data") or {}
    rec("启动工作流 200", r.status_code == 200, f"HTTP {r.status_code} {str(data)[:80]}")
    run_id = data.get("run_id")
    rec("返回两个步骤", [s.get("step_name") for s in data.get("steps", [])] == ["generate", "review"],
        str([s.get("step_name") for s in data.get("steps", [])]))

    time.sleep(1.5)
    r2 = c.get(f"{BASE}/workflows/{run_id}", headers=h)
    d2 = r2.json().get("data") or {}
    status = {s["step_name"]: s["status"] for s in d2.get("steps", [])}
    rec("停在生成门控（paused）", d2.get("status") == "paused" and d2.get("current_step") == "generate",
        f"status={d2.get('status')} current={d2.get('current_step')} steps={status}")

    # 门控语义：确认一个不在等待中的步骤应被拒绝（409），且不会触发任何生成
    r3 = c.post(f"{BASE}/workflows/{run_id}/confirm/review", headers=h, json={})
    rec("确认错误步骤 → 409", r3.status_code == 409, f"HTTP {r3.status_code} {r3.text[:70]}")

    # 归属校验：不存在的 run → 404
    r4 = c.get(f"{BASE}/workflows/00000000-0000-0000-0000-000000000000", headers=h)
    rec("未知 run → 404", r4.status_code == 404, f"HTTP {r4.status_code}")

    # 他人预案 → 404（用不存在的 plan id 模拟越权）
    r5 = c.post(f"{BASE}/plans/00000000-0000-0000-0000-000000000000/workflows/generate-review",
                headers=h, json={})
    rec("非本人预案 → 404", r5.status_code == 404, f"HTTP {r5.status_code}")

    print(f"\n待清理 run_id={run_id}")

bad = [r for r in rows if not r[1]]
print(f"==== 工作流三端点：{len(rows)} 项，失败 {len(bad)}")
sys.exit(1 if bad else 0)
