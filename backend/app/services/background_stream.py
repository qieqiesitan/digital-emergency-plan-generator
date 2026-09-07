"""把异步生成器放到后台任务执行，SSE 消费端断开不取消生成。"""
import asyncio
from collections.abc import AsyncGenerator, Callable


class BackgroundStream:
    """生产端（报告逐章生成）在独立任务中运行，事件经队列转发给 SSE 消费端。

    消费端（浏览器 SSE）断开只会取消 events() 所在的消费任务；
    producer 任务继续运行并按自身逻辑逐章落库，最后自行收尾。
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self.task: asyncio.Task | None = None

    async def start(self, producer_factory: Callable[[], AsyncGenerator]):
        """启动 producer；producer_factory 每次调用返回新的异步生成器。"""
        self.task = asyncio.create_task(self._relay(producer_factory))

    async def _relay(self, producer_factory: Callable[[], AsyncGenerator]) -> None:
        try:
            async for event in producer_factory():
                await self._queue.put(event)
        finally:
            await self._queue.put(None)

    async def events(self) -> AsyncGenerator:
        """SSE 消费端逐条读取事件；生产者结束后返回。"""
        while True:
            event = await self._queue.get()
            if event is None:
                break
            yield event

    async def wait(self) -> None:
        """等待生产端任务结束（测试/收尾用）。"""
        if self.task:
            await self.task
