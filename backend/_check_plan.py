import asyncio
from app.database import async_session
from sqlalchemy import text
async def check():
    async with async_session() as db:
        r = await db.execute(text("SELECT id, title, status, plan_type FROM plan_projects ORDER BY created_at DESC LIMIT 5"))
        for row in r.fetchall():
            print(f"{str(row[0])[:8]}... | {row[1]} | {row[2]} | {row[3]}")
asyncio.run(check())
