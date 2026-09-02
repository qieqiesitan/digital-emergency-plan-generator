"""工作流执行器：pending→running→(paused/failed/completed)；步骤可重试；confirm 门控。

职责：
- 步骤按模板顺序顺序执行（不依赖 DAG 并行），失败按 max_retries 重试；
- confirm=True 的步骤在未确认时暂停（status=paused + current_step 指向该步），
  经 confirm_workflow_step 放行后继续执行；
- start_workflow 创建 workflow_runs/workflow_run_steps 记录并后台执行；
- 聊天工具（任务 6）通过 start_workflow/confirm_workflow_step 接入。

测试可直接替换 runner._execute_step 驱动 _run_steps，验证顺序/重试/门控语义。
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.services.workflow.models import WorkflowRun, WorkflowRunStep
from app.services.workflow.templates import TEMPLATES

logger = logging.getLogger(__name__)

_background_tasks: dict[str, asyncio.Task] = {}


class WorkflowRunner:
    """工作流执行器。db 为 SQLAlchemy AsyncSession（真实运行）或测试替身。"""

    def __init__(self, db):
        self._db = db

    # ── 状态机核心（内存执行，测试直接驱动）──

    async def _run_steps(self, run, template, ctx, max_retries: int = 2) -> dict:
        """按模板步骤顺序执行（confirm 步骤在 ctx['confirmed_steps'] 为 True 时放行）。

        每步失败重试 max_retries 次；仍失败抛 RuntimeError（由上层标记 run failed）。
        执行到未确认的 confirm 步骤时：run.status=paused、run.current_step=该步并返回。
        暂停恢复由调用方重建 ctx：ctx["_pending_gates"] 为等待确认的步骤集合（跳过），
        ctx["confirmed_steps"] 为已放行步骤（执行），ctx["steps"] 缓存已完成结果。
        """
        run.status = "running"
        results = ctx.setdefault("steps", {})
        pending_gates = ctx.get("_pending_gates") or set()
        confirmed = ctx.get("confirmed_steps") or {}

        for step in template["steps"]:
            name = step["name"]
            if name in results and not (
                isinstance(results[name], dict) and results[name].get("awaiting_confirmation")
            ):
                continue  # 已有结果（暂停恢复），不重复执行
            if step.get("confirm") and not confirmed.get(name):
                if name in pending_gates:
                    # 恢复时仍未放行：保持暂停，等 confirm_workflow_step 放行
                    run.status = "paused"
                    run.current_step = name
                    return results
                results[name] = {"awaiting_confirmation": True}
                run.status = "paused"
                run.current_step = name
                return results
            if name in pending_gates:
                # 已放行：清掉上一次暂停残留的 awaiting 标记，执行该步
                results.pop(name, None)
            outcome = None
            # 初始尝试 1 次 + 重试 max_retries 次
            for attempt in range(max_retries + 1):
                try:
                    outcome = await self._execute_step(step, ctx)
                    break
                except Exception as e:
                    if attempt >= max_retries:
                        raise RuntimeError(f"步骤 {name} 失败: {e}") from e
                    await asyncio.sleep(0.2)
            if outcome is not None:
                results[name] = outcome
        run.status = "completed"
        return results

    # ── 默认单步实现：调 chat_dispatch 工具（可被子类/测试覆盖）──

    async def _execute_step(self, step, ctx) -> dict:
        """默认实现：调 chat_dispatch.dispatch。子类/测试可覆盖。"""
        from app.services.chat_dispatch import dispatch

        tool = step["tool"]
        args = self._resolve_args(step.get("params_from"), ctx)
        result = await dispatch(self._db, ctx.get("_user"), tool, args)
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except Exception:
                parsed = {"raw": result}
            if isinstance(parsed, dict) and parsed.get("verified") is False:
                raise RuntimeError(parsed.get("error") or f"工具 {tool} 返回失败")
            return parsed
        return result if isinstance(result, dict) else {"result": result}

    def _resolve_args(self, spec, ctx) -> dict:
        """params_from 支持：字符串（表示从 ctx 取字段路径）或 dict（字段映射）。"""
        if isinstance(spec, str):
            return {"name": _resolve_path(ctx, spec)}
        if isinstance(spec, dict):
            return {k: _resolve_path(ctx, v) for k, v in spec.items()}
        return {}

    # ── DB 持久化入口（任务 6 聊天工具调用）──

    async def start_workflow(self, user, workflow_name: str, params: dict | None = None,
                             background: bool = True):
        """创建 workflow run + 步骤记录；background=True 时后台执行并立即返回。"""
        template = TEMPLATES.get(workflow_name)
        if not template:
            raise ValueError(f"未知工作流模板: {workflow_name}")
        run = WorkflowRun(user_id=user.id, workflow_name=workflow_name,
                          params=params or {}, status="running", current_step=None)
        self._db.add(run)
        await self._flush_safe()
        step_records = []
        for step in template["steps"]:
            rec = WorkflowRunStep(run_id=run.id, step_name=step["name"], status="pending")
            self._db.add(rec)
            step_records.append(rec)
        await self._flush_safe()
        await self._commit_safe()
        if background:
            try:
                task = asyncio.create_task(self._execute_in_background(run.id))
            except RuntimeError:
                # 无运行中事件循环（同步测试环境）：同步执行
                await self._execute_in_background(run.id)
            else:
                _background_tasks[run.id] = task
        else:
            await self._execute_in_background(run.id)
        return run

    async def confirm_workflow_step(self, run_id: str, step_name: str):
        """确认门控放行：run 须处于 paused 且 current_step=step_name，随后后台继续执行。"""
        run = (await (await self._db.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )).scalar_one_or_none())
        if not run:
            raise ValueError(f"工作流不存在: {run_id}")
        if run.status != "paused" or run.current_step != step_name:
            raise ValueError(f"工作流 {run_id} 未在等待步骤 {step_name} 的确认")
        rec = (await (await self._db.execute(
            select(WorkflowRunStep).where(
                WorkflowRunStep.run_id == run_id,
                WorkflowRunStep.step_name == step_name,
            )
        )).scalar_one_or_none())
        if not rec:
            raise ValueError(f"步骤记录不存在: {run_id}/{step_name}")
        rec.status = "confirmed"
        run.status = "running"
        await self._commit_safe()
        try:
            task = asyncio.create_task(self._execute_in_background(run.id))
        except RuntimeError:
            await self._execute_in_background(run.id)
        else:
            _background_tasks[run.id] = task
        return run

    async def _execute_in_background(self, run_id: str) -> dict:
        """后台执行体：独立 session 重建 ctx，跑 _run_steps，持久化步骤结果。"""
        from app.database import async_session
        from app.models.user import User

        try:
            async with async_session() as bg_db:
                bg_runner = WorkflowRunner(bg_db)
                run = (await (await bg_db.execute(
                    select(WorkflowRun).where(WorkflowRun.id == run_id)
                )).scalar_one_or_none())
                if not run:
                    logger.warning("后台工作流不存在 run=%s", run_id)
                    return {}
                template = TEMPLATES.get(run.workflow_name)
                if not template:
                    run.status = "failed"
                    await bg_db.commit()
                    return {}
                user = (await (await bg_db.execute(
                    select(User).where(User.id == run.user_id)
                )).scalar_one_or_none())
                step_rows = (await (await bg_db.execute(
                    select(WorkflowRunStep).where(WorkflowRunStep.run_id == run_id)
                    .order_by(WorkflowRunStep.step_name)
                ))).scalars().all()
                ctx = {"params": run.params or {}, "_user": user}
                confirmed_steps = {}
                pending_gates = set()
                for rec in step_rows:
                    if rec.status == "confirmed":
                        confirmed_steps[rec.step_name] = True
                    if rec.status == "pending" and run.current_step == rec.step_name:
                        pending_gates.add(rec.step_name)
                    if rec.status in ("completed", "confirmed") and rec.result:
                        ctx.setdefault("steps", {})[rec.step_name] = rec.result
                ctx["confirmed_steps"] = confirmed_steps
                ctx["_pending_gates"] = pending_gates
                ctx["_wf_template"] = template
                try:
                    results = await bg_runner._run_steps(run, template, ctx)
                except RuntimeError as step_err:
                    # 持久化失败步骤的 error（error 列在 workflow_run_steps）
                    msg = str(step_err)
                    failed_name = None
                    for step in template["steps"]:
                        if f"步骤 {step['name']} 失败" in msg:
                            failed_name = step["name"]
                            break
                    for rec in step_rows:
                        if rec.step_name == failed_name:
                            rec.status = "failed"
                            rec.error = msg
                            rec.finished_at = datetime.now(timezone.utc)
                    run.status = "failed"
                    await bg_db.commit()
                    raise
                # 持久化步骤结果（完成/失败/等待确认）
                for rec in step_rows:
                    out = results.get(rec.step_name)
                    if out is None:
                        continue
                    if isinstance(out, dict) and out.get("awaiting_confirmation"):
                        rec.status = "pending"
                    else:
                        rec.status = "completed"
                        rec.result = out
                        rec.finished_at = datetime.now(timezone.utc)
                if run.status == "running":
                    run.status = "completed"
                await bg_db.commit()
                return results
        except RuntimeError:
            # 步骤失败已在上层持久化（run failed + 步骤 error），此处仅记录日志
            raise
        except Exception:
            logger.exception("后台工作流执行失败 run=%s", run_id)
            raise

    # ── 安全持久化小工具（测试替身/真实 session 均可容忍）──

    async def _flush_safe(self):
        try:
            await self._db.flush()
        except Exception:
            pass

    async def _commit_safe(self):
        try:
            await self._db.commit()
        except Exception:
            pass


def _resolve_path(ctx: dict, path: str):
    """解析 'steps.create_enterprise.id' / 'params.name' 形式路径。"""
    node = ctx
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node
