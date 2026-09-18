"""stream_bridge：生产者异常时消费者必须立刻报错，而不是永久挂起。

来源：2026-09-19 用 mock 供应商实测——章节生成中途失败时 SSE 只发 ping、
不发 error 也不结束，前端永久转圈，预案状态卡在 generating（要人工改库）。
"""
import asyncio
import pathlib
import re

import pytest

from app.services.stream_bridge import next_or_raise


@pytest.mark.asyncio
async def test_returns_item_then_raises_producer_error():
    """队列里已有的消息照常返回；生产者随后抛错时，下一次等待必须抛错而不是挂起。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def producer():
        queue.put_nowait(("chunk", "第一段"))
        await asyncio.sleep(0.05)
        raise RuntimeError("供应商 429")

    task = asyncio.create_task(producer())
    got = await asyncio.wait_for(next_or_raise(queue, task), timeout=1)
    assert got == ("chunk", "第一段")
    with pytest.raises(RuntimeError, match="429"):
        await asyncio.wait_for(next_or_raise(queue, task), timeout=1)


@pytest.mark.asyncio
async def test_producer_error_with_empty_queue_does_not_hang():
    """核心回归点：生产者什么都没产出就失败时，消费者必须立刻收到异常。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def producer():
        raise ValueError("boom")

    task = asyncio.create_task(producer())
    with pytest.raises(ValueError, match="boom"):
        # 1 秒内必须返回；修复前这里会等到超时（永久阻塞）
        await asyncio.wait_for(next_or_raise(queue, task), timeout=1)


@pytest.mark.asyncio
async def test_producer_done_without_sentinel_raises_loudly():
    """生产者正常结束却没留下消息 = 调用方漏了结束哨兵，要显式报错而不是静默挂起。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def producer():
        return "no-sentinel"

    task = asyncio.create_task(producer())
    with pytest.raises(RuntimeError, match="缺少结束哨兵"):
        await asyncio.wait_for(next_or_raise(queue, task), timeout=1)


@pytest.mark.asyncio
async def test_producer_finished_with_pending_sentinel_is_returned():
    """正常流程：生产者写完 end 就结束，消费者仍要能拿到 end。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def producer():
        queue.put_nowait(("end", "全文"))

    task = asyncio.create_task(producer())
    await asyncio.sleep(0.02)  # 让生产者先跑完，制造"生产者已结束、队列有货"的场景
    assert await asyncio.wait_for(next_or_raise(queue, task), timeout=1) == ("end", "全文")


@pytest.mark.asyncio
async def test_producer_cancelled_propagates_cancelled():
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(asyncio.sleep(10))
    task.cancel()
    await asyncio.sleep(0.02)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(next_or_raise(queue, task), timeout=1)


def test_generate_section_uses_bridge():
    """源码守护：章节生成端点不得再退回裸 `await events.get()` 的写法。"""
    path = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers" / "generation.py"
    src = path.read_text(encoding="utf-8")
    body = src.split("async def event_generator()", 1)[1]
    assert "next_or_raise(events, task)" in body, "章节生成必须用 next_or_raise 消费事件队列"
    assert not re.search(r"kind, payload = await events\.get\(\)", body), \
        "裸 await events.get() 会在生产者抛错时永久挂起"
