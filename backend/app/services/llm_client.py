"""
统一 LLM API 调用客户端。

所有 AI 厂商的调用通过此模块集中管理，避免 chat.py 和 generation.py 中
重复实现同一套逻辑。
"""

import json
import logging
from typing import AsyncGenerator

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from app.config import settings
from app.models.enterprise import AIConfig

logger = logging.getLogger(__name__)

# 厂商 → 默认 API Base URL 映射
API_BASE_MAP: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
}


def _get_api_base(provider: str, base_url: str | None) -> str:
    """获取 API base URL。自定义 base_url 优先，否则使用内置映射。"""
    if base_url:
        return base_url
    return API_BASE_MAP.get(provider, "")


def decrypt_api_key(hex_str: str) -> str:
    """解密加密的 API Key。"""
    try:
        key = settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b"\0")
        cipher = AES.new(key, AES.MODE_ECB)
        return unpad(cipher.decrypt(bytes.fromhex(hex_str)), 16).decode()
    except Exception:
        raise Exception("AI Key解密失败，请前往 设置→AI配置 重新输入API Key保存后重试")


async def llm_chat_completion(
    messages: list[dict],
    ai_config: AIConfig,
    stream: bool = False,
    timeout: int = 120,
) -> dict | AsyncGenerator[str, None]:
    """统一的 LLM Chat Completion 调用入口。

    Args:
        messages:   OpenAI-format 消息列表
        ai_config:  AI 配置（provider, model, temperature 等）
        stream:     是否流式输出
        timeout:    超时秒数（默认 120s）

    Returns:
        stream=False: 完整响应 dict (OpenAI format)
        stream=True:  AsyncGenerator，逐个 yield 文本 chunk

    Raises:
        Exception: AI 调用失败时
    """
    base = _get_api_base(ai_config.provider, ai_config.base_url)

    payload = {
        "model": ai_config.model_name,
        "messages": messages,
        "temperature": ai_config.temperature,
        "max_tokens": ai_config.max_tokens,
        "top_p": ai_config.top_p,
        "stream": stream,
    }

    if stream:
        # 流式路径：AsyncClient 在生成器内部创建和管理
        return _stream_response(base, payload, ai_config, timeout)

    # 非流式路径
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{base}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"},
        )
        if resp.status_code != 200:
            raise Exception(f"AI调用失败: {resp.status_code} {resp.text[:300]}")
        return resp.json()


async def _stream_response(
    base: str,
    payload: dict,
    ai_config: AIConfig,
    timeout: int = 120,
) -> AsyncGenerator[str, None]:
    """内部：流式响应处理。AsyncClient 在函数内部管理生命周期。"""
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{base}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {decrypt_api_key(ai_config.api_key_encrypted)}"},
        ) as resp:
            if resp.status_code != 200:
                err = await resp.aread()
                raise Exception(f"AI 调用失败: {resp.status_code} {err[:300]}")
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        pass


async def llm_collect_all(
    messages: list[dict],
    ai_config: AIConfig,
    timeout: int = 120,
) -> str:
    """便捷函数：非流式调用并直接返回文本内容。"""
    data = await llm_chat_completion(messages, ai_config, stream=False, timeout=timeout)
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
