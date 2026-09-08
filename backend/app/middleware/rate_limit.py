"""轻量内存滑动窗口限流（QA P1-7：登录/注册/忘记密码防刷）。

单 worker 进程内滑动窗口；多 worker 部署需换共享存储（Redis），
此处保持零依赖实现，生产 4 worker 上线前应评估升级。
"""

import asyncio
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status


class SlidingWindowRateLimiter:
    """滑动窗口计数器：key -> deque[timestamp]，过期条目惰性清理。"""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def hit(self, key: str, limit: int, window_seconds: float) -> bool:
        """记录一次访问；超过 limit 返回 False（应拒绝）。"""
        now = time.monotonic()
        async with self._lock:
            dq = self._hits[key]
            cutoff = now - window_seconds
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            # 惰性清理：防止 key 无限增长
            if len(self._hits) > 10_000:
                self._hits = defaultdict(deque)
        return True


_limiter = SlidingWindowRateLimiter()


async def rate_limit(
    request: Request,
    limit: int = 30,
    window_seconds: float = 900,
    scope: str = "auth",
) -> None:
    """FastAPI 依赖：按客户端 IP + 行为维度限流，超限返回 429。"""
    client_ip = request.client.host if request.client else "unknown"
    key = f"{scope}:{client_ip}"
    ok = await _limiter.hit(key, limit=limit, window_seconds=window_seconds)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
            headers={"Retry-After": str(int(window_seconds))},
        )


def rate_limited(limit: int = 30, window_seconds: float = 900, scope: str = "auth"):
    """便捷装饰工厂：可直接注入 Depends。"""

    async def _dep(request: Request) -> None:
        await rate_limit(request, limit=limit, window_seconds=window_seconds, scope=scope)

    return Depends(_dep)
