"""全量生成逐章进度落库。

风险/资源调查报告的全量生成是长时间 SSE 流：若只在最后一章写库，
中途退出、断流或服务重启都会把已生成内容清空为 generating 空行。
本模块提供“每完成一章即保存 summary.chapters + content”的独立会话写入，
保证中断后可续看/续生成，而不是整份作废。
"""

from typing import Any

from app.database import async_session


async def save_generation_progress(
    model: type,
    report_id: str,
    chapters: list[dict[str, Any]],
    content: str | None = None,
    status: str | None = None,
    session_factory=None,
) -> bool:
    """把已完成章节与当前拼接正文写入报告行。

    session_factory 仅测试注入用；默认使用应用级 async_session。
    返回是否找到报告行并写入。
    """
    factory = session_factory or async_session
    db = factory()
    try:
        row = await db.get(model, report_id)
        if row is None:
            return False
        summary = dict(row.summary or {})
        summary["chapters"] = chapters
        row.summary = summary
        if content is not None:
            row.content = content
        if status is not None:
            row.status = status
        await db.commit()
        return True
    finally:
        await db.close()
