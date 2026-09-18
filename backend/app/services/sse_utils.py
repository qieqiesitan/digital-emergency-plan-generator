"""
SSE（Server-Sent Events）辅助函数。

提供两种主流格式：
- sse_event():  序列化 JSON event，用于 sse-starlette 的 EventSourceResponse
- sse_line():   SSE 文本行格式，用于 FastAPI StreamingResponse(media_type='text/event-stream')

另提供 `SSE_HEADERS`：所有 SSE 响应都应带上，尤其是 `X-Accel-Buffering: no`
——nginx 默认 `proxy_buffering on`，会攒满缓冲才下发，导致前端"流式生成"看不到增量；
nginx 原生识别上游的该响应头（无需运维改配置即可生效），是配置兜底之外的第二道保险。
"""

import json
from typing import Mapping

# SSE 响应统一头：禁止缓存 + 禁止网关缓冲 + 保持长连接
SSE_HEADERS: Mapping[str, str] = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def sse_headers(**extra: str) -> dict[str, str]:
    """在统一 SSE 头上追加/覆盖额外响应头。"""
    return {**SSE_HEADERS, **extra}


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
