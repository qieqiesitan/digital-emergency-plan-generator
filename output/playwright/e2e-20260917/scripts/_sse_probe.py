"""SSE 真实链路分块计时探针：直连后端 vs 经 8082 自托管前端代理。

用法（容器内）: python /app/exports/_sse_probe.py
"""

import json
import time

import httpx

USER = {"email": "qa_e2e_test@test.com", "password": "test123456"}
TARGETS = [
    ("direct-backend-8000", "http://emergency-plan-backend:8000"),
    ("shuzihuayuan-proxy-8082", "http://shuzihuayuan:8080"),
]
PROMPT = "请分 5 行输出数字 1 到 5，每行一个数字，不要多余解释"


def login(base):
    r = httpx.post(f"{base}/api/v1/auth/login", json=USER, timeout=20)
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def probe(base, name):
    token = login(base)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"message": PROMPT, "history": [], "conversation_id": None}
    events, t0 = [], time.time()
    status, stream_error = None, None
    try:
        with httpx.stream("POST", f"{base}/api/v1/chat", json=body, headers=headers,
                          timeout=httpx.Timeout(180.0, connect=15.0)) as resp:
            status = resp.status_code
            for line in resp.iter_lines():
                if not line.strip():
                    continue
                events.append({"t": round(time.time() - t0, 3), "line": line[:160]})
    except Exception as exc:  # noqa: BLE001 - 记录断流时刻已收到的数据
        stream_error = f"{type(exc).__name__}: {exc}"[:160]
        events.append({"t": round(time.time() - t0, 3), "line": f"<STREAM ERROR {stream_error}>"})
    total = round(time.time() - t0, 3)
    chunks = [e for e in events if '"type": "chunk"' in e["line"] or '"type":"chunk"' in e["line"]]
    first = events[0] if events else None
    first_chunk = chunks[0] if chunks else None
    gaps = [round(b["t"] - a["t"], 3) for a, b in zip(chunks, chunks[1:])]
    return {
        "name": name, "status": status, "total_seconds": total,
        "stream_error": stream_error,
        "event_lines": len(events), "chunk_events": len(chunks),
        "first_event_seconds": first["t"] if first else None,
        "first_chunk_seconds": first_chunk["t"] if first_chunk else None,
        "last_chunk_seconds": chunks[-1]["t"] if chunks else None,
        "chunk_span_seconds": round(chunks[-1]["t"] - chunks[0]["t"], 3) if len(chunks) > 1 else 0,
        "max_gap_seconds": max(gaps) if gaps else None,
        "progressive": bool(len(chunks) > 1 and (chunks[-1]["t"] - chunks[0]["t"]) > 0.3),
        "sample_lines": [e["line"] for e in events[:3]] + [e["line"] for e in events[-2:]],
    }


if __name__ == "__main__":
    out = []
    for name, base in TARGETS:
        try:
            out.append(probe(base, name))
        except Exception as exc:  # noqa: BLE001
            out.append({"name": name, "error": f"{type(exc).__name__}: {exc}"[:300]})
    print(json.dumps(out, ensure_ascii=False, indent=1))
