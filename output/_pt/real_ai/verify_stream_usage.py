"""真实调用验证：流式调用的 token 用量现在能写进留痕。"""
import asyncio
import sys

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
from sqlalchemy import text  # noqa: E402
from app.services.ai_config_service import get_system_ai_config  # noqa: E402
from app.services.llm_client import llm_chat_completion  # noqa: E402


async def main() -> int:
    async with async_session() as db:
        cfg = await get_system_ai_config(db)
        gen = await llm_chat_completion(
            [{"role": "user", "content": "用一句话说明甲醇储罐区的主要风险。"}],
            cfg, stream=True, timeout=60,
            payload_overrides={"max_tokens": 200, "temperature": 0},
            module="stream_usage_check",
        )
        text_out = "".join([chunk async for chunk in gen])
        print(f"流式返回 {len(text_out)} 字：{text_out[:80]}...")

        await asyncio.sleep(1.5)  # 等留痕落库
        row = (await db.execute(text(
            "select total_tokens, prompt_tokens, completion_tokens, success, module "
            "from llm_call_logs where module='stream_usage_check' order by created_at desc limit 1"
        ))).fetchone()
        print(f"留痕：total={row[0]} prompt={row[1]} completion={row[2]} success={row[3]} module={row[4]}")
        ok = row[0] is not None and row[0] > 0
        print("✅ 流式用量已留痕" if ok else "❌ 仍是 NULL")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
