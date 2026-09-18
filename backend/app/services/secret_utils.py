"""Secret encryption / masking utilities shared across config storage.

W2 加密硬化：
- 新密文用 `AES-256-GCM`（随机 nonce + 认证标签），格式 `gcm$<base64(nonce|ct|tag)>`；
- 历史 AES-ECB 密文（纯 hex）在轮换完成前仍可解密，保证现有部署不停机；
- `ENCRYPTION_KEY_LEGACY` 支持轮换期"新密钥写、新旧密钥都能读"。

注意：旧 ECB 方案没有 IV、无认证，同一明文密文相同；它只作为兼容路径存在，
`backend/scripts/rotate_encryption_key.py` 可把存量密文批量迁移到 GCM。
"""

import base64
import logging
import os

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from app.config import settings

logger = logging.getLogger(__name__)

GCM_PREFIX = "gcm$"
GCM_NONCE_BYTES = 12


def _key_bytes(key: str) -> bytes:
    """历史密钥派生方式（前 32 字节、不足补 0），保证旧密文可解。"""
    return key.encode()[:32].ljust(32, b"\0")


def _decrypt_keys() -> list[bytes]:
    """可解密密钥集合：当前主密钥 +（可选）轮换期旧密钥。"""
    keys = [_key_bytes(settings.ENCRYPTION_KEY)]
    for raw in (settings.ENCRYPTION_KEY_LEGACY or "").split(","):
        raw = raw.strip()
        if raw and raw != settings.ENCRYPTION_KEY:
            keys.append(_key_bytes(raw))
    return keys


def encrypt_secret(plain: str) -> str:
    """用主密钥加密，返回带版本前缀的密文（新格式一律 GCM）。"""
    nonce = os.urandom(GCM_NONCE_BYTES)
    cipher = AES.new(_key_bytes(settings.ENCRYPTION_KEY), AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plain.encode())
    return GCM_PREFIX + base64.b64encode(nonce + ciphertext + tag).decode()


def decrypt_secret(stored: str) -> str:
    """解密（GCM 新格式 + 历史 ECB 格式），失败统一抛友好文案。"""
    try:
        if (stored or "").startswith(GCM_PREFIX):
            blob = base64.b64decode(stored[len(GCM_PREFIX):])
            nonce = blob[:GCM_NONCE_BYTES]
            tag = blob[-16:]
            ciphertext = blob[GCM_NONCE_BYTES:-16]
            for key in _decrypt_keys():
                try:
                    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                    return cipher.decrypt_and_verify(ciphertext, tag).decode()
                except Exception:  # noqa: BLE001 - 换下一把密钥
                    continue
            raise ValueError("GCM 解密失败（密钥不匹配或密文被篡改）")
        # 历史格式：AES-ECB + hex
        raw = bytes.fromhex(stored)
        for key in _decrypt_keys():
            try:
                cipher = AES.new(key, AES.MODE_ECB)
                return unpad(cipher.decrypt(raw), 16).decode()
            except Exception:  # noqa: BLE001
                continue
        raise ValueError("旧格式解密失败（密钥不匹配）")
    except Exception:
        raise Exception("配置解密失败，请重新配置")


def needs_rotation(stored: str) -> bool:
    """该密文是否仍是历史 ECB 格式（需要重加密）。"""
    return bool(stored) and not stored.startswith(GCM_PREFIX)


def legacy_ecb_encrypt(plain: str, key: str) -> str:
    """仅用于测试/迁移校验：按历史算法生成旧格式密文。"""
    cipher = AES.new(_key_bytes(key), AES.MODE_ECB)
    return cipher.encrypt(pad(plain.encode(), 16)).hex()


def mask_secret(value: str) -> str:
    """Mask a secret for display.

    Values longer than 8 chars keep the first 4 and last 3 chars with a
    ``****`` separator; anything else is fully masked.
    """
    if not value:
        return "****"
    if len(value) > 8:
        return f"{value[:4]}****{value[-3:]}"
    return "****"
