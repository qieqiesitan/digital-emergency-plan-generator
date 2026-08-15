"""隐患排查治理状态机服务（任务 2，TDD）。

状态值域（HazardRecord.status）：registered / grading / pending_approval /
rectifying / reviewing / second_review / closed。

流转：
registered --grade(一般)--> rectifying；--grade(重大)--> pending_approval
grading --grade--> 重新定级（一般→rectifying / 重大→pending_approval）
pending_approval --approve--> rectifying；--reject--> grading
  （不允许 rectify，防绕过重大挂牌审批门）
rectifying --rectify--> reviewing
reviewing --review pass--> 停留 reviewing（标准模式/一般）；严格+重大 --> second_review
second_review --review pass--> 停留 second_review；--fail--> rectifying
reviewing / second_review --close(enterprise_admin)--> closed
  （写 review_type=close 记录 + closed_at，销号语义统一为管理员确认）

权限：ROLE_GATE；复查人 ≠ 整改人（422 语义）；整改须由 grade/approve 指定的
rectification_user_id 本人执行（enterprise_admin 例外）；严格模式+重大销号前
必须 second_review。每个动作写 hazard_audit_logs 留痕。

销号语义（B 规格 §10/§3.5）：review pass 不再直接 closed——标准模式 pass 后
记录留在 reviewing（写 first_review pass 记录）；严格+重大 pass → second_review；
second_review pass 留在 second_review；由 enterprise_admin 执行 close 才 closed。

说明：计划/交接契约中的 TRANSITIONS 字面将「rectifying: {"review"}」与
「reviewing: {"close","rectify"}」写成动作名（与目标状态名 rectify/reviewing
同形易混写）。按 apply_transition 行为描述与 B 规格 §5.13 状态机图修正为：
rectifying 状态执行 rectify（整改提交）→ reviewing；reviewing/second_review
状态执行 review（复查判定 pass/fail）与 close（销号）。
"""

from datetime import date, datetime, timedelta, timezone
import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import Enterprise
from app.models.hazard_management import (
    HazardApproval,
    HazardAuditLog,
    HazardRecord,
    HazardRectification,
    HazardReview,
)


TRANSITIONS = {
    "registered": {"grade"},
    "grading": {"grade"},
    "pending_approval": set(),
    "rectifying": {"rectify"},
    "reviewing": {"close", "review"},
    "second_review": {"close", "review"},
}

ROLE_GATE = {
    "grade": {"enterprise_admin"},
    "pending_approval": {"enterprise_admin"},
    "rectify": {"rectifier", "enterprise_admin"},
    "review": {"reviewer", "enterprise_admin"},
    "close": {"enterprise_admin"},
}

LEVEL_MAJOR = "major"
LEVEL_GENERAL = "general"
PLAN_KEYS = ("goal", "measures", "budget", "emergency_measures", "acceptance_criteria")


def _is_major(record) -> bool:
    return record.level == LEVEL_MAJOR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rule_days(rules: Optional[dict], key: str) -> Optional[int]:
    """从 deadline_rules 取天数，兼容 {"key": {"days": N}} / {"key": N} / JSON 字符串。"""
    entry = (rules or {}).get(key)
    if isinstance(entry, dict):
        days = entry.get("days")
        return int(days) if isinstance(days, (int, float)) else None
    if isinstance(entry, (int, float)):
        return int(entry)
    if isinstance(entry, str):
        try:
            parsed = json.loads(entry)
            if isinstance(parsed, dict) and isinstance(parsed.get("days"), (int, float)):
                return int(parsed["days"])
        except (TypeError, ValueError):
            return None
    return None


def _audit_log(record, actor_user, action: str, detail: dict) -> HazardAuditLog:
    return HazardAuditLog(
        enterprise_id=record.enterprise_id,
        record_id=record.id,
        user_id=getattr(actor_user, "id", None),
        action=action,
        detail=detail,
    )


def can_transition(record, action: str, actor_role: str, strict_mode: bool) -> tuple[bool, str]:
    """校验动作/权限/复查人/严格模式销号规则，返回 (ok, reason)。"""
    allowed = TRANSITIONS.get(record.status, set())
    if action not in allowed:
        return False, f"状态 {record.status} 不允许执行动作 {action}"
    if actor_role not in ROLE_GATE.get(action, set()):
        return False, f"角色 {actor_role} 无权执行动作 {action}"
    if action == "review":
        if not record.reviewer_user_id:
            return False, "未指定复查人，无法复查"
        if record.reviewer_user_id == record.rectification_user_id:
            return False, "复查人不能为整改人"
    if action == "close" and strict_mode and _is_major(record) and record.status != "second_review":
        return False, "严格模式下重大隐患须先通过二次复核（second_review）后才能销号"
    return True, ""


def _error_status(action: str, record, actor_role: str) -> int:
    """can_transition 失败时映射 HTTP 语义：非法流转 409、角色不符 403、其余 422。"""
    if action not in TRANSITIONS.get(record.status, set()):
        return 409
    if actor_role not in ROLE_GATE.get(action, set()):
        return 403
    return 409 if action == "close" else 422


async def apply_transition(
    db: AsyncSession,
    record: HazardRecord,
    action: str,
    actor_user,
    actor_role: str,
    payload: dict,
    enterprise: Optional[Enterprise],
) -> HazardRecord:
    """执行状态流转：can_transition 校验 → 按 action 更新字段 → audit log。"""
    payload = payload or {}
    strict_mode = getattr(enterprise, "hazard_closure_mode", "standard") == "strict"
    old_status = record.status

    if action in ("approve", "reject"):
        # 审批动作不在 TRANSITIONS 常量中，单独校验状态与角色
        if record.status != "pending_approval":
            raise HTTPException(409, "仅待审批（pending_approval）状态的隐患可审批")
        if actor_role not in ROLE_GATE["pending_approval"]:
            raise HTTPException(403, f"角色 {actor_role} 无权执行动作 {action}")
    else:
        ok, reason = can_transition(record, action, actor_role, strict_mode)
        if not ok:
            raise HTTPException(_error_status(action, record, actor_role), reason)

    detail: dict[str, Any] = {"from": old_status}

    if action == "grade":
        _apply_grade(record, payload)
    elif action == "approve":
        db.add(HazardApproval(record_id=record.id, user_id=getattr(actor_user, "id", None), action="approve",
                              comment=payload.get("comment")))
        if payload.get("rectification_user_id"):
            record.rectification_user_id = payload["rectification_user_id"]
        record.status = "rectifying"
    elif action == "reject":
        db.add(HazardApproval(record_id=record.id, user_id=getattr(actor_user, "id", None), action="reject",
                              comment=payload.get("comment")))
        # 语义：退回分级阶段（grading）重新定级，比退回 registered 更贴近
        # 「审批不通过 → 复核定级材料」的流程（规格 §5.13 只规定通过路径，
        # 契约允许 grading 或 registered，此处选 grading 并说明）。
        record.status = "grading"
    elif action == "rectify":
        _apply_rectify(db, record, actor_user, actor_role, payload)
    elif action == "review":
        _apply_review(db, record, actor_user, actor_role, payload, strict_mode)
    elif action == "close":
        db.add(HazardReview(record_id=record.id, user_id=getattr(actor_user, "id", None),
                            review_type="close", result="pass", comment=payload.get("comment")))
        record.status = "closed"
        record.closed_at = _now()

    detail["to"] = record.status
    db.add(_audit_log(record, actor_user, action, detail))
    return record


def _apply_grade(record: HazardRecord, payload: dict) -> None:
    """分级：写等级/类型/依据/期限/治理方案，一般→rectifying，重大→pending_approval。"""
    level = payload.get("level")
    if level not in (LEVEL_MAJOR, LEVEL_GENERAL):
        raise HTTPException(422, "level 必须为 major（重大）或 general（一般）")
    record.level = level
    record.hazard_type = payload.get("hazard_type") or record.hazard_type
    record.grading_basis = payload.get("grading_basis")
    if payload.get("rectification_user_id"):
        record.rectification_user_id = payload["rectification_user_id"]
    if payload.get("level_source"):
        record.level_source = payload["level_source"]
    days = _rule_days(payload.get("deadline_rules"), LEVEL_MAJOR if _is_major(record) else LEVEL_GENERAL)
    record.deadline = date.today() + timedelta(days=days) if days else None

    plan = payload.get("rectification_plan")
    if _is_major(record):
        if not record.grading_basis:
            raise HTTPException(422, "重大隐患须填写判定依据（grading_basis）")
        if not isinstance(plan, dict) or not all(k in plan for k in PLAN_KEYS):
            raise HTTPException(422, "重大隐患须填写完整治理方案（goal/measures/budget/emergency_measures/acceptance_criteria）")
        record.rectification_plan = plan
        record.status = "pending_approval"
    else:
        record.status = "rectifying"


def _apply_rectify(db, record: HazardRecord, actor_user, actor_role: str, payload: dict) -> None:
    """整改：校验整改人本人（enterprise_admin 例外），写 hazard_rectifications + 证据，状态→reviewing。"""
    if actor_role != "enterprise_admin" and getattr(actor_user, "id", None) != record.rectification_user_id:
        raise HTTPException(422, "仅指定的整改责任人可提交整改")
    db.add(HazardRectification(
        record_id=record.id,
        user_id=getattr(actor_user, "id", None),
        content=payload.get("content") or "",
        evidence=payload.get("evidence") or [],
        submitted_at=_now(),
    ))
    if payload.get("reviewer_user_id"):
        record.reviewer_user_id = payload["reviewer_user_id"]
    record.status = "reviewing"


def _apply_review(db, record: HazardRecord, actor_user, actor_role: str, payload: dict, strict_mode: bool) -> None:
    """复查：pass→（严格+重大→second_review，其余停留当前复查状态，不直接销号）；fail→退回 rectifying。"""
    result = payload.get("result")
    if result not in ("pass", "fail"):
        raise HTTPException(422, "复查结果 result 必须为 pass 或 fail")
    if actor_role == "reviewer" and getattr(actor_user, "id", None) != record.reviewer_user_id:
        raise HTTPException(422, "仅指定的复查人可执行复查")

    review_type = "second_review" if record.status == "second_review" else "first_review"
    db.add(HazardReview(
        record_id=record.id,
        review_type=review_type,
        user_id=getattr(actor_user, "id", None),
        result=result,
        comment=payload.get("comment"),
        evidence=payload.get("evidence") or [],
    ))
    if result == "fail":
        record.status = "rectifying"
    elif strict_mode and _is_major(record):
        record.status = "second_review"
    else:
        record.status = "reviewing"
