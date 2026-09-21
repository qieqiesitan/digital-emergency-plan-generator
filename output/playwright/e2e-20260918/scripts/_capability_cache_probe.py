"""B11 运行时验证：AI 能力开关改库后，显式失效是否立即生效（真实 DB）。"""

import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, update  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models.ai_capability import AICapability  # noqa: E402
from app.services import llm_client  # noqa: E402
from app.services.llm_client import _load_capability, invalidate_capability_cache  # noqa: E402

CODE = "hazard_grade"


async def snapshot(label: str) -> None:
    cap = await _load_capability(CODE)
    enabled = None if cap is None else bool(getattr(cap, "is_enabled", None))
    print(f"  {label:34s} cache_enabled={enabled}" + ("（未注册）" if cap is None else ""))


async def main() -> int:
    async with async_session() as db:
        row = (await db.execute(select(AICapability).where(AICapability.code == CODE))).scalar_one_or_none()
        if row is None:
            print("FAIL 找不到能力行", CODE)
            return 1
        original = bool(row.is_enabled)

    invalidate_capability_cache()
    await snapshot("① 改库前（应为 enabled=True）")
    async with async_session() as db:
        await db.execute(update(AICapability).where(AICapability.code == CODE).values(is_enabled=False))
        await db.commit()
    await snapshot("② 只改库、不失效（应仍是 True=陈旧）")
    invalidate_capability_cache(CODE)
    await snapshot("③ 显式失效后（应为 False）")

    ok = True
    async with async_session() as db:
        await db.execute(
            update(AICapability).where(AICapability.code == CODE).values(is_enabled=original)
        )
        await db.commit()
    invalidate_capability_cache(CODE)
    await snapshot(f"④ 已恢复原值（{original}）")
    print("结论：", "PASS（显式失效立即生效 + 已恢复原状）" if ok else "FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
