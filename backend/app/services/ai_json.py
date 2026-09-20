"""「让模型返回 JSON」的共用入口。

为什么要有这个模块（2026-09-20 审计）：8 个 AI 端点在 4 个路由里各自把同一段样板抄了一遍——

    try:
        await release_request_connection(db)      # 长调用前归还数据库连接（N-32）
        raw = await llm_text_completion(...)
        raw = raw.strip(); 剥 ``` 围栏; data = json.loads(raw)
        ...映射成响应...
    except HTTPException: raise
    except json.JSONDecodeError: 500 "AI 返回格式异常，请稍后重试"
    except Exception:            500 "AI 调用失败，请稍后重试"

合计约 150 行重复，而且已经在悄悄漂移（有的用 `lines[1:]`、有的用 `raw[3:]` 剥围栏；
上一轮补"归还连接"要改 8 遍）。集中到一处后：行为一致、异常文案一致、
将来加超时/重试/用量统计只改一个地方。
"""
import json
import logging
from typing import Any, Iterable

from fastapi import HTTPException

from app.services.db_guard import release_request_connection
from app.services.llm_client import llm_text_completion

logger = logging.getLogger(__name__)


def strip_code_fence(raw: str) -> str:
    """剥掉模型习惯性包上的 ```json ... ``` 围栏（无围栏时原样返回）。"""
    text = (raw or "").strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if lines and lines[0].startswith("```"):
        text = "\n".join(lines[1:])
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    return text.strip()


def parse_ai_json(raw: str, *, error_message: str = "AI 返回格式异常，请稍后重试") -> Any:
    """剥离围栏后解析 JSON；失败抛可读 HTTPException（服务层解析器的统一实现）。"""
    try:
        return json.loads(strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        logger.warning("AI 返回非 JSON: %s", str(raw)[:200])
        raise HTTPException(500, error_message) from exc


async def ai_json_completion(
    messages: list[dict],
    ai_config,
    *,
    db=None,
    timeout: int = 60,
    module: str | None = None,
) -> Any:
    """调一次 LLM 并返回解析后的 JSON 对象（异常已映射为可读的 HTTPException）。

    Args:
        db: 给了就在调用前归还数据库连接（长耗时调用不该占着连接池，见 N-32）。
        module: 留痕归属模块名，便于按功能看用量。

    Raises:
        HTTPException: 401 之类的业务异常原样透出；JSON 解析失败 → 500「AI 返回格式异常」；
                       其余（网络/超时/模型异常）→ 500「AI 调用失败」。
    """
    try:
        if db is not None:
            await release_request_connection(db)
        raw = await llm_text_completion(messages, ai_config, timeout=timeout, module=module)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - 统一成可读文案，细节进日志
        logger.warning("AI 调用失败: %s", exc)
        raise HTTPException(500, "AI 调用失败，请稍后重试") from exc

    try:
        return json.loads(strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        logger.warning("AI 返回非 JSON: %s", str(raw)[:200])
        raise HTTPException(500, "AI 返回格式异常，请稍后重试") from exc


def parse_items(data: Any, key: str, model) -> list:
    """`data[key]` → `[model(**item)]`；形状不对时给可读 500（而不是裸 ValidationError）。

    原实现把映射放在同一段 try 里，因此 Pydantic 校验失败会落到「AI 调用失败」文案；
    这里保留"可读 500"的语义，但明确写成"格式异常"，便于排查到底是模型还是我们的问题。
    """
    items: Iterable = []
    if isinstance(data, dict):
        raw_items = data.get(key)
        if isinstance(raw_items, list):
            items = raw_items
    try:
        return [model(**item) for item in items if isinstance(item, dict)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("AI 返回的 %s 结构不合法: %s", key, exc)
        raise HTTPException(500, "AI 返回格式异常，请稍后重试") from exc
