"""限流（QA P1-7：登录/注册/忘记密码防刷）。

W2：改为 Postgres 固定窗口计数（app_runtime_state），跨 worker 生效——
原实现是进程内滑动窗口，4 worker 下阈值被放大 4 倍。
注意：按客户端 IP 计数；若前面有反向代理，需保证 uvicorn 信任并透传真实 IP
（见 deploy/gateway-nginx.conf.example 的部署检查项）。
"""

import time

from fastapi import Depends, HTTPException, Request, status

from app.services.runtime_state import incr_counter


async def rate_limit(
    request: Request,
    limit: int = 30,
    window_seconds: float = 900,
    scope: str = "auth",
) -> None:
    """FastAPI 依赖：按客户端 IP + 行为维度限流，超限返回 429。"""
    client_ip = request.client.host if request.client else "unknown"
    window_seconds = int(window_seconds)
    window_index = int(time.time() // window_seconds)
    key = f"rl:{scope}:{client_ip}:{window_index}"
    count = await incr_counter(key, ttl_seconds=window_seconds + 1)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": str(window_seconds)},
        )


def rate_limited(limit: int = 30, window_seconds: float = 900, scope: str = "auth"):
    """便捷装饰工厂：可直接注入 Depends。"""

    async def _dep(request: Request) -> None:
        await rate_limit(request, limit=limit, window_seconds=window_seconds, scope=scope)

    return Depends(_dep)
