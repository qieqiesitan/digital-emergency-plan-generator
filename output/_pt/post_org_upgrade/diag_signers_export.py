"""一次跑全：建成员 → 写应急组织 → 看 load_emergency_groups 形状 → 导出 docx 找名字 → 清理。

判定：
  · 若 groups 里有 name 而 docx 里没有 → 渲染/模板侧丢数据（真缺陷）
  · 若 groups 里就没有 name → 切源映射漏了成员姓名（真缺陷）
"""
import asyncio
import io
import json
import sys
import zipfile

import httpx
from sqlalchemy import select

sys.path.insert(0, "/app")

from app.database import async_session  # noqa: E402
import app.main  # noqa: E402,F401 - 先加载全量模型/路由，保证所有表已注册（否则 FK 解析失败）
from app.models.enterprise import Enterprise  # noqa: E402,F401
from app.models.enterprise_org import EnterpriseMember  # noqa: E402
from app.services.emergency_org_service import load_emergency_groups, save_emergency_org  # noqa: E402

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
MEMBER = "签署冒烟测试员"
UNIT = "签署页诊断单位"
BODY = "<h3>总则</h3><p>验证组织架构升级后的导出与签署页取数。</p>"


async def main() -> int:
    async with async_session() as db:
        member = EnterpriseMember(enterprise_id=ENT, name=MEMBER, enabled=True)
        db.add(member)
        await db.commit()
        await db.refresh(member)
        print(f"① 建成员：{member.id} {member.name}")

        await save_emergency_org(db, ENT, [{
            "id": "u1", "name": UNIT,
            "roles": [{"id": "r1", "name": "总指挥", "member_ids": [member.id]}],
        }])
        await db.commit()

        groups = await load_emergency_groups(db, ENT)
        print(f"\n② load_emergency_groups：{json.dumps(groups, ensure_ascii=False)[:400]}")
        names_in_groups = [m.get("name") for g in (groups or []) for m in g.get("members", [])]
        print(f"   分组里的成员名：{names_in_groups}")

    with httpx.Client(timeout=180) as c:
        token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                    "password": "test123456"}).json()
                 .get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}
        c.put(f"{BASE}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": BODY})
        r = c.post(f"{BASE}/plans/{PLAN}/export/docx", headers=h, json={})
        print(f"\n③ 导出 docx：HTTP {r.status_code} {len(r.content or b'')} 字节")
        in_docx = False
        if r.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                joined = "\n".join(z.read(n).decode("utf-8", "ignore")
                                   for n in z.namelist() if n.endswith(".xml"))
            in_docx = MEMBER in joined
            print(f"   docx 含成员名：{in_docx}；含单位名：{UNIT in joined}")

        # 清理
        c.put(f"{BASE}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": ""})
        c.put(f"{BASE}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})

    async with async_session() as db:
        m = (await db.execute(select(EnterpriseMember).where(EnterpriseMember.name == MEMBER))).scalars().first()
        if m:
            await db.delete(m)
            await db.commit()
    print("\n④ 已清理（正文/应急组织/测试成员）")

    if names_in_groups and MEMBER in names_in_groups and not in_docx:
        print("=> 结论：分组里有成员名但 docx 里没有 → **渲染/模板侧丢数据（真缺陷）**")
    elif not names_in_groups:
        print("=> 结论：分组里就没有成员名 → **切源映射漏了成员（真缺陷）**")
    elif in_docx:
        print("=> 结论：签署页取数正常（此前是我造的单元没有成员，误判）")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
