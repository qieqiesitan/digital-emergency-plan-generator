import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

async def fix():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/emergency_plan")
    session_factory = async_sessionmaker(engine)
    async with session_factory() as s:
        # Fix user name
        await s.execute(text("UPDATE users SET name='测试用户' WHERE email='test@test.com'"))
        # Delete garbled enterprises (those with ???? names, keep real ones)
        r = await s.execute(text("SELECT id, name FROM enterprises WHERE name LIKE '%?%' OR name LIKE '%????%'"))
        bad = [row[0] for row in r]
        for bid in bad:
            # Delete associated data first
            await s.execute(text("DELETE FROM risk_sources WHERE enterprise_id=:id"), {"id": str(bid)})
            await s.execute(text("DELETE FROM emergency_resources WHERE enterprise_id=:id"), {"id": str(bid)})
            await s.execute(text("DELETE FROM enterprises WHERE id=:id"), {"id": str(bid)})
        await s.commit()
        # Verify
        r = await s.execute(text("SELECT name FROM users WHERE email='test@test.com'"))
        print("User:", r.scalar())
        r = await s.execute(text("SELECT id, name FROM enterprises ORDER BY created_at"))
        for row in r:
            print("Enterprise:", row)
    await engine.dispose()

asyncio.run(fix())
