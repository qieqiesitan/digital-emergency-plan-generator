"""把历史 AES-ECB 密文重加密为 AES-GCM（W2 密钥轮换工具）。

用法（backend 容器内，建议先 dry-run）：
    docker exec -e PYTHONPATH=/app -w /app emergency-plan-backend \
        python /app/scripts/rotate_encryption_key.py --dry-run
    docker exec -e PYTHONPATH=/app -w /app emergency-plan-backend \
        python /app/scripts/rotate_encryption_key.py --apply

前置条件（缺一不可）：
1. 新 `ENCRYPTION_KEY` 已注入并重启生效；
2. 旧密钥仍保留在 `ENCRYPTION_KEY_LEGACY`（逗号分隔），否则旧密文解不开；
3. 已做数据库备份（scripts/backup.sh）。

覆盖范围：`ai_configs.api_key_encrypted`、`third_party_config`（secret 类型）。
脚本幂等：已带 `gcm$` 前缀的行跳过；解密失败的行保持原值并计入 failed。
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.database import async_session
from app.models.enterprise import AIConfig
from app.models.third_party_config import ThirdPartyConfig
# FK 目标表注册：只导入 AIConfig 时，flush 阶段会因找不到 users 表而报
# NoReferencedTableError（dry-run 不 flush 所以看不出来）
from app.models.user import User  # noqa: F401
from app.services.secret_utils import GCM_PREFIX, decrypt_secret, encrypt_secret


async def rotate(dry_run: bool) -> dict:
    stats = {"ai_configs": 0, "third_party": 0, "skipped": 0, "failed": 0}
    failures: list[str] = []

    async with async_session() as db:
        for row in (await db.execute(select(AIConfig))).scalars().all():
            stored = row.api_key_encrypted or ""
            if not stored or stored.startswith(GCM_PREFIX):
                stats["skipped"] += 1
                continue
            try:
                plain = decrypt_secret(stored)
            except Exception:
                stats["failed"] += 1
                failures.append(f"ai_configs:{row.id}")
                continue
            stats["ai_configs"] += 1
            if not dry_run:
                row.api_key_encrypted = encrypt_secret(plain)

        tp_rows = (await db.execute(
            select(ThirdPartyConfig).where(ThirdPartyConfig.config_type == "secret")
        )).scalars().all()
        for row in tp_rows:
            stored = row.config_value or ""
            if not stored or stored.startswith(GCM_PREFIX):
                stats["skipped"] += 1
                continue
            try:
                plain = decrypt_secret(stored)
            except Exception:
                stats["failed"] += 1
                failures.append(f"third_party:{row.config_key}")
                continue
            stats["third_party"] += 1
            if not dry_run:
                row.config_value = encrypt_secret(plain)

        if not dry_run:
            await db.commit()

    return {**stats, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description="历史密文重加密（ECB → GCM）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只统计，不写库")
    mode.add_argument("--apply", action="store_true", help="实际重写并提交")
    args = parser.parse_args()

    result = asyncio.run(rotate(dry_run=args.dry_run))
    print(f"{'[dry-run] ' if args.dry_run else '[apply] '}"
          f"ai_configs={result['ai_configs']} third_party={result['third_party']} "
          f"skipped={result['skipped']} failed={result['failed']}")
    if result["failures"]:
        print("以下行解密失败（保持原值，需人工处理）：")
        for item in result["failures"]:
            print("  -", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
