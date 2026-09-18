"""生产者任务 → 消费者队列 的桥接工具。

为什么需要它（2026-09-19 实测的真缺陷）：章节生成端点原本这样写——

    task = asyncio.create_task(_run_stream())     # 生产者：把事件丢进队列
    while True:
        kind, payload = await events.get()        # 消费者：等队列
        ...
        elif kind == "end":
            break
    await task                                    # 只有走到这里才会抛出生产者的异常

生产者一旦在 put("end") 之前抛错（LLM 限流/超时/流式中断），异常只落在 task 上，
队列里永远不会有下一条消息 → 消费者**永久阻塞**：SSE 只发心跳、不发 error、也不结束，
前端一直转圈，预案状态卡在 generating，直到人工改库。

`next_or_raise()` 把"等队列"和"看生产者"合成一次等待：谁先就绪就走谁，
生产者异常时立刻把异常抛给消费者，由上层决定怎么报错。
"""
import asyncio
from typing import Any


async def next_or_raise(queue: "asyncio.Queue[Any]", producer: "asyncio.Task[Any]") -> Any:
    """取队列里的下一条消息；生产者若异常/取消结束则抛出对应异常。

    Args:
        queue:    生产者写入消息的队列
        producer: 生产者任务

    Returns:
        队列里的一条消息。

    Raises:
        BaseException: 生产者抛出的原异常（或 CancelledError）。
        RuntimeError:   生产者正常结束但队列已空——说明缺少结束哨兵，属于调用方 bug，
                        这里显式报错而不是静默挂起。
    """
    getter: "asyncio.Task[Any]" = asyncio.ensure_future(queue.get())
    try:
        done, _pending = await asyncio.wait(
            {getter, producer}, return_when=asyncio.FIRST_COMPLETED
        )
    except asyncio.CancelledError:
        getter.cancel()
        raise

    if getter in done:
        return getter.result()

    # 生产者先结束：异常/取消/正常结束三种情况分别处理
    if producer.cancelled():
        getter.cancel()
        raise asyncio.CancelledError()
    exc = producer.exception()
    if exc is not None:
        getter.cancel()
        raise exc
    # 正常结束：结束哨兵一定已在队列里；队列若已空说明调用方漏了哨兵
    if queue.empty():
        getter.cancel()
        raise RuntimeError(
            "生产者已结束但事件队列为空：缺少结束哨兵，消费者会永久阻塞（调用方 bug）"
        )
    return await getter
