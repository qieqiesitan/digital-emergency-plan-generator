"""LLM 调用留痕：best-effort 写入，绝不因留痕失败影响业务请求。

留痕是观测手段。把观测手段做成故障源是本末倒置——所以这里吞掉所有异常，
只记日志。宁可丢一条留痕，也不能让用户的生成请求因为写日志失败而报错。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_call_log import LlmCallLog

logger = logging.getLogger("llm_telemetry")

MAX_ERROR_MESSAGE = 2000


@dataclass
class LlmCallRecord:
    module: str
    capability: str
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    duration_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    success: bool = True
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    truncated: bool = False
    user_id: Optional[str] = None
    enterprise_id: Optional[str] = None


async def record_call(db: AsyncSession, record: LlmCallRecord) -> Optional[str]:
    """写一条留痕。任何异常都被吞掉并记日志——留痕失败不是业务失败。"""
    try:
        row = LlmCallLog(
            module=record.module,
            capability=record.capability,
            model=record.model,
            prompt_version=record.prompt_version,
            duration_ms=record.duration_ms,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            total_tokens=record.total_tokens,
            success=record.success,
            error_code=record.error_code,
            error_message=(record.error_message or "")[:MAX_ERROR_MESSAGE] or None,
            retry_count=record.retry_count,
            truncated=record.truncated,
            user_id=record.user_id,
            enterprise_id=record.enterprise_id,
        )
        db.add(row)
        await db.commit()
        return getattr(row, "id", None)
    except Exception:
        logger.exception("LLM 调用留痕写入失败（已忽略，不影响业务）")
        return None
