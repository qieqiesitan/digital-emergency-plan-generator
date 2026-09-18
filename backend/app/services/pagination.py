"""分页参数夹紧：避免调用方传入超大 page_size 造成无界查询/响应。

用于非 Pydantic Query 约束的入口（内存图谱查询、聊天工具参数等）。
"""


def clamp_page_size(value, default: int = 20, maximum: int = 100) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(size, maximum))


def clamp_page(value, default: int = 1) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, page)
