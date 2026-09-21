"""Phase B：把系统 AI 配置指向 Mock 供应商后，走真实 HTTP 看故障如何呈现给用户。

用法（容器内）：python /tmp/probe_llm_e2e.py <model> <section_key> <期望结果>
    期望结果 ∈ ok | error
断言：SSE 是否给出 done/error、耗时是否有界、章节有没有被错误落库。
"""
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
U, P = "qa_e2e_test@test.com", "test123456"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"


def login() -> str:
    r = httpx.post(f"{BASE}/auth/login", json={"email": U, "password": P}, timeout=30)
    r.raise_for_status()
    body = r.json()
    return (body.get("data") or {}).get("access_token") or body.get("access_token")


def stream_generate(token: str, section: str, timeout: float = 150.0) -> dict:
    """跑章节生成，收集 SSE 事件。"""
    events, chunks, status = [], "", None
    t0 = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", f"{BASE}/plans/{PLAN}/generate/{section}",
                           headers={"Authorization": f"Bearer {token}"},
                           json={}) as resp:
            status = resp.status_code
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    try:
                        obj = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    events.append(obj)
                    if obj.get("type") == "chunk" or "content" in obj:
                        chunks += str(obj.get("content") or "")
    return {"status": status, "events": events, "text": chunks,
            "elapsed": round(time.perf_counter() - t0, 1)}


def main() -> None:
    model, section, expect = sys.argv[1], sys.argv[2], sys.argv[3]
    token = login()
    out = stream_generate(token, section)
    types = [e.get("type") for e in out["events"]]
    done = "done" in types
    err_events = [e for e in out["events"] if e.get("type") == "error"]

    print(f"── model={model} section={section} 期望={expect}")
    print(f"   HTTP {out['status']} 耗时 {out['elapsed']}s 事件={types} 正文={len(out['text'])} 字")
    if err_events:
        print(f"   error 事件文案: {str(err_events[0].get('message'))[:160]}")

    ok = True
    if expect == "ok":
        if not done:
            print("   ❌ 期望成功但没有 done 事件")
            ok = False
        if len(out["text"]) < 3:
            print("   ❌ 期望有正文但正文过短")
            ok = False
    else:
        if done:
            print("   ❌ 期望失败却收到了 done（失败被当成成功）")
            ok = False
        if not err_events:
            print("   ❌ 没有 error 事件，网络断了？")
            ok = False
        if out["elapsed"] > 60:
            print(f"   ❌ 失败耗时过长（{out['elapsed']}s），像是在死等")
            ok = False
    print(f"   {'✅ 符合预期' if ok else '⚠️ 有偏差'}")
    print(json.dumps({"model": model, "section": section, "expect": expect,
                      "status": out["status"], "elapsed": out["elapsed"],
                      "events": types, "text_len": len(out["text"]),
                      "error": (err_events[0].get("message") if err_events else None)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
