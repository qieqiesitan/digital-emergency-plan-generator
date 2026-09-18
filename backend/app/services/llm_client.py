"""
统一 LLM API 调用客户端。

所有 AI 厂商的调用通过此模块集中管理，避免 chat.py 和 generation.py 中
重复实现同一套逻辑。
"""

import asyncio
import copy
import json
import logging
import random
import time
from typing import AsyncGenerator

import httpx
from fastapi import HTTPException

from app.models.enterprise import AIConfig
from app.services.ai_capability_service import is_capability_enabled
from app.services.secret_utils import decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

# 厂商 → 默认 API Base URL 映射
API_BASE_MAP: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
}

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
DEFAULT_MAX_RETRIES = 3

# 超时分类：优先按异常类型（LLMTimeoutError），文本特征仅作兼容兜底——
# httpx 的 ReadTimeout 消息可能为空串，纯文本判定会漏（2026-09-18 复测踩到）。
TIMEOUT_MARKERS = ("timed out", "timeout", "ReadTimeout", "ConnectTimeout", "PoolTimeout")

# 能力注册表进程内缓存：TTL 30s，避免每次调用都查库，同时让"停用"在 30s 内生效。
CAPABILITY_CACHE_TTL_SECONDS = 30.0
_CAPABILITY_CACHE: dict[str, tuple[float, object]] = {}


def is_timeout_error(exc: "LLMError") -> bool:
    """判断 LLMError(status_code=0) 是否源自超时。

    为什么要这个函数：`except httpx.TimeoutException` 在这个模块里是死代码——
    超时在更底层就被转成了 LLMError，永远走不到那个分支，
    结果超时和连接失败都被映射成 500 + "AI调用失败: 0"，用户看不出该重试还是该改配置。
    """
    if isinstance(exc, LLMTimeoutError):
        return True
    if exc.status_code != 0:
        return False
    text = str(exc).lower()
    return any(marker.lower() in text for marker in TIMEOUT_MARKERS)


class LLMError(Exception):
    """LLM 调用失败（非 200）。携带状态码与响应文本，供调用方按原文案重建。"""

    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        super().__init__(f"AI调用失败: {status_code} {text[:300]}")


class CapabilityDisabledError(LLMError):
    """AI 能力被管理员停用（W1：能力注册表真正接线）。"""

    def __init__(self, name: str):
        super().__init__(503, f"AI 能力「{name}」已被管理员停用，请联系管理员开启后重试")


class LLMTimeoutError(LLMError):
    """供应商请求超时（保留类型，供上层映射 504）。"""

    def __init__(self, detail: str = ""):
        super().__init__(0, detail or "AI 请求超时")


class LLMStreamTruncatedError(RuntimeError):
    """流式响应未正常结束（未收到 [DONE]）——结果不完整，调用方不得落库。

    为什么要单独一个异常类型：供应商中途断连时，`_stream_response` 原本直接 return，
    调用方把半截正文当完整结果落库，系统还标记成功。用户拿到半截报告却没有任何提示，
    这是最危险的一类错误——没人会去查一个"成功"的请求。
    """

    def __init__(self, received_chars: int = 0):
        super().__init__(f"LLM 流式响应中断：未收到结束标记，已收到 {received_chars} 字符")
        self.received_chars = received_chars


def _get_api_base(provider: str, base_url: str | None) -> str:
    """获取 API base URL。自定义 base_url 优先，否则使用内置映射。"""
    if base_url:
        return base_url
    return API_BASE_MAP.get(provider, "")


def decrypt_api_key(hex_str: str) -> str:
    """解密加密的 API Key。"""
    try:
        return decrypt_secret(hex_str)
    except Exception:
        # 保持 AI 场景原有 UX 文案；secret_utils 已改为通用解密失败提示。
        raise Exception("AI Key解密失败，请前往 设置→AI配置 重新输入API Key保存后重试")


encrypt_api_key = encrypt_secret


async def _load_capability(code: str):
    """读取能力注册表（30s 进程内缓存）；读取失败按"未注册"处理。"""
    now = time.monotonic()
    cached = _CAPABILITY_CACHE.get(code)
    if cached is not None and now - cached[0] < CAPABILITY_CACHE_TTL_SECONDS:
        return cached[1]
    capability = None
    try:
        from app.database import async_session
        from app.services.ai_capability_service import get_capability

        async with async_session() as session:
            capability = await get_capability(session, code)
    except Exception:  # noqa: BLE001 - 注册表不可用不应阻断调用
        logger.exception("读取 AI 能力注册表失败（按未注册处理）: %s", code)
    _CAPABILITY_CACHE[code] = (now, capability)
    return capability


def invalidate_capability_cache(code: str | None = None) -> None:
    """清进程内能力缓存：管理端刚改过开关时立即生效（其余 worker 由 30s TTL 兜底）。

    2026-09-19 审计：`PUT /platform/capabilities/{code}` 改完只写库，
    当前 worker 最长 30s 内仍按旧值放行/拦截 —— 补一个显式失效让"停用/启用"立刻可见。
    """
    if code is None:
        _CAPABILITY_CACHE.clear()
        return
    _CAPABILITY_CACHE.pop(code, None)


async def _emit_telemetry(record) -> None:
    """best-effort 写一条调用留痕；任何失败都不影响业务请求。"""
    try:
        from app.database import async_session
        from app.services.llm_telemetry import record_call

        async with async_session() as session:
            await record_call(session, record)
    except Exception:  # noqa: BLE001
        logger.exception("LLM 调用留痕失败（已忽略，不影响业务）")


async def _post_with_retry(base: str, payload: dict, headers: dict, timeout: int,
                           max_retries: int = DEFAULT_MAX_RETRIES, metrics: dict | None = None):
    """POST chat/completions，对 429/5xx/网络错误指数退避重试；401/400 不重试。"""
    for attempt in range(max_retries + 1):
        if metrics is not None:
            metrics["attempts"] = attempt + 1
        client = httpx.AsyncClient(timeout=timeout)
        try:
            resp = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            if attempt < max_retries:
                await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                continue
            if isinstance(e, httpx.TimeoutException):
                raise LLMTimeoutError(str(e))
            raise LLMError(0, str(e))
        finally:
            await client.aclose()
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in RETRYABLE_STATUS and attempt < max_retries:
            await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
            continue
        raise LLMError(resp.status_code, resp.text)
    raise LLMError(0, "LLM retry exhausted")


def _delta_texts(delta: dict) -> tuple[str, str]:
    """从 SSE delta 提取 (reasoning_content, content)。"""
    delta = delta or {}
    return delta.get("reasoning_content") or "", delta.get("content") or ""


async def llm_chat_completion(
    messages: list[dict],
    ai_config: AIConfig,
    stream: bool = False,
    timeout: int = 120,
    tools: list | None = None,
    payload_overrides: dict | None = None,
    include_top_p: bool = True,
    reasoning_cb=None,
    capability: str | None = None,
    module: str | None = None,
    user_id: str | None = None,
    enterprise_id: str | None = None,
) -> dict | AsyncGenerator[str, None]:
    """统一的 LLM Chat Completion 调用入口。

    Args:
        messages:   OpenAI-format 消息列表
        ai_config:  AI 配置（provider, model, temperature 等）
        stream:     是否流式输出
        timeout:    超时秒数（默认 120s）
        tools:      工具调用声明（非 None 时加入 payload）
        payload_overrides: 浅合并覆盖标准 payload（如 temperature/max_tokens）
        include_top_p: False 时不写入 top_p 键（sync/reranker 历史行为）
        capability: 能力注册表 code；被停用则直接拒绝，并应用 model_override（W1 接线）
        module:     留痕归属模块（默认取能力注册表的 module，否则 unclassified）

    Returns:
        stream=False: 完整响应 dict (OpenAI format)
        stream=True:  AsyncGenerator，逐个 yield 文本 chunk

    Raises:
        LLMError: 非 200 响应时（status_code + text）
    """
    capability_row = await _load_capability(capability) if capability else None
    if capability and capability_row is not None and not is_capability_enabled(capability_row):
        raise CapabilityDisabledError(getattr(capability_row, "name", None) or capability)
    if capability_row is not None and getattr(capability_row, "model_override", None):
        ai_config = copy.copy(ai_config)
        ai_config.model_name = capability_row.model_override

    base = _get_api_base(ai_config.provider, ai_config.base_url)

    payload = {
        "model": ai_config.model_name,
        "messages": messages,
        "temperature": ai_config.temperature,
        "max_tokens": ai_config.max_tokens,
        "stream": stream,
    }
    if include_top_p:
        payload["top_p"] = ai_config.top_p
    if tools is not None:
        payload["tools"] = tools
    retry_count = DEFAULT_MAX_RETRIES
    if payload_overrides:
        # B19：max_retries 是客户端重试参数，不得混入请求体（严格 API 400）。
        # 浅拷贝后取出，保证 payload 不含该键，其余 override 照常生效。
        overrides = dict(payload_overrides)
        retry_count = overrides.pop("max_retries", DEFAULT_MAX_RETRIES)
        payload.update(overrides)

    telemetry_module = module or getattr(capability_row, "module", None) or "unclassified"
    metrics: dict = {}
    started = time.perf_counter()

    def _record(success: bool, *, error_code=None, error_message=None,
                usage: dict | None = None, truncated: bool = False):
        from app.services.llm_telemetry import LlmCallRecord

        usage = usage or {}
        return LlmCallRecord(
            module=telemetry_module,
            capability=capability or "",
            model=payload.get("model"),
            prompt_version=getattr(capability_row, "prompt_ref", None),
            duration_ms=int((time.perf_counter() - started) * 1000),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            success=success,
            error_code=error_code,
            error_message=error_message,
            retry_count=max(0, metrics.get("attempts", 1) - 1),
            truncated=truncated,
            user_id=user_id,
            enterprise_id=enterprise_id,
        )

    if stream:
        # 流式路径：AsyncClient 在生成器内部创建和管理
        inner = _stream_response(base, payload, ai_config, timeout, max_retries=retry_count,
                                 reasoning_cb=reasoning_cb, metrics=metrics)
        return _telemetry_stream(inner, _record)

    # 非流式路径
    headers = {"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"}
    try:
        data = await _post_with_retry(base, payload, headers, timeout,
                                      max_retries=retry_count, metrics=metrics)
    except Exception as exc:  # noqa: BLE001 - 失败也要留痕后原样抛出
        await _emit_telemetry(_record(False, error_code=getattr(exc, "status_code", None),
                                      error_message=str(exc)))
        raise
    usage = data.get("usage") if isinstance(data, dict) else None
    await _emit_telemetry(_record(True, usage=usage))
    return data


async def _telemetry_stream(inner: AsyncGenerator[str, None], record_factory):
    """流式包装：正常结束/截断/失败各写一条留痕，并把原异常抛给调用方。"""
    try:
        async for piece in inner:
            yield piece
    except LLMStreamTruncatedError as exc:
        await _emit_telemetry(record_factory(False, error_message=str(exc), truncated=True))
        raise
    except Exception as exc:  # noqa: BLE001
        await _emit_telemetry(record_factory(False, error_code=getattr(exc, "status_code", None),
                                             error_message=str(exc)))
        raise
    else:
        await _emit_telemetry(record_factory(True))


async def _stream_response(
    base: str,
    payload: dict,
    ai_config: AIConfig,
    timeout: int = 120,
    max_retries: int = DEFAULT_MAX_RETRIES,
    reasoning_cb=None,
    metrics: dict | None = None,
) -> AsyncGenerator[str, None]:
    """内部：流式响应处理（建连/首响应前可重试，中途断流不重试）。"""
    headers = {"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"}
    received = 0
    for attempt in range(max_retries + 1):
        if metrics is not None:
            metrics["attempts"] = attempt + 1
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{base}/chat/completions",
                                         json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        err = await resp.aread()
                        if resp.status_code in RETRYABLE_STATUS and attempt < max_retries:
                            await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                            continue
                        raise LLMError(resp.status_code, err.decode("utf-8", errors="replace"))
                    finished = False
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                finished = True
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                reasoning, content = _delta_texts(delta)
                                if reasoning and reasoning_cb:
                                    try:
                                        reasoning_cb(reasoning)
                                    except Exception:
                                        logger.exception("reasoning_cb failed")
                                if content:
                                    received += len(content)
                                    yield content
                            except json.JSONDecodeError:
                                pass
                    if finished:
                        return
                    # 未收到 [DONE] 就结束：供应商中途断连。已产出的分片无法收回，
                    # 因此不重试（重试会导致内容重复），而是抛错让调用方决定如何处理。
                    raise LLMStreamTruncatedError(received)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            if attempt < max_retries:
                await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                continue
            if isinstance(e, httpx.TimeoutException):
                raise LLMTimeoutError(str(e))
            raise LLMError(0, str(e))
    raise LLMError(0, "LLM retry exhausted")


async def llm_collect_all(
    messages: list[dict],
    ai_config: AIConfig,
    timeout: int = 120,
    **kwargs,
) -> str:
    """便捷函数：非流式调用并直接返回文本内容。"""
    data = await llm_chat_completion(messages, ai_config, stream=False, timeout=timeout, **kwargs)
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def llm_stream_all(
    messages: list[dict],
    ai_config: AIConfig,
    timeout: int = 120,
    **kwargs,
) -> str:
    """流式调用并收集为完整文本。"""
    result = ""
    gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=timeout, **kwargs)
    async for chunk in gen:
        result += chunk
    return result


async def llm_text_completion(
    messages: list[dict],
    ai_config: AIConfig,
    timeout: int = 120,
    **kwargs,
) -> str:
    """非流式 LLM 调用并返回文本内容，错误统一映射为 HTTPException。

    此前各路由各自实现了 `_call_llm(_nonstream)`（解密 + base_url + payload +
    错误映射），此处收敛为单一实现：
    - 解密失败 → 500
    - 非 200 → 500（401 附带重新配置提示）
    - 超时 → 504
    - 其他连接失败 → 502
    """
    try:
        decrypt_api_key(ai_config.api_key_encrypted)  # 提前触发解密失败，映射为 500
    except Exception:
        raise HTTPException(500, "AI 配置密钥解密失败")
    try:
        data = await llm_chat_completion(messages, ai_config, stream=False, timeout=timeout, **kwargs)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except HTTPException:
        raise
    except CapabilityDisabledError:
        # 保留类型：调用方（如隐患 AI 降级路径）据此给出"能力已停用"的明确提示
        raise
    except LLMError as e:
        if e.status_code == 401:
            raise HTTPException(500, "AI API Key 无效或已过期，请在系统设置中重新配置 AI 模型")
        if is_timeout_error(e):
            raise HTTPException(504, f"AI 响应超时（{timeout}s），请稍后重试") from e
        if e.status_code == 0:
            raise HTTPException(502, f"AI 服务连接失败: {e}") from e
        raise HTTPException(500, "AI 服务调用失败，请稍后重试") from e
    except Exception as e:
        raise HTTPException(502, f"AI 服务连接失败: {e}")

