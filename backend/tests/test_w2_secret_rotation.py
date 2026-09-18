"""W2：密钥加密硬化（AES-GCM 新格式 + 历史 ECB 兼容 + 轮换支持）。"""

import base64

import pytest

from app import config as config_module
from app.services import secret_utils
from app.services.secret_utils import (
    GCM_PREFIX,
    decrypt_secret,
    encrypt_secret,
    legacy_ecb_encrypt,
    needs_rotation,
)

OLD_KEY = "abcdefghijklmnopqrstuvwxyz123456"
NEW_KEY = "N" * 32


def _use_keys(monkeypatch, primary: str, legacy: str = ""):
    monkeypatch.setattr(secret_utils.settings, "ENCRYPTION_KEY", primary)
    monkeypatch.setattr(secret_utils.settings, "ENCRYPTION_KEY_LEGACY", legacy)


def test_new_ciphertext_is_gcm_and_nondeterministic(monkeypatch):
    _use_keys(monkeypatch, NEW_KEY)
    first = encrypt_secret("sk-test")
    second = encrypt_secret("sk-test")
    assert first.startswith(GCM_PREFIX) and second.startswith(GCM_PREFIX)
    assert first != second, "同一明文两次加密必须不同（随机 nonce）"
    assert decrypt_secret(first) == "sk-test"


def test_legacy_ecb_ciphertext_still_decrypts(monkeypatch):
    """升级不能解不开存量密文：旧 ECB hex 仍走兼容路径。"""
    _use_keys(monkeypatch, OLD_KEY)
    legacy_ct = legacy_ecb_encrypt("Bearer old-key", OLD_KEY)
    assert not legacy_ct.startswith(GCM_PREFIX)
    assert needs_rotation(legacy_ct) is True
    assert decrypt_secret(legacy_ct) == "Bearer old-key"


def test_rotation_window_reads_both_keys(monkeypatch):
    """轮换窗口：主密钥=新，旧密钥在 LEGACY 列表里，新旧密文都能读。"""
    _use_keys(monkeypatch, OLD_KEY)
    legacy_ct = legacy_ecb_encrypt("old-secret", OLD_KEY)

    _use_keys(monkeypatch, NEW_KEY, legacy=OLD_KEY)
    assert decrypt_secret(legacy_ct) == "old-secret"
    fresh = encrypt_secret("new-secret")
    assert fresh.startswith(GCM_PREFIX)
    assert decrypt_secret(fresh) == "new-secret"


def test_tampered_gcm_ciphertext_is_rejected(monkeypatch):
    _use_keys(monkeypatch, NEW_KEY)
    blob = base64.b64decode(encrypt_secret("sk-test")[len(GCM_PREFIX):])
    tampered = bytearray(blob)
    tampered[-1] ^= 0xFF
    bad = GCM_PREFIX + base64.b64encode(bytes(tampered)).decode()
    with pytest.raises(Exception, match="重新配置"):
        decrypt_secret(bad)


def test_needs_rotation_flags_only_legacy(monkeypatch):
    _use_keys(monkeypatch, NEW_KEY)
    assert needs_rotation(encrypt_secret("x")) is False
    assert needs_rotation("abcd1234") is True
    assert needs_rotation("") is False


def test_default_encryption_keys_are_flagged_as_known_weak():
    assert OLD_KEY in config_module.KNOWN_DEFAULT_ENCRYPTION_KEYS
    assert "a" * 32 in config_module.KNOWN_DEFAULT_ENCRYPTION_KEYS
