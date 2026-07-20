"""
SSE（Server-Sent Events）辅助函数。

提供两种主流格式：
- sse_event():  序列化 JSON event，用于 sse-starlette 的 EventSourceResponse
- sse_line():   SSE 文本行格式，用于 FastAPI StreamingResponse(media_type='text/event-stream')
"""

import json


def sse_event(event_type: str, **kwargs) -> str:
    """序列化 JSON event 字符串 — 用于 EventSourceResponse (sse-starlette)。

    输出格式：{"type": "progress", "message": "...", ...}

    使用示例：
        await event_queue.put(sse_event("progress", message="开始生成..."))
    """
    return json.dumps({"type": event_type, **kwargs}, ensure_ascii=False)


def sse_line(data: dict) -> str:
    """SSE 文本行格式 — 用于 StreamingResponse(media_type='text/event-stream')。

    输出格式：data: {"type": "chunk", "content": "..."}\n\n

    使用示例：
        yield sse_line({"type": "chunk", "content": "Hello"})
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
