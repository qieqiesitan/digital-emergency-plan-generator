"""D-2 存量修复：按台账重算企业档案的危化品文本（只改"有台账"的企业）。

台账为空的企业保留手填文本（未建台账时的 AI 引导兜底）。
运行方式：docker cp 到 backend 容器后 `python /tmp/_chemicals_backfill.py`。
"""
import asyncio

from sqlalchemy import func, select

import app.main  # noqa: F401  触发全部模型注册（独立脚本里 FK 解析需要 users 等表）
from app.database import async_session
from app.models.enterprise import Enterprise
from app.models.hazardous_chemicals import HazardousChemical
from app.services.chemical_summary import sync_enterprise_chemicals_summary


async def main():
    async with async_session() as db:
        rows = (await db.execute(
            select(
                Enterprise.id, Enterprise.name, Enterprise.hazardous_chemicals,
                select(func.count(HazardousChemical.id))
                .where(HazardousChemical.enterprise_id == Enterprise.id)
                .scalar_subquery().label("n"),
            ).order_by(Enterprise.name)
        )).all()
        changed = 0
        for ent_id, name, text, n in rows:
            if not n:
                continue
            before = (text or "").strip() or "(空)"
            after = await sync_enterprise_chemicals_summary(db, ent_id)
            if after:
                changed += 1
                print(f"[修复] {name} 台账 {n} 种\n  旧: {before[:70]}\n  新: {after[:110]}")
                await db.commit()   # 逐家提交：中途出错不影响已完成的企业
            else:
                print(f"[已是派生值] {name}（台账 {n} 种）: {before[:70]}")
        await db.commit()
        print(f"\n共修复 {changed} 家企业的档案危化品文本")


asyncio.run(main())
