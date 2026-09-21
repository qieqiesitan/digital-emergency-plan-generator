"""任务 13 真机核验：章节自动填充 + 导出签署页用真实应急组织数据（临时脚本，不入库）。"""

import asyncio
from types import SimpleNamespace

from sqlalchemy import text

from app.database import async_session
from app.routers.export import _build_signers_from_org
from app.routers.sections import autofill_section
from app.services.emergency_org_service import load_emergency_groups

PLAN_ID = "9c123a28-88fd-43f1-9ce6-50c33b6e745d"


async def main() -> None:
    async with async_session() as db:
        row = (
            await db.execute(
                text(
                    "select p.enterprise_id, e.user_id from plan_projects p "
                    "join enterprises e on e.id = p.enterprise_id where p.id = :p"
                ),
                {"p": PLAN_ID},
            )
        ).first()
        eid, uid = str(row[0]), str(row[1])
        user = SimpleNamespace(id=uid)

        groups = await load_emergency_groups(db, eid)
        print("应急组织分组数:", len(groups))
        print("签署人:", _build_signers_from_org(groups))

        res = await autofill_section(PLAN_ID, "sec_2", current_user=user, db=db)
        html = res.data.content or ""
        rows = html.count("<tr><td>")
        print("autofill 章节长度:", len(html), "表格行数:", rows)
        print("含应急指挥部:", "应急指挥部" in html, "| 含刘昕野:", "刘昕野" in html)
        await db.rollback()

        left = list(
            (await db.execute(text("select id from plan_sections limit 1"))).scalars().all()
        )
        print("回滚后仍可查询:", bool(left))


asyncio.run(main())
