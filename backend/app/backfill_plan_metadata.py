"""一次性存量数据回填：预案编号 + 章节元数据。

背景：2026-08-08 上线预案生成增强时，迁移 SQL 只新增了列，
存量预案的 plan_number/version_number 为空、章节元数据为默认值，
导致导出 400 与「自动填充」按钮不出现。

本脚本：
1. 为 plan_number/version_number 为空的预案自动生成编号（与 create_plan 同规则）。
2. 按模板结构回填章节的 ai_generatable/auto_fill/auto_fill_source/data_dependencies。

运行：容器内 `python -m app.backfill_plan_metadata`（或本地 venv）。
"""

import asyncio
from datetime import datetime

from sqlalchemy import select, func

from app.database import async_session
from app.models.enterprise import PlanProject, PlanSection, PlanTemplate
from app.routers.plans import PLAN_TYPE_CODE, _generate_plan_number


def _walk(structure: list) -> dict:
    """把模板结构拍平成 {section_key: meta}。"""
    meta = {}
    for item in structure:
        meta[item["key"]] = {
            "ai_generatable": item.get("ai_generatable", True),
            "auto_fill": item.get("auto_fill", False),
            "auto_fill_source": item.get("auto_fill_source"),
            "data_dependencies": item.get("data_dependencies", []),
        }
        meta.update(_walk(item.get("subsections", [])))
    return meta


async def run() -> None:
    async with async_session() as db:
        plans = (await db.execute(select(PlanProject))).scalars().all()
        templates = {
            t.plan_type: t.structure
            for t in (await db.execute(select(PlanTemplate))).scalars().all()
        }

        # 1) 编号回填：先统计每企业+类型的全部预案数，再给空编号的按序分配
        counter = {}
        for p in plans:
            key = (p.enterprise_id, p.plan_type)
            counter[key] = counter.get(key, 0) + 1

        used = {}
        fixed_numbers = 0
        for p in plans:
            if not p.plan_number or not p.version_number:
                key = (p.enterprise_id, p.plan_type)
                used[key] = used.get(key, 0) + 1
                if not p.plan_number:
                    ent = p.enterprise  # relationship selectin 已加载
                    p.plan_number = _generate_plan_number(
                        ent.name if ent else "", p.plan_type, used[key]
                    )
                if not p.version_number:
                    now = datetime.now()
                    p.version_number = f"A-{now.year}-{now.month:02d}"
                fixed_numbers += 1

        # 2) 章节元数据回填：按模板
        fixed_sections = 0
        for p in plans:
            structure = templates.get(p.plan_type)
            if not structure:
                continue
            meta_map = _walk(structure)
            sections = (await db.execute(
                select(PlanSection).where(PlanSection.plan_project_id == p.id)
            )).scalars().all()
            for s in sections:
                meta = meta_map.get(s.section_key)
                if not meta:
                    continue
                if s.ai_generatable != meta["ai_generatable"]:
                    s.ai_generatable = meta["ai_generatable"]
                    fixed_sections += 1
                if s.auto_fill != meta["auto_fill"]:
                    s.auto_fill = meta["auto_fill"]
                    fixed_sections += 1
                if s.auto_fill_source != meta["auto_fill_source"]:
                    s.auto_fill_source = meta["auto_fill_source"]
                    fixed_sections += 1
                if s.data_dependencies != meta["data_dependencies"]:
                    s.data_dependencies = meta["data_dependencies"]
                    fixed_sections += 1

        await db.commit()
        print(f"回填完成：编号修正 {fixed_numbers} 条，章节元数据修正 {fixed_sections} 条")


if __name__ == "__main__":
    asyncio.run(run())
