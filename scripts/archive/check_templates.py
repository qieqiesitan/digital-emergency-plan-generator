import asyncio
from app.database import async_session
from app.models.user import User
from app.models.enterprise import PlanTemplate
from sqlalchemy import select

async def check():
    async with async_session() as db:
        r = await db.execute(select(PlanTemplate).where(PlanTemplate.is_active == True))
        templates = r.scalars().all()
        print(f"Template count: {len(templates)}")
        for t in templates:
            keys = [s.get("key", "?") for s in (t.structure or [])]
            print(f"  id={t.id}, type={t.plan_type}, name={t.name}")
            print(f"  structure keys: {keys}")
            for s in (t.structure or []):
                subs = s.get("subsections", [])
                subkeys = [sub.get("key", "?") for sub in subs]
                print(f"    {s.get('key','?')}: {s.get('title','?')} subs={subkeys}")

asyncio.run(check())
