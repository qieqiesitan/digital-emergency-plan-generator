"""定向回归 ④章节自动填充（取应急组织）⑤主岗+兼岗 ⑧旧写接口下线行为。"""
import asyncio
import sys

import httpx
from sqlalchemy import select, text

import app.main  # noqa: F401 - 注册全部模型
from app.database import async_session
from app.models.enterprise_org import MemberPosition
from app.models.enterprise import PlanSection

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
NAME = "回归测试员"

rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:32s} {detail}")


async def first_autofill_section():
    async with async_session() as db:
        row = (await db.execute(
            select(PlanSection).where(PlanSection.plan_project_id == PLAN,
                                      PlanSection.auto_fill.is_(True)).limit(1)
        )).scalars().first()
        return row.section_key if row else None


async def member_posts(member_id: str):
    async with async_session() as db:
        posts = (await db.execute(
            select(MemberPosition).where(MemberPosition.member_id == member_id)
        )).scalars().all()
        return [(p.org_node_id, p.is_primary) for p in posts]


async def cleanup_sections():
    async with async_session() as db:
        await db.execute(text(
            "update plan_sections set content=null, ai_generated=false "
            "where plan_project_id=:p and coalesce(content,'')=''"), {"p": PLAN})
        await db.commit()


async def main() -> int:
    async with httpx.AsyncClient(timeout=120) as c:
        token = (await c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                         "password": "test123456"})).json()
        h = {"Authorization": f"Bearer {(token.get('data') or {}).get('access_token')}"}
        mid = None
        auto_key = await first_autofill_section()

        # ⑧ 旧写接口 → 410 + 迁移指引；旧读接口 → 200
        r = await c.put(f"{BASE}/enterprises/{ENT}/org-structure", headers=h, json={"groups": []})
        rec("⑧ 旧写接口 PUT 已下线", r.status_code == 410 and "emergency-org" in r.text,
            f"HTTP {r.status_code} {r.text[:70]}")
        r = await c.get(f"{BASE}/enterprises/{ENT}/org-structure", headers=h)
        rec("⑧ 旧读接口 GET 兼容", r.status_code == 200, f"HTTP {r.status_code}")

        # ⑤ 主岗 + 兼岗
        nodes = [
            {"id": "n_main", "type": "dept", "name": "主岗部门", "parent_id": None, "members": []},
            {"id": "n_extra", "type": "team", "name": "兼岗班组", "parent_id": None, "members": []},
        ]
        await c.put(f"{BASE}/enterprises/{ENT}/org/nodes", headers=h, json={"nodes": nodes})
        r = await c.post(f"{BASE}/enterprises/{ENT}/org/members", headers=h,
                         json={"name": NAME, "role": "member", "org_node_id": "n_main",
                               "extra_node_ids": ["n_extra"]})
        mid = (r.json().get("data") or {}).get("id")
        rec("⑤ 建成员(主岗+兼岗)", r.status_code == 201, f"HTTP {r.status_code} id={mid}")
        r = await c.get(f"{BASE}/enterprises/{ENT}/org/members", headers=h)
        mine = [m for m in (r.json().get("data") or []) if m.get("id") == mid]
        rec("⑤ 回读成员任职", bool(mine),
            f"org_node_id={mine[0].get('org_node_id') if mine else None} "
            f"extra={mine[0].get('extra_node_ids') if mine else None}")
        posts = await member_posts(mid) if mid else []
        rec("⑤ member_positions 落库", len(posts) >= 2 and any(p[1] for p in posts), f"rows={posts}")

        # ④ 章节自动填充
        if auto_key is None:
            rec("④ 找到 auto_fill 章节", False, "本预案没有 auto_fill=True 的章节")
        else:
            await c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
            r = await c.post(f"{BASE}/plans/{PLAN}/sections/{auto_key}/autofill", headers=h)
            rec("④ 空应急组织 → 明确报错", r.status_code == 400 and "应急组织" in r.text,
                f"HTTP {r.status_code} {r.text[:60]}")
            await c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": [
                {"id": "u1", "name": "应急指挥部", "roles": [
                    {"id": "r1", "name": "总指挥", "member_ids": [mid]}]}]})
            r = await c.post(f"{BASE}/plans/{PLAN}/sections/{auto_key}/autofill", headers=h)
            content = (r.json().get("data") or {}).get("content") or ""
            rec("④ 有应急组织 → 填充含人名", r.status_code == 200 and NAME in content,
                f"HTTP {r.status_code} 正文 {len(content)} 字")
            await c.put(f"{BASE}/plans/{PLAN}/sections/{auto_key}", headers=h, json={"content": ""})

        # 清理
        await c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
        await c.put(f"{BASE}/enterprises/{ENT}/org/nodes", headers=h, json={"nodes": []})
        if mid:
            await c.delete(f"{BASE}/enterprises/{ENT}/org/members/{mid}", headers=h)

    await cleanup_sections()
    print("\n（已清理）")
    bad = [r for r in rows if not r[1]]
    print(f"==== ④⑤⑧：{len(rows)} 项，失败 {len(bad)}")
    for n, _, d in bad:
        print(f"   FAIL {n}: {d}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
