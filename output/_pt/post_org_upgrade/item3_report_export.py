"""定向回归 ③：资源调查报告导出通道（造一份最小报告 → 导出 → 校验 → 清理）。"""
import asyncio
import io
import sys
import zipfile

import httpx
from sqlalchemy import delete, select

import app.main  # noqa: F401
from app.database import async_session
from app.models.resource_investigation import ResourceInvestigationReport

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
MARK = "回归验证用资源调查章节标题"


async def create_report() -> str:
    async with async_session() as db:
        rep = ResourceInvestigationReport(
            enterprise_id=ENT, status="draft",
            summary={"chapters": {"ch1": {"title": MARK,
                                          "content": "<p>本企业应急队伍与物资见应急组织与资源台账。</p>"}}},
        )
        db.add(rep)
        await db.commit()
        await db.refresh(rep)
        return rep.id


async def drop_report(rid: str) -> None:
    async with async_session() as db:
        await db.execute(delete(ResourceInvestigationReport).where(ResourceInvestigationReport.id == rid))
        await db.commit()


async def main() -> int:
    rid = await create_report()
    print(f"① 造报告：{rid}")
    ok = True
    async with httpx.AsyncClient(timeout=180) as c:
        token = (await c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                         "password": "test123456"})).json()
        h = {"Authorization": f"Bearer {(token.get('data') or {}).get('access_token')}"}
        r = await c.get(f"{BASE}/enterprises/{ENT}/resource-investigation/preview", headers=h)
        print(f"② 预览：HTTP {r.status_code} {len(r.content)} 字节")
        r = await c.get(f"{BASE}/enterprises/{ENT}/resource-investigation/export", headers=h)
        size = len(r.content or b"")
        print(f"③ 导出：HTTP {r.status_code} {size} 字节")
        if r.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                joined = "\n".join(z.read(n).decode("utf-8", "ignore")
                                   for n in z.namelist() if n.endswith(".xml"))
            hit = MARK in joined
            print(f"④ docx 含章节标题：{hit}")
            ok = hit
        else:
            print(f"   失败：{r.text[:200]}")
            ok = False
    await drop_report(rid)
    print("⑤ 已清理报告")
    print("\n" + ("[OK] 资源调查报告导出通道正常" if ok else "[X] 导出通道有问题"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
