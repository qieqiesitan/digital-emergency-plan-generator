"""补验：组织架构图（mermaid）确实从应急组织分组生成（临时脚本，不入库）。"""

import asyncio

from sqlalchemy import text

from app.database import async_session
from app.routers.generation import _append_additional_diagram_prompt, _build_org_chart_mermaid
from app.services.emergency_org_service import load_emergency_groups


async def main() -> None:
    async with async_session() as db:
        eid = str(
            (
                await db.execute(
                    text(
                        "select id from enterprises where name = :n "
                        "and jsonb_array_length(org_structure) = 8"
                    ),
                    {"n": "西安宝岳空间科技有限公司"},
                )
            ).scalar()
        )
        groups = await load_emergency_groups(db, eid)
        mermaid = _build_org_chart_mermaid(groups)
        print("mermaid 行数:", len((mermaid or "").splitlines()))
        print("含应急指挥部:", "应急指挥部" in (mermaid or ""))
        print("含刘昕野-总指挥:", "刘昕野-总指挥" in (mermaid or ""))
        prompt = _append_additional_diagram_prompt(
            "正文", "comprehensive", "sec_3", {"org_structure": groups}
        )
        print("章节提示词注入应急组织:", "应急指挥部" in prompt, "| 长度:", len(prompt))


asyncio.run(main())
