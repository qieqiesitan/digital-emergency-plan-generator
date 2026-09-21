"""容器内探针（零 AI 额度）：plan_generate_review 工作流能启动并**停在生成确认门控**。

只验到"暂停"这一步——确认会真的触发 AI 生成（耗时 + 花额度），所以不确认；
跑完删除本次 run/step 记录。
"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.chat_dispatch import dispatch  # noqa: E402
from app.services.workflow.models import WorkflowRun, WorkflowRunStep  # noqa: E402

PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:34s} {detail}", flush=True)


async def main() -> int:
    async with async_session() as db:
        user = (await db.execute(
            select(User).where(User.email == "qa_e2e_test@test.com")
        )).scalar_one_or_none()
        if user is None:
            print("!! QA 账号不存在")
            return 1

        out = await dispatch(db, user, "run_workflow",
                             {"workflow_name": "plan_generate_review",
                              "params": {"plan_id": PLAN}})
        if isinstance(out, str):
            out = json.loads(out)
        rec("启动工作流", out.get("verified") is True, str(out)[:120])
        run_id = out.get("run_id")

        await asyncio.sleep(1.5)
        run = (await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))).scalar_one()
        steps = (await db.execute(
            select(WorkflowRunStep).where(WorkflowRunStep.run_id == run_id)
        )).scalars().all()
        status = {s.step_name: s.status for s in steps}
        rec("停在生成确认门控", run.status == "paused" and run.current_step == "generate",
            f"status={run.status} current={run.current_step} steps={status}")
        rec("复核步骤未提前执行", status.get("review") == "pending", f"review={status.get('review')}")

        # 清理（不确认）
        for s in steps:
            await db.delete(s)
        await db.delete(run)
        await db.commit()

        left = (await db.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )).scalar_one_or_none()
        rec("清理本次 run", left is None, "run 已删除")

        bad = [r for r in rows if not r[1]]
        print(f"\n==== plan_generate_review 门控探针：{len(rows)} 项，失败 {len(bad)}")
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
