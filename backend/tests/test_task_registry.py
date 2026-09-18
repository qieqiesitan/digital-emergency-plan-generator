"""后台任务注册表：强引用 + 完成即摘除 + 异常落日志（2026-09-18 审计修复）。"""

import asyncio
import logging

from app.services.task_registry import active_task_count, spawn


def test_spawn_keeps_reference_then_discards_on_completion():
    async def run():
        done = asyncio.Event()

        async def work():
            await asyncio.sleep(0.01)
            done.set()

        task = spawn(work(), name="unit-test-ok")
        assert active_task_count() == 1, "任务执行期间必须被强引用持有"
        await task
        assert done.is_set()
        assert active_task_count() == 0, "任务完成后必须从注册表摘除（避免累积泄漏）"

    asyncio.run(run())


def test_spawn_logs_exception_and_discards(caplog):
    async def run():
        async def boom():
            raise RuntimeError("boom")

        task = spawn(boom(), name="unit-test-boom")
        # 注册表里的 done-callback 会取回异常并记日志；这里再 await 一次确认异常不丢
        try:
            await task
        except RuntimeError:
            pass
        assert active_task_count() == 0

    with caplog.at_level(logging.ERROR):
        asyncio.run(run())
    assert any("后台任务失败" in record.message for record in caplog.records), caplog.text
