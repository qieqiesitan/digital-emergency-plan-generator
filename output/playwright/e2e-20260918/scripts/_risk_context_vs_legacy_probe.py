"""只读探针：对比「旧 risk_sources 表」与「生成上下文 build_risk_management_context」。

目的：证明"系统里显示有风险源、但 AI 生成时读不到"这一互联互通缺陷。
不写任何数据。
"""
import asyncio

from sqlalchemy import func, select

from app.database import async_session
from app.models.enterprise import Enterprise, RiskSource
from app.services.risk_context_builder import build_risk_management_context


async def main():
    async with async_session() as db:
        rows = (await db.execute(
            select(
                Enterprise.id,
                Enterprise.name,
                select(func.count(RiskSource.id))
                .where(RiskSource.enterprise_id == Enterprise.id)
                .scalar_subquery()
                .label("legacy"),
            ).order_by(Enterprise.name)
        )).all()
        print(f"{'企业':<34} {'旧表行数':>8} {'生成上下文条数':>14} {'事故类型数':>10}")
        for ent_id, name, legacy in rows:
            if not legacy:
                continue
            ctx = await build_risk_management_context(ent_id, db)
            items = ctx.get("risk_sources") or []
            types = {i.get("accident_type") for i in items if i.get("accident_type")}
            flag = "  <<< 旧表有数据但生成读不到" if (legacy and not items) else ""
            print(f"{name[:32]:<34} {legacy:>8} {len(items):>14} {len(types):>10}{flag}")


asyncio.run(main())
