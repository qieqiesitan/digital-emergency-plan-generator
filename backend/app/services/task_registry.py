"""后台 asyncio 任务注册表。

解决的问题（2026-09-18 审计）：

- asyncio 官方提醒：``create_task()`` 的返回值必须被保存，否则任务可能在执行途中被
  垃圾回收；``app/routers/external.py`` 的外部对接生成任务此前正是"创建即丢弃"。
- 任务异常若不取回，只会变成 "Task exception was never retrieved" 噪音，
  不进日志、不告警。
- 用 dict 长期持有已完成任务（generation / plan_generation_service / workflow.runner
  三处 ``_background_tasks``）会随次数累积，属内存泄漏，且这些 dict 从未被读取。

统一入口：``spawn(coro, name=...)`` —— 强引用、完成后自动摘除、异常写 error 日志。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

_tasks: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task[Any]:
    """启动后台任务并登记强引用；完成后自动摘除，异常写 error 日志。"""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)

    def _cleanup(finished: asyncio.Task[Any]) -> None:
        _tasks.discard(finished)
        if finished.cancelled():
            return
        exc = finished.exception()
        if exc is not None:
            logger.error(
                "后台任务失败（%s）: %s", name or finished.get_name(), exc, exc_info=exc
            )

    task.add_done_callback(_cleanup)
    return task


def active_task_count() -> int:
    """当前登记中的后台任务数（供测试与运维观测）。"""
    return len(_tasks)
