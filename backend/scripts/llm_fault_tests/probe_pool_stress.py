"""Phase C：并发压测——长时间 AI 调用会不会把数据库连接池占满？

做法：把系统 AI 配置指向"非流式但先睡 6s"的 mock，同时发起 N 个聊天请求
（每个请求在 LLM 推理期间都会持有请求级 DB 会话），并在压测期间每秒采样
`pg_stat_activity`，观察：
    - 后端进程实际持有的连接数 / idle in transaction 数
    - 是否出现连接池超时（请求 500）或明显排队
    - 同时打一个只读控制接口，看是否被拖慢（SSE/AI 是否阻塞其他请求）
"""
import asyncio
import json
import os
import statistics
import time

import asyncpg
import httpx

API = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
DSN = os.environ.get("PG_DSN", "postgresql://postgres:postgres@postgres:5432/emergency_plan")
U, P = "qa_e2e_test@test.com", "test123456"
N = int(os.environ.get("N", "24"))


async def login(client: httpx.AsyncClient) -> str:
    r = await client.post(f"{API}/auth/login", json={"email": U, "password": P}, timeout=30)
    r.raise_for_status()
    return (r.json().get("data") or {}).get("access_token")


async def one_chat(client: httpx.AsyncClient, token: str, idx: int) -> dict:
    """一个聊天请求：等 SSE 收完（或失败），返回状态与耗时。"""
    t0 = time.perf_counter()
    status, chunks = None, 0
    try:
        async with client.stream(
            "POST", f"{API}/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": f"压测消息 {idx}"},
            timeout=httpx.Timeout(120.0, read=60.0),
        ) as resp:
            status = resp.status_code
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    chunks += 1
    except Exception as e:  # noqa: BLE001
        return {"idx": idx, "status": status or 0, "elapsed": time.perf_counter() - t0,
                "error": f"{type(e).__name__}: {str(e)[:80]}"}
    return {"idx": idx, "status": status, "elapsed": time.perf_counter() - t0, "chunks": chunks}


async def probe_control(client: httpx.AsyncClient, token: str, stop: asyncio.Event,
                        out: list) -> None:
    """压测期间每 1.5s 打一次只读接口，记录是否变慢/报错。"""
    while not stop.is_set():
        t0 = time.perf_counter()
        try:
            r = await client.get(f"{API}/plans", headers={"Authorization": f"Bearer {token}"}, timeout=35)
            out.append({"status": r.status_code, "ms": round((time.perf_counter() - t0) * 1000)})
        except Exception as e:  # noqa: BLE001
            out.append({"status": 0, "ms": round((time.perf_counter() - t0) * 1000),
                        "error": f"{type(e).__name__}"})
        await asyncio.sleep(1.5)


async def sample_pg(conn: asyncpg.Connection, stop: asyncio.Event, out: list) -> None:
    """每秒采样一次连接状态。"""
    while not stop.is_set():
        try:
            rows = await conn.fetch(
                """
                SELECT state, count(*) AS n
                FROM pg_stat_activity
                WHERE datname = current_database() AND pid <> pg_backend_pid()
                  AND application_name <> 'asyncpg'
                GROUP BY state
                """
            )
            snap = {r["state"] or "unknown": r["n"] for r in rows}
            total = sum(snap.values())
            out.append({"total": total, "idle_in_tx": snap.get("idle in transaction", 0),
                        "active": snap.get("active", 0), "idle": snap.get("idle", 0)})
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(1.0)


async def main() -> None:
    async with httpx.AsyncClient() as client:
        token = await login(client)
        pg = await asyncpg.connect(DSN)
        stop = asyncio.Event()
        pg_samples, ctrl = [], []
        sampler = asyncio.create_task(sample_pg(pg, stop, pg_samples))
        controller = asyncio.create_task(probe_control(client, token, stop, ctrl))
        await asyncio.sleep(1)

        t0 = time.perf_counter()
        results = await asyncio.gather(*[one_chat(client, token, i) for i in range(N)])
        wall = time.perf_counter() - t0

        stop.set()
        await asyncio.gather(sampler, controller, return_exceptions=True)
        await pg.close()

    ok = [r for r in results if r["status"] == 200]
    bad = [r for r in results if r["status"] != 200]
    lat = sorted(r["elapsed"] for r in ok)
    max_conn = max((s["total"] for s in pg_samples), default=0)
    max_tx = max((s["idle_in_tx"] for s in pg_samples), default=0)
    ctrl_bad = [c for c in ctrl if c["status"] != 200]

    print(f"── 并发 {N} 个聊天请求（每次 LLM 推理 6s）")
    print(f"   总耗时 {wall:.1f}s；成功 {len(ok)}；失败 {len(bad)}")
    if lat:
        print(f"   成功请求耗时 p50={statistics.median(lat):.1f}s "
              f"p95={lat[int(len(lat) * 0.95) - 1]:.1f}s max={lat[-1]:.1f}s")
    if bad:
        print(f"   失败样例：{bad[:3]}")
    print(f"   压测期间 DB 连接峰值 {max_conn}（其中 idle in transaction 峰值 {max_tx}）")
    print(f"   控制接口探测 {len(ctrl)} 次：失败 {len(ctrl_bad)}；"
          f"耗时 p50={statistics.median([c['ms'] for c in ctrl]) if ctrl else 0:.0f}ms "
          f"max={max((c['ms'] for c in ctrl), default=0)}ms")
    if ctrl_bad:
        print(f"   控制接口失败样例：{ctrl_bad[:3]}")
    print(json.dumps({"n": N, "ok": len(ok), "bad": len(bad), "wall_s": round(wall, 1),
                      "max_conn": max_conn, "max_idle_in_tx": max_tx,
                      "ctrl_calls": len(ctrl), "ctrl_bad": len(ctrl_bad),
                      "ctrl_max_ms": max((c["ms"] for c in ctrl), default=0)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
