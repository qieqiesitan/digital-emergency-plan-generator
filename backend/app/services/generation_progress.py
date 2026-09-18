"""预案生成运行时状态（跨 worker 共享，落 app_runtime_state）。

历史问题：这些状态原来存在模块级 dict（进程内存），而生产是 4 uvicorn worker——
防重失效导致同一预案并发生成两份、轮询进度落到别的 worker 返回空、
停止信号只有 1/4 概率命中真正在跑的 worker。

现在统一落 Postgres（见 app/services/runtime_state.py），带 TTL 自动过期：
- progress：当前阶段/章节/序号/思考摘要
- active / cancel：是否在生成、是否请求停止
- failed_sections：最近一次批量生成失败章节
"""

import asyncio
import logging
import time

from app.services.runtime_state import delete_state, get_state, set_state

logger = logging.getLogger(__name__)

PROGRESS_TTL_SECONDS = 3600
ACTIVE_TTL_SECONDS = 2 * 3600
FAILED_TTL_SECONDS = 2 * 3600


def _progress_key(plan_id: str) -> str:
    return f"plan_progress:{plan_id}"


def _active_key(plan_id: str) -> str:
    return f"plan_active:{plan_id}"


def _failed_key(plan_id: str) -> str:
    return f"plan_failed:{plan_id}"


# ── 进度 ──

_local_progress: dict[str, dict] = {}
_flush_tasks: dict[str, asyncio.Task] = {}
FLUSH_DEBOUNCE_SECONDS = 0.5


def set_progress(plan_id: str, **fields) -> None:
    """同步写入（供流式 reasoning/content 回调调用）+ 去抖落库。

    回调由同步代码触发（llm_client 的 reasoning_cb），不能 await；
    因此本地立即更新、异步去抖 0.5s 落 app_runtime_state，
    其他 worker 最多 0.5s 后能读到同一进度。
    """
    state = _local_progress.setdefault(plan_id, {})
    state.update(fields)
    state["updated_at"] = time.time()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = _flush_tasks.get(plan_id)
    if task and not task.done():
        return
    _flush_tasks[plan_id] = loop.create_task(_flush_progress(plan_id))


async def _flush_progress(plan_id: str) -> None:
    try:
        await asyncio.sleep(FLUSH_DEBOUNCE_SECONDS)
        snapshot = dict(_local_progress.get(plan_id) or {})
        if snapshot:
            await set_state(_progress_key(plan_id), snapshot, ttl_seconds=PROGRESS_TTL_SECONDS)
    except Exception:  # noqa: BLE001 - 进度落库失败不影响生成
        logger.exception("生成进度落库失败 plan=%s", plan_id)
    finally:
        _flush_tasks.pop(plan_id, None)


async def get_progress(plan_id: str) -> dict:
    """读进度：本地与共享存储取 updated_at 较新的一份。"""
    local = _local_progress.get(plan_id)
    shared = await get_state(_progress_key(plan_id)) or {}
    if local and local.get("updated_at", 0) >= shared.get("updated_at", 0):
        return dict(local)
    return shared


async def clear_progress(plan_id: str) -> None:
    _local_progress.pop(plan_id, None)
    await delete_state(_progress_key(plan_id))


# ── 生成中标记 / 停止信号 ──

async def set_active(plan_id: str, active: bool) -> None:
    key = _active_key(plan_id)
    state = await get_state(key) or {}
    state["active"] = active
    state.setdefault("cancel", False)
    if active:
        state["cancel"] = False
    await set_state(key, state, ttl_seconds=ACTIVE_TTL_SECONDS)


async def is_active(plan_id: str) -> bool:
    state = await get_state(_active_key(plan_id)) or {}
    return bool(state.get("active"))


async def request_cancel(plan_id: str) -> None:
    key = _active_key(plan_id)
    state = await get_state(key) or {}
    state["active"] = False
    state["cancel"] = True
    await set_state(key, state, ttl_seconds=ACTIVE_TTL_SECONDS)


async def is_cancel_requested(plan_id: str) -> bool:
    state = await get_state(_active_key(plan_id)) or {}
    return bool(state.get("cancel"))


# ── 失败章节 ──

async def set_failed_sections(plan_id: str, items) -> None:
    await set_state(_failed_key(plan_id), {"items": list(items or [])},
                    ttl_seconds=FAILED_TTL_SECONDS)


async def get_failed_sections(plan_id: str) -> list:
    state = await get_state(_failed_key(plan_id)) or {}
    return list(state.get("items") or [])
