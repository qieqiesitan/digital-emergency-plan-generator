"""真实额度 ④⑦：风险评估报告单章（SSE）+ 预案批量生成缩小版（3 章）。"""
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
U, P = "qa_e2e_test@test.com", "test123456"
OUT = "/app/exports/_preview"


def sse(client: httpx.Client, path: str, h: dict, body: dict, timeout: float = 900.0) -> dict:
    t0 = time.perf_counter()
    types: list[str] = []
    text, last_err = "", None
    with client.stream("POST", f"{BASE}{path}", headers=h, json=body,
                       timeout=httpx.Timeout(timeout, read=timeout)) as resp:
        status = resp.status_code
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                obj = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            t = obj.get("type")
            types.append(t)
            if t == "chunk":
                text += str(obj.get("content") or "")
            if t == "error":
                last_err = obj.get("message")
    return {"status": status, "elapsed": round(time.perf_counter() - t0, 1),
            "events": types, "text": text, "error": last_err}


def main() -> int:
    with httpx.Client(timeout=httpx.Timeout(900.0, read=900.0)) as c:
        token = (c.post(f"{BASE}/auth/login", json={"email": U, "password": P}).json()
                 .get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}

        # ④ 风险评估报告：第一章（4000-6000 字，最能压测长流式 + HTML 表格）
        r1 = sse(c, f"/enterprises/{ENT}/risk-assessment/generate/section", h,
                 {"chapter_key": "ch1_hazard_id"})
        print(f"\n【④ 风险评估报告·ch1_hazard_id】HTTP {r1['status']}  {r1['elapsed']}s  "
              f"事件数={len(r1['events'])} 正文={len(r1['text'])} 字 err={r1['error']}")
        print(f"   事件类型：{sorted(set(r1['events']))}")
        print(f"   正文开头：{r1['text'][:220].replace(chr(10), ' ')}")
        print(f"   正文结尾：{r1['text'][-160:].replace(chr(10), ' ')}")

        # ⑦ 批量生成缩小版：只跑前 3 章
        r2 = sse(c, f"/plans/{PLAN}/generate/batch", h,
                 {"keys": ["sec_1", "sec_1_1", "sec_1_2"]})
        print(f"\n【⑦ 批量生成 3 章】HTTP {r2['status']}  {r2['elapsed']}s  "
              f"事件数={len(r2['events'])} 正文={len(r2['text'])} 字 err={r2['error']}")
        kinds: dict[str, int] = {}
        for t in r2["events"]:
            kinds[t] = kinds.get(t, 0) + 1
        print(f"   事件统计：{kinds}")
        with open(os.path.join(OUT, "real-round4.json"), "w", encoding="utf-8") as fh:
            json.dump({"report_ch1": {k: v for k, v in r1.items() if k != "events"},
                       "batch3": {k: v for k, v in r2.items() if k != "events"}},
                      fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
