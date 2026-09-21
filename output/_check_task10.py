"""任务 10 真机核验：旧 /org-structure 的兼容读与下线写（临时脚本，不入库）。"""

import asyncio
from types import SimpleNamespace

from sqlalchemy import text

from app.database import async_session
from app.routers.enterprise_sub import get_org_structure, update_org_structure


async def main() -> None:
    async with async_session() as db:
        row = (
            await db.execute(
                text(
                    "select id, user_id from enterprises "
                    "where name = :n and jsonb_array_length(org_structure) = 8"
                ),
                {"n": "西安宝岳空间科技有限公司"},
            )
        ).first()
        eid, uid = str(row[0]), str(row[1])
        user = SimpleNamespace(id=uid)

        res = await get_org_structure(eid, current_user=user, db=db)
        groups = res.data
        print("compat groups:", [(g["group_key"], g["group_name"], len(g["members"])) for g in groups])
        print("总指挥:", [m["name"] for g in groups for m in g["members"] if m["role"] == "chief"])

        try:
            await update_org_structure(eid, current_user=user, db=db)
        except Exception as exc:  # noqa: BLE001 - 临时核验脚本
            print("PUT ->", getattr(exc, "status_code", "?"), str(getattr(exc, "detail", exc))[:70])


asyncio.run(main())
