"""
统一 LLM API 调用客户端。

所有 AI 厂商的调用通过此模块集中管理，避免 chat.py 和 generation.py 中
重复实现同一套逻辑。
"""

import asyncio
import json
import logging
import random
from typing import AsyncGenerator

import httpx
from fastapi import HTTPException

from app.models.enterprise import AIConfig
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


class LLMError(Exception):
    """LLM 调用失败（非 200）。携带状态码与响应文本，供调用方按原文案重建。"""

    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        super().__init__(f"AI调用失败: {status_code} {text[:300]}")


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


async def _post_with_retry(base: str, payload: dict, headers: dict, timeout: int,
                           max_retries: int = DEFAULT_MAX_RETRIES):
    """POST chat/completions，对 429/5xx/网络错误指数退避重试；401/400 不重试。"""
    for attempt in range(max_retries + 1):
        client = httpx.AsyncClient(timeout=timeout)
        try:
            resp = await client.post(f"{base}/chat/completions", json=payload, headers=headers)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            if attempt < max_retries:
                await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                continue
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

    Returns:
        stream=False: 完整响应 dict (OpenAI format)
        stream=True:  AsyncGenerator，逐个 yield 文本 chunk

    Raises:
        LLMError: 非 200 响应时（status_code + text）
    """
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

    if stream:
        # 流式路径：AsyncClient 在生成器内部创建和管理
        return _stream_response(base, payload, ai_config, timeout, reasoning_cb=reasoning_cb)

    # 非流式路径
    headers = {"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"}
    return await _post_with_retry(base, payload, headers, timeout, max_retries=retry_count)


async def _stream_response(
    base: str,
    payload: dict,
    ai_config: AIConfig,
    timeout: int = 120,
    max_retries: int = DEFAULT_MAX_RETRIES,
    reasoning_cb=None,
) -> AsyncGenerator[str, None]:
    """内部：流式响应处理（建连/首响应前可重试，中途断流不重试）。"""
    headers = {"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"}
    for attempt in range(max_retries + 1):
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
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                return
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
                                    yield content
                            except json.JSONDecodeError:
                                pass
                    return
        except (httpx.TransportError, httpx.TimeoutException) as e:
            if attempt < max_retries:
                await asyncio.sleep(min(8, 2 ** attempt) + random.uniform(0, 0.5))
                continue
            raise LLMError(0, str(e))
    raise LLMError(0, "LLM retry exhausted")


async def llm_collect_all(
    messages: list[dict],
    ai_config: AIConfig,
    timeout: int = 120,
) -> str:
    """便捷函数：非流式调用并直接返回文本内容。"""
    data = await llm_chat_completion(messages, ai_config, stream=False, timeout=timeout)
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def llm_stream_all(
    messages: list[dict],
    ai_config: AIConfig,
    timeout: int = 120,
) -> str:
    """流式调用并收集为完整文本。"""
    result = ""
    gen = await llm_chat_completion(messages, ai_config, stream=True, timeout=timeout)
    async for chunk in gen:
        result += chunk
    return result


async def llm_text_completion(
    messages: list[dict],
    ai_config: AIConfig,
    timeout: int = 120,
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
        data = await llm_chat_completion(messages, ai_config, stream=False, timeout=timeout)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except httpx.TimeoutException:
        raise HTTPException(504, f"AI 响应超时（{timeout}s），请稍后重试")
    except HTTPException:
        raise
    except LLMError as e:
        if e.status_code == 401:
            raise HTTPException(500, "AI API Key 无效或已过期，请在系统设置中重新配置 AI 模型")
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(502, f"AI 服务连接失败: {e}")

