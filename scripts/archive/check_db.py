import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

async def check():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/emergency_plan")
    session_factory = async_sessionmaker(engine)
    async with session_factory() as s:
        r = await s.execute(text("SHOW server_encoding"))
        print("Server encoding:", r.scalar())
        r = await s.execute(text("SHOW client_encoding"))
        print("Client encoding:", r.scalar())
        r = await s.execute(text("SELECT datname, encoding, datcollate, datctype FROM pg_database WHERE datname='emergency_plan'"))
        row = r.fetchone()
        print("DB:", row)
        # Check users
        r = await s.execute(text("SELECT id, email, name, role FROM users"))
        for row in r:
            print("User:", row)
        # Check enterprises
        r = await s.execute(text("SELECT id, name, industry FROM enterprises"))
        for row in r:
            print("Enterprise:", row)
    await engine.dispose()

asyncio.run(check())
