from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.enterprise import PlanProject, PlanSection, PlanVersion
from app.schemas.common import ApiResponse
from app.dependencies import get_current_user
from pydantic import BaseModel

class VersionCreate(BaseModel):
    description: str | None = None

class VersionResponse(BaseModel):
    id: str; version_number: int; created_by: str; description: str | None; created_at: str
    model_config = {"from_attributes": True}

class VersionDetail(VersionResponse):
    snapshot: dict

class SectionDiff(BaseModel):
    section_key: str; title: str; change_type: str; old_content: str | None; new_content: str | None

class VersionCompare(BaseModel):
    version_a: int; version_b: int; diffs: list[SectionDiff]

router = APIRouter(prefix="/plans", tags=["Versions"])


def _build_snapshot(plan, sections: list) -> dict:
    """构建含风格参数与 Mermaid 图表的完整快照。"""
    return {
        "title": plan.title,
        "style_preference": plan.style_preference,
        "advanced_prompt_overrides": plan.advanced_prompt_overrides,
        "sections": [
            {
                "section_key": s.section_key,
                "title": s.title,
                "content": s.content,
                "ai_generated": s.ai_generated,
                "mermaid_svgs": s.mermaid_svgs,
            }
            for s in sections
        ],
    }


def _apply_snapshot(plan, section_map: dict, snapshot: dict) -> None:
    """将快照恢复到 plan 与章节；旧快照缺字段时跳过对应项。"""
    if "style_preference" in snapshot:
        plan.style_preference = snapshot.get("style_preference")
    if "advanced_prompt_overrides" in snapshot:
        plan.advanced_prompt_overrides = snapshot.get("advanced_prompt_overrides")
    for s_data in snapshot.get("sections", []):
        s = section_map.get(s_data.get("section_key"))
        if not s:
            continue
        s.content = s_data.get("content")
        if "mermaid_svgs" in s_data:
            s.mermaid_svgs = s_data.get("mermaid_svgs")


@router.get("/{plan_id}/versions", response_model=ApiResponse[list[VersionResponse]])
async def list_versions(plan_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    rows = (await db.execute(select(PlanVersion).where(PlanVersion.plan_project_id == plan_id).order_by(PlanVersion.version_number.desc()))).scalars().all()
    return ApiResponse(data=[VersionResponse(id=r.id, version_number=r.version_number, created_by=r.created_by, description=r.description, created_at=r.created_at.isoformat() if r.created_at else "") for r in rows])

@router.get("/{plan_id}/versions/{version_id}", response_model=ApiResponse[VersionDetail])
async def get_version(plan_id: str, version_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    v = (await db.execute(select(PlanVersion).where(PlanVersion.id == version_id, PlanVersion.plan_project_id == plan_id))).scalar_one_or_none()
    if not v: raise HTTPException(404, "版本不存在")
    return ApiResponse(data=VersionDetail(id=v.id, version_number=v.version_number, created_by=v.created_by, description=v.description, created_at=v.created_at.isoformat() if v.created_at else "", snapshot=v.snapshot or {}))

@router.post("/{plan_id}/versions", response_model=ApiResponse[VersionResponse])
async def create_version(plan_id: str, data: VersionCreate, current_user=Depends(get_current_user), db=Depends(get_db)):
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order))).scalars().all()
    snapshot = _build_snapshot(p, sections)
    new_ver = p.current_version + 1
    v = PlanVersion(plan_project_id=plan_id, version_number=new_ver, created_by="manual", description=data.description, snapshot=snapshot)
    p.current_version = new_ver
    db.add(v); await db.commit(); await db.refresh(v)
    return ApiResponse(data=VersionResponse(id=v.id, version_number=v.version_number, created_by=v.created_by, description=v.description, created_at=v.created_at.isoformat() if v.created_at else ""))

@router.get("/{plan_id}/versions/compare", response_model=ApiResponse[VersionCompare])
async def compare_versions(plan_id: str, a: int = Query(...), b: int = Query(...), current_user=Depends(get_current_user), db=Depends(get_db)):
    va = (await db.execute(select(PlanVersion).where(PlanVersion.plan_project_id == plan_id, PlanVersion.version_number == a))).scalar_one_or_none()
    vb = (await db.execute(select(PlanVersion).where(PlanVersion.plan_project_id == plan_id, PlanVersion.version_number == b))).scalar_one_or_none()
    if not va or not vb: raise HTTPException(404, "版本不存在")
    sa = {s["section_key"]: s for s in (va.snapshot or {}).get("sections", [])}
    sb = {s["section_key"]: s for s in (vb.snapshot or {}).get("sections", [])}
    diffs = []
    for key in set(sa.keys()) | set(sb.keys()):
        old = sa.get(key); new = sb.get(key)
        old_c = old["content"] if old else None
        new_c = new["content"] if new else None
        title = new["title"] if new else (old["title"] if old else key)
        if not old and new: ct = "added"
        elif old and not new: ct = "removed"
        elif old_c != new_c: ct = "modified"
        else: ct = "unchanged"
        diffs.append(SectionDiff(section_key=key, title=title, change_type=ct, old_content=old_c, new_content=new_c))
    return ApiResponse(data=VersionCompare(version_a=a, version_b=b, diffs=diffs))

@router.post("/{plan_id}/versions/{version_id}/rollback")
async def rollback_version(plan_id: str, version_id: str, current_user=Depends(get_current_user), db=Depends(get_db)):
    v = (await db.execute(select(PlanVersion).where(PlanVersion.id == version_id, PlanVersion.plan_project_id == plan_id))).scalar_one_or_none()
    if not v: raise HTTPException(404, "版本不存在")
    p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id))).scalar_one_or_none()
    if not p: raise HTTPException(404, "预案不存在")
    section_map = {}
    for s_data in v.snapshot.get("sections", []):
        s = (await db.execute(select(PlanSection).where(
            PlanSection.plan_project_id == plan_id,
            PlanSection.section_key == s_data["section_key"],
        ))).scalar_one_or_none()
        if s:
            section_map[s.section_key] = s
    _apply_snapshot(p, section_map, v.snapshot or {})
    await db.commit()
    return {"code": 0, "message": "已回滚"}

