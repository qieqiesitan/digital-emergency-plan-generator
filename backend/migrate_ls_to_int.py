"""
L/S 字段迁移脚本 —— 将 risk_sources 表的 likelihood/severity 从文本转换为整数
运行方式: python backend/migrate_ls_to_int.py
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from sqlalchemy import text
from app.database import engine, async_session

TEXT_TO_INT = {"高": 4, "中": 3, "低": 2}


async def migrate():
    async with engine.begin() as conn:
        # Step 1: Add temporary integer columns
        print("Step 1: Adding temp columns...")
        await conn.execute(text(
            "ALTER TABLE risk_sources ADD COLUMN IF NOT EXISTS likelihood_int INTEGER DEFAULT 3"
        ))
        await conn.execute(text(
            "ALTER TABLE risk_sources ADD COLUMN IF NOT EXISTS severity_int INTEGER DEFAULT 3"
        ))

        # Step 2: Convert existing text data
        print("Step 2: Converting text values to integers...")
        for text_val, int_val in TEXT_TO_INT.items():
            await conn.execute(text(
                "UPDATE risk_sources SET likelihood_int = :int_val WHERE likelihood = :text_val"
            ), {"int_val": int_val, "text_val": text_val})
            await conn.execute(text(
                "UPDATE risk_sources SET severity_int = :int_val WHERE severity = :text_val"
            ), {"int_val": int_val, "text_val": text_val})

        # Step 3: Drop old columns
        print("Step 3: Dropping old columns...")
        await conn.execute(text("ALTER TABLE risk_sources DROP COLUMN IF EXISTS likelihood"))
        await conn.execute(text("ALTER TABLE risk_sources DROP COLUMN IF EXISTS severity"))

        # Step 4: Rename new columns
        print("Step 4: Renaming new columns...")
        await conn.execute(text("ALTER TABLE risk_sources RENAME COLUMN likelihood_int TO likelihood"))
        await conn.execute(text("ALTER TABLE risk_sources RENAME COLUMN severity_int TO severity"))

        print("Migration completed successfully!")


async def main():
    try:
        await migrate()
    except Exception as e:
        print(f"Migration may have partially succeeded or already been applied: {e}")
        print("You may need to restart the app for create_all to align the schema.")


if __name__ == "__main__":
    asyncio.run(main())
