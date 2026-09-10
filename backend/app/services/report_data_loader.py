"""报告生成共享数据加载器：危化品明细 + 组织成员。

风险评估/应急资源调查报告此前只手挑少量字段注入提示词，漏掉化学品理化
特性与组织成员（应急预案链路有完整注入）。此模块提供统一查询，供
risk_context_builder 与 resource_investigation_service 复用。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise_org import EnterpriseMember
from app.models.hazardous_chemicals import HazardousChemical


async def load_chemicals(enterprise_id: str, db: AsyncSession) -> list[dict]:
    """加载企业危化品 MSDS 级字段列表（应急预案与报告共用）。"""
    rows = (
        (
            await db.execute(
                select(HazardousChemical)
                .where(HazardousChemical.enterprise_id == enterprise_id)
                .order_by(HazardousChemical.name)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "name": c.name,
            "cas_no": c.cas_no,
            "un_no": c.un_no,
            "physical_state": c.physical_state,
            "flash_point": c.flash_point,
            "explosion_limit": c.explosion_limit,
            "ignition_temp": c.ignition_temp,
            "density": c.density,
            "boiling_point": c.boiling_point,
            "health_hazard": c.health_hazard,
            "fire_hazard": c.fire_hazard,
            "leak_response": c.leak_response,
            "storage_transport": c.storage_transport,
            "first_aid": c.first_aid,
            "protective_measures": c.protective_measures,
            "location": c.location,
            "max_storage": c.max_storage,
        }
        for c in rows
    ]


async def load_org_members(enterprise_id: str, db: AsyncSession) -> list[dict]:
    """加载启用中的企业组织成员（姓名/职务/电话/组织节点）。"""
    rows = (
        (
            await db.execute(
                select(EnterpriseMember)
                .where(
                    EnterpriseMember.enterprise_id == enterprise_id,
                    EnterpriseMember.enabled.is_(True),
                )
                .order_by(EnterpriseMember.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "name": m.name or "",
            "position": m.position or "",
            "role": m.role or "",
            "phone": m.phone or "",
            "org_node_id": m.org_node_id or "",
        }
        for m in rows
    ]
