"""诊断：章节生成失败后，SSE 流到底有没有被服务端关闭？

逐行打印带时间戳的 SSE 事件，并在收到 done/error 后继续尝试读取 N 秒，
看服务端是否真的结束响应（而不是靠 ping 把连接一直吊着）。
"""
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
U, P = "qa_e2e_test@test.com", "test123456"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
SECTION = sys.argv[1] if len(sys.argv) > 1 else "sec_2"
WAIT_AFTER_TERMINAL = float(os.environ.get("WAIT_AFTER", "12"))


def main() -> None:
    r = httpx.post(f"{BASE}/auth/login", json={"email": U, "password": P}, timeout=30)
    token = (r.json().get("data") or {}).get("access_token")
    t0 = time.perf_counter()
    terminal_at = None
    ended_at = None
    types = []
    with httpx.Client(timeout=httpx.Timeout(60.0, read=30.0)) as client:
        with client.stream("POST", f"{BASE}/plans/{PLAN}/generate/{SECTION}",
                           headers={"Authorization": f"Bearer {token}"}, json={}) as resp:
            print(f"[{time.perf_counter()-t0:6.1f}s] HTTP {resp.status_code} "
                  f"encoding={resp.headers.get('transfer-encoding') or resp.headers.get('content-length')} "
                  f"conn={resp.headers.get('connection')}", flush=True)
            try:
                for line in resp.iter_lines():
                    el = time.perf_counter() - t0
                    if not line:
                        continue
                    if line.startswith("data:"):
                        try:
                            obj = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            obj = {"raw": line[:60]}
                        t = obj.get("type")
                        types.append(t)
                        print(f"[{el:6.1f}s] data type={t} {str(obj)[:110]}", flush=True)
                        if t in ("done", "error"):
                            terminal_at = el
                            if WAIT_AFTER_TERMINAL <= 0:
                                break
                    else:
                        print(f"[{el:6.1f}s] other: {line[:80]}", flush=True)
                    if terminal_at and el - terminal_at >= WAIT_AFTER_TERMINAL:
                        print(f"[{el:6.1f}s] 收到终止事件后已等 {WAIT_AFTER_TERMINAL}s，"
                              f"服务端仍未结束响应 → 由客户端主动断开", flush=True)
                        break
                else:
                    ended_at = time.perf_counter() - t0
            except Exception as e:  # noqa: BLE001
                print(f"[{time.perf_counter()-t0:6.1f}s] 读取异常 {type(e).__name__}: {e}", flush=True)

    print(f"\n终止事件于 {terminal_at}s；服务端关闭流于 "
          f"{ended_at if ended_at is not None else '未关闭（被动断开）'}；事件序列={types}")


if __name__ == "__main__":
    main()
