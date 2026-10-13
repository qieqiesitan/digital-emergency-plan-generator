"""宿主 -> localhost:5438 完整 Postgres 协议登录验证（排查 5438 浏览器打不开一案）。"""
import asyncio

import asyncpg


async def main():
    conn = await asyncpg.connect(
        host="localhost",
        port=5438,
        user="postgres",
        password="postgres",
        database="emergency_plan",
    )
    version = await conn.fetchval("SELECT version()")
    tables = await conn.fetchval(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    )
    await conn.close()
    print("LOGIN OK")
    print("server:", version.split(",")[0])
    print("public tables:", tables)


asyncio.run(main())
