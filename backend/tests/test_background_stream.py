"""test_background_stream.py"""
import asyncio

import pytest

from app.services.background_stream import BackgroundStream


@pytest.mark.asyncio
async def test_relays_all_events():
    async def producer():
        for i in range(3):
            yield {"n": i}

    stream = BackgroundStream()
    await stream.start(producer)
    got = []
    async for event in stream.events():
        got.append(event)
    assert [e["n"] for e in got] == [0, 1, 2]
    await stream.wait()


@pytest.mark.asyncio
async def test_producer_continues_after_consumer_disconnect():
    release = asyncio.Event()
    produced = []

    async def producer():
        produced.append("first")
        yield {"n": 0}
        await release.wait()
        produced.append("second")
        yield {"n": 1}

    stream = BackgroundStream()
    await stream.start(producer)
    consumer = stream.events()
    assert (await anext(consumer))["n"] == 0
    # 模拟浏览器断开：消费端不再读取
    await consumer.aclose()
    release.set()
    await stream.wait()
    assert produced == ["first", "second"]
    # 断开后生产者仍把第二条事件放进队列
    assert stream._queue.qsize() >= 1
