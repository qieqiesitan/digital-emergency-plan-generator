"""真实额度 ② 聊天助手端到端（含工具调用循环）：3 个问题，记录选了哪些工具与最终答复。"""
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
U, P = "qa_e2e_test@test.com", "test123456"
OUT = "/app/exports/_preview"

QUESTIONS = [
    "我名下有哪些企业？只列名称和行业。",
    "系统里有哪些隐患排查检查表模板？给我名称和类别。",
    "帮我查一下法规库里关于「危险化学品储存」的要求，列出条目编号和要点。",
]


def ask(client: httpx.Client, token: str, question: str) -> dict:
    t0 = time.perf_counter()
    events, text, conv_id = [], "", None
    with client.stream("POST", f"{BASE}/chat",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"message": question}) as resp:
        status = resp.status_code
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                obj = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            events.append(obj.get("type"))
            if obj.get("type") == "chunk":
                text += str(obj.get("content") or "")
            if obj.get("type") == "conv_id":
                conv_id = obj.get("content")
    return {"status": status, "text": text, "conv_id": conv_id,
            "events": events, "elapsed": round(time.perf_counter() - t0, 1)}


def main() -> int:
    with httpx.Client(timeout=httpx.Timeout(300.0, read=240.0)) as c:
        token = (c.post(f"{BASE}/auth/login", json={"email": U, "password": P}).json()
                 .get("data") or {}).get("access_token")
        results = []
        for q in QUESTIONS:
            r = ask(c, token, q)
            results.append({"q": q, **r})
            print(f"\n【问】{q}")
            print(f"HTTP {r['status']}  {r['elapsed']}s  事件={r['events']}")
            print(f"【答】{r['text'].strip()[:600]}")
        with open(os.path.join(OUT, "real-chat-result.json"), "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=1)
    ok = all(r["status"] == 200 and r["text"].strip() for r in results)
    print(f"\n汇总：{sum(1 for r in results if r['status'] == 200 and r['text'].strip())}/3 有正常答复")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
