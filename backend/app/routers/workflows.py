"""前端可驱动的端到端工作流入口。

背景（2026-09-20）：工作流执行器 `WorkflowRunner` 与模板早就在跑，但**只挂了聊天工具**
（`run_workflow` / `get_workflow_progress` / `confirm_workflow_step`）——预案页上没有任何按钮。
这里补三个薄端点，把同一套能力暴露给界面：

· `POST /plans/{plan_id}/workflows/generate-review` 对已有预案跑「生成正文 → 质量复核」
· `GET  /workflows/{run_id}`                        查进度（步骤状态 + 复核结果）
· `POST /workflows/{run_id}/confirm/{step_name}`     放行确认门控（生成前必须点一次）

权限：全部按 `user_id` 归属校验（run 属于当前用户；启动时校验预案归属），不做管理员限制——
工作流操作的都是调用者自己的预案。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import PlanProject
from app.schemas.common import ApiResponse
from app.services.workflow.models import WorkflowRun, WorkflowRunStep
from app.services.workflow.runner import WorkflowRunner

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Workflows"])

TEMPLATE_GENERATE_REVIEW = "plan_generate_review"


def _run_payload(run: WorkflowRun, steps: list[WorkflowRunStep]) -> dict:
    """与聊天工具 `get_workflow_progress` 保持同一形状，前端/模型看到的是同一套字段。"""
    return {
        "run_id": run.id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "current_step": run.current_step,
        "params": run.params or {},
        "steps": [
            {
                "step_name": s.step_name,
                "status": s.status,
                "retry_count": s.retry_count,
                "error": s.error,
                # review 步骤的结果就是质检明细（issues/warnings），前端直接展示
                "result": s.result,
            }
            for s in steps
        ],
    }


async def _load_run(db: AsyncSession, run_id: str, user_id: str) -> WorkflowRun:
    run = (await db.execute(
        select(WorkflowRun).where(WorkflowRun.id == run_id, WorkflowRun.user_id == user_id)
    )).scalar_one_or_none()
    if not run:
        raise HTTPException(404, "工作流不存在或无权访问")
    return run


async def _load_steps(db: AsyncSession, run_id: str) -> list[WorkflowRunStep]:
    return list((await db.execute(
        select(WorkflowRunStep).where(WorkflowRunStep.run_id == run_id)
        .order_by(WorkflowRunStep.step_name)
    )).scalars().all())


@router.post("/plans/{plan_id}/workflows/generate-review", response_model=ApiResponse[dict])
async def start_generate_review(
    plan_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对已有预案启动「生成 → 复核」工作流（会停在"生成前确认"门控上）。"""
    plan = (await db.execute(
        select(PlanProject).where(PlanProject.id == plan_id, PlanProject.user_id == current_user.id)
    )).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "预案不存在")

    try:
        run = await WorkflowRunner(db).start_workflow(
            current_user, TEMPLATE_GENERATE_REVIEW, {"plan_id": plan_id}, background=True)
    except ValueError as exc:               # 模板缺失/名字写错：500 不如直接说清
        logger.exception("启动工作流失败 plan=%s", plan_id)
        raise HTTPException(500, f"工作流模板不可用：{exc}") from exc

    steps = await _load_steps(db, run.id)
    return ApiResponse(data=_run_payload(run, steps),
                       message="已启动；生成前需要确认")


@router.get("/workflows/{run_id}", response_model=ApiResponse[dict])
async def get_workflow_run(
    run_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _load_run(db, run_id, current_user.id)
    return ApiResponse(data=_run_payload(run, await _load_steps(db, run.id)))


@router.post("/workflows/{run_id}/confirm/{step_name}", response_model=ApiResponse[dict])
async def confirm_workflow_step(
    run_id: str,
    step_name: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """放行等待确认的步骤（未处于等待该步时会明确报错，不静默）。"""
    await _load_run(db, run_id, current_user.id)
    try:
        await WorkflowRunner(db).confirm_workflow_step(run_id, step_name)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    run = await _load_run(db, run_id, current_user.id)
    return ApiResponse(data=_run_payload(run, await _load_steps(db, run.id)),
                       message=f"已确认「{step_name}」")
