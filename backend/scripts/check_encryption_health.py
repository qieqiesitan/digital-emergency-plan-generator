"""加密健康检查：统计密文格式分布 + 列出"任何密钥都解不开"的行（2026-09-19 部署工具）。

用途（服务端可直接执行，只读、不写库）：

1. **轮换前**：确认哪些行仍是历史 ECB 密文（需要 `rotate_encryption_key.py --apply`）；
2. **轮换后**：确认 `legacy 待迁移=0`，且没有解不开的行；
3. **日常巡检**：一旦出现 `undecryptable`，说明该行是"历史坏密文"或在轮换中丢了旧密钥 ——
   脚本会打印 **表名/主键/字段**，照着"处理建议"到对应配置页重新保存即可。

用法：
    docker exec -e PYTHONPATH=/app -w /app emergency-plan-backend \
        python /app/scripts/check_encryption_health.py

退出码：0=全部可解（含仍待轮换）；1=存在解不开的密文。
"""

import asyncio
import hashlib
import sys

from sqlalchemy import select

from app.database import async_session
from app.config import settings
from app.models.enterprise import AIConfig
from app.models.third_party_config import ThirdPartyConfig
# FK 目标表注册（否则 flush/mapper 解析缺 users 表）
from app.models.user import User  # noqa: F401
from app.services.secret_utils import GCM_PREFIX, decrypt_secret, mask_secret

# (表名, 定位字段, 密文字段, 处理建议)
SCOPE = [
    ("ai_configs", "id", "api_key_encrypted", "设置 → AI 配置（重新保存该条 API Key）"),
    ("third_party_config", "config_key", "config_value", "设置 → 第三方配置（重新保存该密钥）"),
]


def _classify(stored: str) -> tuple[str, str | None]:
    """返回 (状态, 明文掩码)：gcm / legacy / empty / undecryptable。"""
    if not stored:
        return "empty", None
    if stored.startswith(GCM_PREFIX):
        try:
            return "gcm", mask_secret(decrypt_secret(stored))
        except Exception:  # noqa: BLE001
            return "undecryptable", None
    try:
        return "legacy", mask_secret(decrypt_secret(stored))
    except Exception:  # noqa: BLE001
        return "undecryptable", None


async def check() -> dict:
    # 打印当前生效密钥指纹 + LEGACY 把数：轮换期最常见的误操作是"跑脚本的环境里没有旧密钥"，
    # 指纹能让运维一眼区分"真的坏密文"还是"用错了密钥环境"。
    fingerprint = hashlib.sha256((settings.ENCRYPTION_KEY or "").encode()).hexdigest()[:8]
    legacy_count = len([k for k in (settings.ENCRYPTION_KEY_LEGACY or "").split(",") if k.strip()])
    report: dict = {"counts": {}, "problems": [], "scope": SCOPE,
                    "key_fingerprint": fingerprint, "legacy_keys": legacy_count}
    print(f"==> 生效 ENCRYPTION_KEY 指纹={fingerprint}，ENCRYPTION_KEY_LEGACY 把数={legacy_count}")
    async with async_session() as db:
        rows = []
        for row in (await db.execute(select(AIConfig))).scalars().all():
            rows.append(("ai_configs", str(row.id), "api_key_encrypted", row.api_key_encrypted or ""))
        for row in (await db.execute(
            select(ThirdPartyConfig).where(ThirdPartyConfig.config_type == "secret")
        )).scalars().all():
            rows.append(("third_party_config", str(row.config_key), "config_value", row.config_value or ""))

    for table, pk, field, stored in rows:
        status, masked = _classify(stored)
        report["counts"][status] = report["counts"].get(status, 0) + 1
        print(f"  {table:18s} {pk[:36]:36s} {field:20s} {status:14s} {masked or ''}")
        if status == "undecryptable":
            suggestion = dict((t, s) for t, _, _, s in [(a, b, c, d) for a, b, c, d in SCOPE])[table]
            report["problems"].append({"table": table, "pk": pk, "field": field, "fix": suggestion})
    return report


def main() -> int:
    result = asyncio.run(check())
    counts = result["counts"]
    print("\n==> 密文格式分布：", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "（无密文行）")
    if result["problems"]:
        print("\n!! 以下密文所有可用密钥都解不开（需人工重新保存）：")
        for p in result["problems"]:
            print(f"   - {p['table']} {p['pk']} .{p['field']}  →  {p['fix']}")
        print("\n提示：轮换期间请确认 ENCRYPTION_KEY_LEGACY 仍包含旧密钥；确认无误后按上述建议重存。")
        return 1
    if counts.get("legacy"):
        print(f"\n提示：仍有 {counts['legacy']} 行历史 ECB 密文，可执行 "
              "backend/scripts/rotate_encryption_key.py --dry-run 查看后 --apply 重加密。")
    print("加密健康检查通过 ✅（无解不开的密文）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
