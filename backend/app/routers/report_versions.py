"""风险评估/资源调查报告的版本路由工厂：保存快照、列表、回滚、正文编辑保存。"""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.schemas.common import ApiResponse


class VersionCreate(BaseModel):
    description: str | None = None


class ReportContentUpdate(BaseModel):
    content: str


class ReportVersionItem(BaseModel):
    id: str
    version_number: int
    created_by: str
    description: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


def build_report_versions_router(report_type: str, report_model, version_model) -> APIRouter:
    """报告版本路由工厂：risk-assessment / resource-investigation 共用同一套逻辑。"""
    router = APIRouter(
        prefix=f"/enterprises/{{enterprise_id}}/{report_type}",
        tags=[f"{report_type} versions"],
    )

    async def _get_report(db: AsyncSession, enterprise_id: str, current_user_id: str):
        ent = (await db.execute(
            select(Enterprise).where(Enterprise.id == enterprise_id, Enterprise.user_id == current_user_id)
        )).scalar_one_or_none()
        if not ent:
            raise HTTPException(404, "企业不存在")
        report = (await db.execute(
            select(report_model).where(report_model.enterprise_id == enterprise_id)
        )).scalar_one_or_none()
        if not report:
            raise HTTPException(404, "报告不存在，请先生成报告")
        return report

    def _item(v) -> ReportVersionItem:
        return ReportVersionItem(
            id=v.id,
            version_number=v.version_number,
            created_by=v.created_by,
            description=getattr(v, "description", None),
            created_at=v.created_at.isoformat() if getattr(v, "created_at", None) else "",
        )

    @router.post("/versions", response_model=ApiResponse[ReportVersionItem])
    async def create_report_version(
        enterprise_id: str,
        body: VersionCreate | None = None,
        current_user=Depends(get_current_user),
        db=Depends(get_db),
    ):
        """保存当前报告为版本快照（content+summary），版本号 +1。"""
        report = await _get_report(db, enterprise_id, current_user.id)
        new_ver = (report.current_version or 1) + 1
        v = version_model(
            id=str(uuid4()),
            report_id=report.id,
            version_number=new_ver,
            content=report.content or "",
            summary=report.summary or {},
            created_by="manual",
        )
        report.current_version = new_ver
        db.add(v)
        await db.commit()
        await db.refresh(v)
        return ApiResponse(data=_item(v))

    @router.get("/versions", response_model=ApiResponse[list[ReportVersionItem]])
    async def list_report_versions(
        enterprise_id: str,
        current_user=Depends(get_current_user),
        db=Depends(get_db),
    ):
        report = await _get_report(db, enterprise_id, current_user.id)
        rows = (await db.execute(
            select(version_model)
            .where(version_model.report_id == report.id)
            .order_by(version_model.version_number.desc())
        )).scalars().all()
        return ApiResponse(data=[_item(v) for v in rows])

    @router.post("/versions/{version_id}/rollback")
    async def rollback_report_version(
        enterprise_id: str,
        version_id: str,
        current_user=Depends(get_current_user),
        db=Depends(get_db),
    ):
        """回滚到指定版本：恢复 content/summary 并同步当前版本号。"""
        report = await _get_report(db, enterprise_id, current_user.id)
        v = (await db.execute(select(version_model).where(
            version_model.id == version_id,
            version_model.report_id == report.id,
        ))).scalar_one_or_none()
        if not v:
            raise HTTPException(404, "版本不存在")
        report.content = v.content
        report.summary = v.summary or {}
        report.current_version = v.version_number
        await db.commit()
        return {
            "code": 0,
            "message": f"已回滚到 V{v.version_number}",
            "current_version": v.version_number,
        }

    @router.put("/content", response_model=ApiResponse[dict])
    async def save_report_content(
        enterprise_id: str,
        body: ReportContentUpdate,
        current_user=Depends(get_current_user),
        db=Depends(get_db),
    ):
        """保存编辑后的报告正文（Markdown）。"""
        report = await _get_report(db, enterprise_id, current_user.id)
        report.content = body.content
        await db.commit()
        return ApiResponse(data={"content_length": len(body.content)})

    return router
