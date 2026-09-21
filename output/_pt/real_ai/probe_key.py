"""真实额度第 0 步：最小调用验证密钥/模型可用（成本 ≈ 30 token）。"""
import asyncio
import sys
import time

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
from app.services.ai_config_service import get_system_ai_config  # noqa: E402
from app.services.llm_client import llm_chat_completion  # noqa: E402


async def main() -> int:
    async with async_session() as db:
        cfg = await get_system_ai_config(db)
    if cfg is None:
        print("!! 没有系统 AI 配置")
        return 1
    print(f"配置：provider={cfg.provider} model={cfg.model_name} base={cfg.base_url} "
          f"temperature={cfg.temperature} max_tokens={cfg.max_tokens}")
    t0 = time.perf_counter()
    try:
        data = await llm_chat_completion(
            [{"role": "user", "content": "只回复两个字：可用"}],
            cfg, stream=False, timeout=30,
            payload_overrides={"max_tokens": 8, "temperature": 0},
            module="key_check",
        )
    except Exception as e:  # noqa: BLE001
        print(f"!! 调用失败：{type(e).__name__}: {str(e)[:200]}")
        return 1
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = data.get("usage") or {}
    print(f"OK 返回={text.strip()[:20]!r} 耗时={time.perf_counter() - t0:.1f}s "
          f"tokens={usage.get('total_tokens')}（prompt={usage.get('prompt_tokens')} "
          f"completion={usage.get('completion_tokens')}）")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
