"""核实法规检索的 recall/similarity_score 语义（零额度，直调工具层）。"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
from app.models.user import User  # noqa: E402
from sqlalchemy import select  # noqa: E402
from app.services.chat_dispatch import dispatch  # noqa: E402


async def main() -> int:
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.email == "qa_e2e_test@test.com"))).scalar_one()
        out = await dispatch(db, user, "search_regulation_articles",
                             {"query": "危险化学品储存的要求", "top_k": 5})
        if isinstance(out, str):      # dispatch 返回的是 JSON 文本
            out = json.loads(out)
        arts = (out or {}).get("articles") or []
        print(f"返回 {len(arts)} 条")
        for a in arts[:5]:
            print(f"   recall={a.get('recall'):8s} score={a.get('similarity_score')} "
                  f"{a.get('article_number')} | {a.get('regulation_full_name')[:24]}")
        nulls = sum(1 for a in arts if a.get("similarity_score") is None)
        marked = all(a.get("recall") in ("vector", "lexical") for a in arts)
        zero = sum(1 for a in arts if a.get("similarity_score") == 0.0)
        print(f"词面命中(score=null) {nulls} 条；标记齐全 {marked}；仍出现 0.0 的 {zero} 条")
        ok = marked and zero == 0
        print("✅ 语义已修正（不再报假的 0.0）" if ok else "❌ 仍有 0.0 或缺少 recall 标记")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
