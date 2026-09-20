from fastapi import APIRouter, Depends, HTTPException
import html as _html
from sqlalchemy import select
from app.database import get_db
from app.models.enterprise import PlanProject, PlanSection, Enterprise
from app.schemas.plan import SectionResponse, SectionUpdate
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user
from app.services.data_marks import stale_domains_for_sections

router = APIRouter(prefix="/plans", tags=["Sections"])


def _render_org_structure_html(org_structure: list) -> str:
    """应急组织分组 → HTML 表格（每组一张表）。用户数据一律转义，防存储型 XSS。

    职务列优先取应急角色名（如「总指挥」），无 role_name 时回落到公司职位；
    职责列优先取成员级职责（角色职责），为空时回落到组级职责。
    """
    parts = []
    for g in org_structure or []:
        members = [m for m in g.get("members", []) if m.get("name")]
        if not members:
            continue
        group_duties = _html.escape(str(g.get("responsibilities") or ""), quote=True)
        rows = "".join(
            f"<tr><td>{i+1}</td><td>{_html.escape(str(m.get('name','')), quote=True)}</td>"
            f"<td>{_html.escape(str(m.get('role_name') or m.get('position') or ''), quote=True)}</td>"
            f"<td>{_html.escape(str(m.get('phone','')), quote=True)}</td>"
            f"<td>{_html.escape(str(m.get('responsibilities') or ''), quote=True) or group_duties}</td></tr>"
            for i, m in enumerate(members)
        )
        group_name = _html.escape(str(g.get('group_name','')), quote=True)
        parts.append(
            f"<h4>{group_name}</h4>"
            f"<table><thead><tr><th>序号</th><th>姓名</th><th>职务</th>"
            f"<th>联系电话</th><th>职责</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    return "\n".join(parts)


@router.get("/{plan_id}/sections", response_model=ApiResponse[list[SectionResponse]])
async def list_sections(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    rows = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()
    # D-3：消费 data_dependencies，标出"依赖数据已变更、正文未更新"的章节
    stale_map = await stale_domains_for_sections(db, p.enterprise_id, rows)
    items = []
    for s in rows:
        item = SectionResponse.model_validate(s)
        item.stale_domains = stale_map.get(s.section_key, [])
        items.append(item)
    return ApiResponse(data=items)

@router.get("/{plan_id}/sections/{section_key}", response_model=ApiResponse[SectionResponse])
async def get_section(plan_id: str, section_key: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()
    if not s: raise HTTPException(404, "章节不存在")
    return ApiResponse(data=SectionResponse.model_validate(s))

@router.put("/{plan_id}/sections/{section_key}", response_model=ApiResponse[SectionResponse])
async def update_section(plan_id: str, section_key: str, data: SectionUpdate, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()
    if not s: raise HTTPException(404, "章节不存在")
    s.content = data.content; await db.commit(); await db.refresh(s)
    return ApiResponse(data=SectionResponse.model_validate(s))


@router.post("/{plan_id}/sections/{section_key}/autofill", response_model=ApiResponse[SectionResponse])
async def autofill_section(plan_id: str, section_key: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p:
        raise HTTPException(404, "预案不存在")
    s = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id, PlanSection.section_key == section_key))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "章节不存在")
    if not s.auto_fill:
        raise HTTPException(400, "该章节不支持自动填充")
    if s.auto_fill_source != "org_structure":
        raise HTTPException(400, "不支持的自动填充来源")

    from app.services.emergency_org_service import load_emergency_groups

    ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
    groups = await load_emergency_groups(db, p.enterprise_id) if ent else []
    html = _render_org_structure_html(groups)
    if not html:
        raise HTTPException(400, "请先维护应急组织")

    s.content = html
    s.ai_generated = False
    await db.commit()
    await db.refresh(s)
    return ApiResponse(data=SectionResponse.model_validate(s))
