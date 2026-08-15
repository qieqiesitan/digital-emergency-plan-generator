"""隐患公开端点（免登录，任务 5 §8 + 任务 10 §11.2）。

`POST /public/hazard/report/{token}` 扫码上报：
- token 匹配优先级：先查 `risk_objects.public_token`（风险点二维码，自动带
  object_id，enterprise 由风险点归属推导，location 可选）；再查
  `enterprises.hazard_report_token`（企业通用二维码，object_id 空、location
  必填——取舍：无风险点关联时 location 是唯一位置线索，强制必填以保证隐患
  可定位、管理员可处理；规格 §8 允许留空，此处按任务契约收紧为 422）。
- nonce 防重：进程内 dict + 时间戳，TTL 5 分钟（键 `hazard_report:{nonce}`），
  重复提交 409「请勿重复提交」；过期惰性清理。单进程假设（与规格 §13 调度器
  假设一致）。
- 落库 source_type=report、created_by=NULL、status=registered、code=HD-{三位序号}；
  响应不暴露内部信息（§8「已提交，待企业管理员确认」风格）。

`GET /public/hazard/{token}` 隐患公示公开页（任务 10）：
- token = `enterprises.hazard_public_token`，无效 → 404「链接已失效」（§16）；
- 只读、脱敏：企业名称（首字符 + **）、公示列表（编号/标题/等级/状态/整改
  情况摘要，复用 hazard_management 公示行构造，不含责任人/联系方式/照片/
  位置/内部备注）；响应含 generated_at 与 masked 标记；
- scope 口径（ongoing/closed/all，默认 all）与企业内公示一致，非法 422。
"""

from datetime import datetime, timezone
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.hazard_management import HazardRecord
from app.models.risk_management import RiskObject
from app.schemas.common import ApiResponse
from app.services.hazard_service import next_hazard_code
# 公示行/口径/整改摘要/名称脱敏等共享逻辑放在主隐患路由（hazard_management），
# 公开端点复用保证企业内与公开口径一致（§11.2「口径与企业内公示一致」）
from app.routers.hazard_management import (
    _dict_labels,
    _latest_rectifications,
    _mask_enterprise_name,
    _publicity_row,
    _rectification_summary,
    _resolve_publicity_scopes,
)


router = APIRouter(prefix="/public/hazard", tags=["Public Hazard"])

NONCE_TTL_SECONDS = 300  # nonce 防重窗口 5 分钟（§8 幂等）
# 进程内 nonce 缓存：键 `hazard_report:{nonce}` → 首次提交时间（time.monotonic）。
# 成功落库后写入；查询时惰性清理过期键，避免无限增长。
_nonce_cache: dict[str, float] = {}


def _purge_expired_nonces(now: float) -> None:
    expired = [key for key, ts in _nonce_cache.items() if now - ts >= NONCE_TTL_SECONDS]
    for key in expired:
        _nonce_cache.pop(key, None)


def _nonce_available(nonce: str) -> bool:
    """nonce 未被使用过（TTL 内）；过期键先惰性清理。"""
    _purge_expired_nonces(time.monotonic())
    return f"hazard_report:{nonce}" not in _nonce_cache


def _mark_nonce(nonce: str) -> None:
    """成功落库后写入 nonce 缓存（防重窗口起点）。"""
    now = time.monotonic()
    _purge_expired_nonces(now)
    _nonce_cache[f"hazard_report:{nonce}"] = now


class PublicHazardReport(BaseModel):
    """扫码上报请求：title 可选（缺省由描述截断），description/nonce 必填。"""

    title: Optional[str] = Field(None, max_length=255)
    description: str = Field(..., min_length=1)
    photo_urls: Optional[list[str]] = None
    location: Optional[str] = Field(None, max_length=500)
    nonce: str = Field(..., min_length=1)


@router.post("/report/{token}", response_model=ApiResponse[dict])
async def public_hazard_report(token: str, body: PublicHazardReport, db: AsyncSession = Depends(get_db)):
    """扫码上报：风险点 token 优先（自动带 object_id），其次企业通用 token。"""
    description = (body.description or "").strip()
    if not description:
        raise HTTPException(422, "description 不能为空")
    if not (body.nonce or "").strip():
        raise HTTPException(422, "nonce 不能为空")

    obj = (await db.execute(
        select(RiskObject).where(RiskObject.public_token == token)
    )).scalar_one_or_none()
    object_id: Optional[str] = None
    if obj:
        # 风险点 token：object_id 自动带，enterprise 由风险点归属推导
        object_id = obj.id
        ent = (await db.execute(
            select(Enterprise).where(Enterprise.id == obj.enterprise_id)
        )).scalar_one_or_none()
        if not ent:
            raise HTTPException(404, "链接已失效")
        location = (body.location or "").strip() or None  # 已关联风险点，location 可选
    else:
        # 企业通用 token：object_id 空，location 必填（见模块 docstring 取舍）
        ent = (await db.execute(
            select(Enterprise).where(Enterprise.hazard_report_token == token)
        )).scalar_one_or_none()
        if not ent:
            raise HTTPException(404, "链接已失效")
        location = (body.location or "").strip()
        if not location:
            raise HTTPException(422, "企业通用二维码上报时 location 必填")

    if not _nonce_available(body.nonce):
        raise HTTPException(409, "请勿重复提交")

    title = (body.title or "").strip()
    if not title:
        title = description[:255] or "扫码上报隐患"
    record = HazardRecord(
        enterprise_id=ent.id,
        code=await next_hazard_code(db, ent.id),
        source_type="report",
        object_id=object_id,
        title=title[:255],
        description=description,
        photo_urls=list(body.photo_urls or []),
        location=location[:500] if location else None,
        # created_by 留空 → NULL（扫码上报匿名，规格 §5.4/§8）
    )
    db.add(record)
    await db.commit()
    # 成功落库后再标记 nonce，避免失败提交误占防重窗口
    _mark_nonce(body.nonce)
    return ApiResponse(data={"message": "已提交，待企业管理员确认"}, message="已提交，待企业管理员确认")


@router.get("/{token}", response_model=ApiResponse[dict])
async def public_hazard_publicity(
    token: str,
    scope: str = Query("all"),
    db: AsyncSession = Depends(get_db),
):
    """隐患公示公开页（免登录，§11.2）：token 校验 + 脱敏只读。

    token = `enterprises.hazard_public_token`；无效 → 404「链接已失效」（§16）。
    响应：企业名称（脱敏：首字符 + **）、公示列表（编号/标题/等级/状态/整改
    情况摘要，不含责任人/联系方式/照片/位置/内部备注）。
    口径：scope=ongoing/closed/all（字典 publicity_scope 码值，企业覆盖优先），
    默认 all，与企业内公示一致；非法 scope → 422。
    generated_at = 请求时刻（企业 token 无生成时间列——取舍：页面「生成于」
    展示当前时间即可满足；如需精确生成时刻后续可加列）；masked=True 标记数据
    已脱敏。
    """
    ent = (await db.execute(
        select(Enterprise).where(Enterprise.hazard_public_token == token)
    )).scalar_one_or_none()
    if not ent:
        raise HTTPException(404, "链接已失效")
    scopes = await _resolve_publicity_scopes(db, ent.id)
    if scope not in scopes:
        raise HTTPException(422, f"scope 非法: {scope}，可选 {sorted(scopes)}")
    q = select(HazardRecord).where(HazardRecord.enterprise_id == ent.id)
    if scope == "ongoing":
        q = q.where(HazardRecord.status != "closed")
    elif scope == "closed":
        q = q.where(HazardRecord.status == "closed")
    records = list((await db.execute(
        q.order_by(HazardRecord.created_at.desc())
    )).scalars().all())
    status_labels = await _dict_labels(db, ent.id, "record_status_label")
    source_labels = await _dict_labels(db, ent.id, "source_type")
    latest = await _latest_rectifications(db, [r.id for r in records])
    return ApiResponse(data={
        "enterprise_name": _mask_enterprise_name(ent.name),
        "items": [
            _publicity_row(r, status_labels, source_labels,
                           _rectification_summary(r, latest.get(r.id)))
            for r in records
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "masked": True,
    })
