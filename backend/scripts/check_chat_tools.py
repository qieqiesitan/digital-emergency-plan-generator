"""逐个调用聊天助手的工具层（绕过 LLM），巡检 37 个工具是否可用。

为什么需要：聊天助手的工具由模型按需调用，出问题时表现为"助手答不出来"，
很难定位是提示词、模型还是工具本身坏。这个脚本直接 `dispatch()` 每个工具，
把"工具层"与"模型层"分开验证，**不消耗任何模型额度**。

用法（在 backend 容器内，或本机能连到 DATABASE_URL 的环境）：
    python scripts/check_chat_tools.py                  # 只跑只读工具（默认）
    python scripts/check_chat_tools.py --email a@b.c    # 指定账号
    python scripts/check_chat_tools.py --include-write  # 额外跑"写入类"里的安全子集

退出码：0 = 全部通过；1 = 有工具报错（打印 error 内容）。
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models.enterprise import Enterprise, PlanProject  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.chat_dispatch import dispatch  # noqa: E402

# 只读且零 AI 的工具：给上合法参数后应当返回正常结果
READ_TOOLS = [
    "get_dashboard", "get_ai_config", "get_preferences", "get_regulation_stats",
    "list_enterprises", "list_templates", "list_regulations", "list_plans",
    "get_enterprise", "get_plan", "list_resources", "list_risk_sources",
    "list_resource_investigations", "list_risk_assessments",
    "get_generation_progress", "search_regulations", "search_regulation_articles",
    "query_enterprise_knowledge",
]


def _brief(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


async def run(email: str) -> int:
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not user:
            print(f"账号不存在：{email}")
            return 1
        ent = (await db.execute(
            select(Enterprise).where(Enterprise.user_id == user.id).limit(1)
        )).scalar_one_or_none()
        plan = (await db.execute(
            select(PlanProject).where(PlanProject.user_id == user.id).limit(1)
        )).scalar_one_or_none()
        ctx = {
            "enterprise_id": ent.id if ent else "",
            "plan_id": plan.id if plan else "",
            "keyword": "", "query": "动火作业", "top_k": 5,
            "question": "企业有哪些主要风险？", "name": "探针查询",
        }
        print(f"账号：{email}｜企业：{ctx['enterprise_id'] or '-'}｜预案：{ctx['plan_id'] or '-'}")

        failures = []
        for name in READ_TOOLS:
            args = {k: v for k, v in ctx.items() if k in _ARGS.get(name, ()) and v != ""}
            out = await dispatch(db, user, name, args)
            try:
                parsed = json.loads(out)
                ok = "error" not in parsed
                detail = _brief(json.dumps(parsed, ensure_ascii=False, default=str))
            except Exception:
                ok, detail = False, _brief(str(out))
            print(("PASS " if ok else "FAIL ") + f"{name:32s} {detail}")
            if not ok:
                failures.append((name, detail))

        print(f"\n合计 {len(READ_TOOLS) - len(failures)}/{len(READ_TOOLS)} PASS")
        return 1 if failures else 0


async def run_write_cycles(email: str) -> int:
    """写入类工具的安全闭环：建 → 查 → 改 → 删（自清理，失败也会兜底删）。"""
    created: dict[str, str] = {}
    failures: list[tuple[str, str]] = []
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        ent = (await db.execute(
            select(Enterprise).where(Enterprise.user_id == user.id).limit(1)
        )).scalar_one_or_none()

        async def call(name: str, args: dict, label: str | None = None):
            out = await dispatch(db, user, name, args)
            parsed = json.loads(out)
            ok = "error" not in parsed
            print(("PASS " if ok else "FAIL ")
                  + f"{label or name:34s} {_brief(json.dumps(parsed, ensure_ascii=False, default=str))}")
            if not ok:
                failures.append((label or name, str(parsed.get("error"))))
            return parsed

        # 资源：建 → 改 → 删
        res = await call("create_resource", {"enterprise_id": ent.id, "name": "巡检-资源",
                                            "category": "消防设施", "quantity": 1, "unit": "具"})
        rid = res.get("id") or (res.get("resource") or {}).get("id")
        created["resource"] = rid or ""
        if rid:
            await call("update_resource", {"resource_id": rid, "location": "巡检-位置"}, "update_resource")
            listed = await call("list_resources", {"enterprise_id": ent.id}, "list_resources(命中)")
            names = [r.get("name") for r in (listed.get("resources") or [])]
            if "巡检-资源" not in names:
                failures.append(("list_resources 应含新建资源", str(names)))
                print("FAIL list_resources 应含新建资源")
            await call("delete_resource", {"resource_id": rid}, "delete_resource")
            created["resource"] = ""

        # 预案：建 → 查 → 删
        plan = await call("create_plan", {"enterprise_id": ent.id, "plan_type": "comprehensive",
                                          "title": "巡检-预案"})
        pid = plan.get("id") or (plan.get("plan") or {}).get("id")
        created["plan"] = pid or ""
        if pid:
            await call("get_plan", {"plan_id": pid}, "get_plan(新建)")
            await call("delete_plan", {"plan_id": pid}, "delete_plan")
            created["plan"] = ""

        # 企业：建 → 查 → 改 → 删
        ent_new = await call("create_enterprise", {"name": "巡检-企业", "industry": "其他"})
        eid = ent_new.get("id") or (ent_new.get("enterprise") or {}).get("id")
        created["enterprise"] = eid or ""
        if eid:
            await call("get_enterprise", {"enterprise_id": eid}, "get_enterprise(新建)")
            await call("update_enterprise", {"enterprise_id": eid, "address": "巡检-地址"},
                       "update_enterprise")
            await call("delete_enterprise", {"enterprise_id": eid}, "delete_enterprise")
            created["enterprise"] = ""

        if created.get("resource"):
            await dispatch(db, user, "delete_resource", {"resource_id": created["resource"]})
        if created.get("plan"):
            await dispatch(db, user, "delete_plan", {"plan_id": created["plan"]})
        if created.get("enterprise"):
            await dispatch(db, user, "delete_enterprise", {"enterprise_id": created["enterprise"]})

    print(f"\n写入闭环合计 {'全部通过' if not failures else f'{len(failures)} 项失败'}")
    for name, err in failures:
        print(f"  - {name}: {err}")
    return 1 if failures else 0


# 每个工具需要的参数（与 chat.py 的 CHAT_TOOLS 声明一致）
_ARGS = {
    "get_enterprise": ("enterprise_id",),
    "list_plans": ("enterprise_id", "keyword"),
    "get_plan": ("plan_id",),
    "list_resources": ("enterprise_id",),
    "list_risk_sources": ("enterprise_id",),
    "list_resource_investigations": ("enterprise_id",),
    "list_risk_assessments": ("enterprise_id",),
    "get_generation_progress": ("plan_id",),
    "search_regulations": ("query",),
    "search_regulation_articles": ("query", "top_k"),
    "query_enterprise_knowledge": ("enterprise_id", "question"),
    "list_enterprises": ("keyword",),
    "list_regulations": ("keyword",),
}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", default="qa_e2e_test@test.com")
    ap.add_argument("--include-write", action="store_true", help="预留：写入类工具的安全子集")
    args = ap.parse_args()

    async def _main() -> int:
        # 两个阶段必须在同一个事件循环里：连接池与事件循环绑定，
        # 分两次 asyncio.run 会报 "attached to a different loop"。
        code = await run(args.email)
        if args.include_write:
            code = max(code, await run_write_cycles(args.email))
        return code

    raise SystemExit(asyncio.run(_main()))
