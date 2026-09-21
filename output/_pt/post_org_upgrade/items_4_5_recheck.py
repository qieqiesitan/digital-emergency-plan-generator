"""复验 ⑤（读 positions 而非 extra_node_ids）+ 补做 ④ 章节自动填充。"""
import asyncio
import sys

import httpx
from sqlalchemy import select, text

import app.main  # noqa: F401
from app.database import async_session
from app.models.enterprise import PlanSection

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
NAME = "回归测试员"
KEY = "sec_1"

rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:34s} {detail}")


async def set_autofill(enabled: bool) -> None:
    async with async_session() as db:
        await db.execute(text(
            "update plan_sections set auto_fill=:f, auto_fill_source=:s "
            "where plan_project_id=:p and section_key=:k"
        ), {"f": enabled, "s": "org_structure" if enabled else None, "p": PLAN, "k": KEY})
        await db.commit()


async def clear_section() -> None:
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

        # ⑤ 建「主岗 + 兼岗」成员并按 positions 复验
        await c.put(f"{BASE}/enterprises/{ENT}/org/nodes", headers=h, json={"nodes": [
            {"id": "n_main", "type": "dept", "name": "主岗部门", "parent_id": None, "members": []},
            {"id": "n_extra", "type": "team", "name": "兼岗班组", "parent_id": None, "members": []},
        ]})
        r = await c.post(f"{BASE}/enterprises/{ENT}/org/members", headers=h,
                         json={"name": NAME, "role": "member", "org_node_id": "n_main",
                               "extra_node_ids": ["n_extra"]})
        mid = (r.json().get("data") or {}).get("id")
        pos = ((r.json().get("data") or {}).get("positions")) or []
        rec("⑤ 创建响应含 positions", len(pos) == 2 and any(p.get("is_primary") for p in pos),
            f"positions={pos}")

        r = await c.get(f"{BASE}/enterprises/{ENT}/org/members", headers=h)
        mine = [m for m in (r.json().get("data") or []) if m.get("id") == mid]
        pos_list = (mine[0].get("positions") if mine else []) or []
        rec("⑤ 列表接口返回 positions", len(pos_list) == 2, f"positions={pos_list}")

        # ④ 章节自动填充：临时把 sec_1 设为 auto_fill(org_structure)
        await set_autofill(True)
        await c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
        r = await c.post(f"{BASE}/plans/{PLAN}/sections/{KEY}/autofill", headers=h)
        rec("④ 空应急组织 → 明确报错", r.status_code == 400 and "应急组织" in r.text,
            f"HTTP {r.status_code} {r.text[:60]}")

        await c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": [
            {"id": "u1", "name": "应急指挥部", "roles": [
                {"id": "r1", "name": "总指挥", "member_ids": [mid]}]}]})
        r = await c.post(f"{BASE}/plans/{PLAN}/sections/{KEY}/autofill", headers=h)
        content = (r.json().get("data") or {}).get("content") or ""
        rec("④ 有应急组织 → 填充含人名", r.status_code == 200 and NAME in content,
            f"HTTP {r.status_code} 正文 {len(content)} 字，含人名={NAME in content}")
        rec("④ 填充结果标为非 AI", (r.json().get("data") or {}).get("ai_generated") is False,
            f"ai_generated={(r.json().get('data') or {}).get('ai_generated')}")

        # 清理
        await c.put(f"{BASE}/plans/{PLAN}/sections/{KEY}", headers=h, json={"content": ""})
        await set_autofill(False)
        await c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
        await c.put(f"{BASE}/enterprises/{ENT}/org/nodes", headers=h, json={"nodes": []})
        if mid:
            await c.delete(f"{BASE}/enterprises/{ENT}/org/members/{mid}", headers=h)

    await clear_section()
    print("\n（已清理：章节正文/auto_fill 标记/应急组织/组织树/成员）")
    bad = [r for r in rows if not r[1]]
    print(f"==== ④⑤ 复验：{len(rows)} 项，失败 {len(bad)}")
    for n, _, d in bad:
        print(f"   FAIL {n}: {d}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
