"""并发压测探针（一次性诊断，不修改业务代码）。

用法（容器内，需 PYTHONPATH=/app）:
    python /app/exports/_concurrency_probe.py http     # 真实 API 60 并发（普通端点）
    python /app/exports/_concurrency_probe.py pool     # 模拟 4 worker × (10+20) 连接池上限
    python /app/exports/_concurrency_probe.py threads  # 8082 长连接线程模型（需宿主配合）
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time

import httpx

USER = {"email": "qa_e2e_test@test.com", "password": "test123456"}
DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/emergency_plan")


def login(base="http://emergency-plan-backend:8000"):
    r = httpx.post(f"{base}/api/v1/auth/login", json=USER, timeout=20)
    r.raise_for_status()
    return r.json()["data"]["access_token"]


# ───────────────────────── HTTP 并发 ─────────────────────────

async def http_load(n=60, base="http://emergency-plan-backend:8000", path="/api/v1/enterprises?page_size=100"):
    token = login(base)
    headers = {"Authorization": f"Bearer {token}"}
    lat, codes = [], []

    async with httpx.AsyncClient(timeout=60) as client:
        async def one(i):
            t0 = time.time()
            try:
                r = await client.get(base + path, headers=headers)
                codes.append(r.status_code)
            except Exception as exc:  # noqa: BLE001
                codes.append(f"{type(exc).__name__}: {str(exc)[:60]}")
            lat.append(time.time() - t0)

        t0 = time.time()
        await asyncio.gather(*[one(i) for i in range(n)])
        wall = time.time() - t0
    lat.sort()
    ok = sum(1 for c in codes if c == 200)
    return {
        "concurrency": n, "wall_seconds": round(wall, 2), "success": ok, "total": n,
        "p50_ms": round(lat[len(lat) // 2] * 1000), "p95_ms": round(lat[int(len(lat) * 0.95) - 1] * 1000),
        "max_ms": round(lat[-1] * 1000),
        "errors": [c for c in codes if c != 200][:5],
    }


# ─────────────────── 连接池上限（4 worker × 30） ───────────────────

def _pg_activity():
    try:
        out = subprocess.run(
            ["python", "-c",
             "import asyncio,asyncpg\n"
             "async def m():\n"
             "    c=await asyncpg.connect('postgresql://postgres:postgres@postgres:5432/emergency_plan')\n"
             "    n=await c.fetchval(\"select count(*) from pg_stat_activity where datname='emergency_plan'\")\n"
             "    print(n)\n"
             "    await c.close()\n"
             "asyncio.run(m())"],
            capture_output=True, text=True, timeout=15)
        return int(out.stdout.strip())
    except Exception:  # noqa: BLE001
        return None


def _worker_probe(idx, n_conn, hold_seconds, result_path):
    async def run():
        from sqlalchemy.ext.asyncio import create_async_engine
        # 与 app/database.py 完全一致的池参数
        engine = create_async_engine(DB_URL, pool_size=5, max_overflow=10, pool_recycle=1800,
                                     pool_pre_ping=True)
        ok, errs = 0, []
        lock = asyncio.Lock()

        async def one():
            nonlocal ok
            try:
                async with engine.connect() as conn:
                    from sqlalchemy import text
                    await conn.execute(text("select pg_sleep(:s)"), {"s": hold_seconds})
                async with lock:
                    ok += 1
            except Exception as exc:  # noqa: BLE001
                async with lock:
                    errs.append(f"{type(exc).__name__}: {str(exc)[:120]}")

        await asyncio.gather(*[one() for _ in range(n_conn)])
        await engine.dispose()
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump({"worker": idx, "ok": ok, "errors": errs[:3], "error_count": len(errs)}, fh)

    asyncio.run(run())


def pool_ceiling(workers=4, per_worker=15, hold=6.0):
    peak = {"n": 0}

    def monitor(stop):
        while not stop.is_set():
            n = _pg_activity()
            if n and n > peak["n"]:
                peak["n"] = n
            time.sleep(0.7)

    procs, paths = [], []
    stop = threading.Event()
    mon = threading.Thread(target=monitor, args=(stop,), daemon=True)
    mon.start()
    base_activity = _pg_activity()
    for i in range(workers):
        p = f"/tmp/pool_probe_{i}.json"
        paths.append(p)
        procs.append(subprocess.Popen(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0,'/app/exports');"
             "from _concurrency_probe import _worker_probe;"
             f"_worker_probe({i},{per_worker},{hold},{p!r})"]))
    t0 = time.time()
    for p in procs:
        p.wait(timeout=120)
    wall = round(time.time() - t0, 2)
    stop.set()
    time.sleep(0.8)
    res = {"workers": workers, "connections_per_worker": per_worker,
           "attempted_total": workers * per_worker, "wall_seconds": wall,
           "pg_activity_before": base_activity, "pg_activity_peak": peak["n"],
           "max_connections": 100, "results": []}
    for p in paths:
        try:
            res["results"].append(json.load(open(p, encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            res["results"].append({"error": str(exc)[:120]})
    res["total_ok"] = sum(r.get("ok", 0) for r in res["results"])
    res["total_errors"] = sum(r.get("error_count", 0) for r in res["results"])
    return res


# ─────────────────── 8082 长连接线程模型 ───────────────────

def _hold_connections(host, port, n, seconds, results):
    socks = []
    for _ in range(n):
        try:
            s = socket.create_connection((host, port), timeout=5)
            s.sendall(b"GET /api/v1/export/tasks/probe HTTP/1.0\r\nHost: x\r\n\r\n")
            socks.append(s)
        except Exception as exc:  # noqa: BLE001
            results.append(f"connect_fail: {type(exc).__name__}")
    time.sleep(seconds)
    for s in socks:
        try:
            s.close()
        except Exception:  # noqa: BLE001
            pass
    results.append(f"held={len(socks)}")


def threads_probe(n=60, hold=8):
    results = []
    th = threading.Thread(target=_hold_connections, args=("shuzihuayuan", 8080, n, hold, results),
                          daemon=True)
    th.start()
    time.sleep(2.5)
    # 长连接保持期间的静态页可用性
    avail = []
    for _ in range(5):
        t0 = time.time()
        try:
            r = httpx.get("http://shuzihuayuan:8080/", timeout=10)
            avail.append({"status": r.status_code, "ms": round((time.time() - t0) * 1000)})
        except Exception as exc:  # noqa: BLE001
            avail.append({"error": type(exc).__name__, "ms": round((time.time() - t0) * 1000)})
        time.sleep(0.3)
    th.join(timeout=60)
    return {"held_connections_target": n, "hold_seconds": hold, "result": results, "static_availability": avail}


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "http"
    if mode == "http":
        print(json.dumps(asyncio.run(http_load()), ensure_ascii=False, indent=1))
    elif mode == "pool":
        print(json.dumps(pool_ceiling(), ensure_ascii=False, indent=1))
    elif mode == "threads":
        print(json.dumps(threads_probe(), ensure_ascii=False, indent=1))
