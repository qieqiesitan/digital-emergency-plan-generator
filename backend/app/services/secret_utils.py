"""Secret encryption / masking utilities shared across config storage.

Encryption intentionally mirrors the scheme previously implemented in
``app.services.llm_client.decrypt_api_key`` (AES-128/ECB derived from
``ENCRYPTION_KEY`` with PKCS7 padding), so ciphertexts stored in existing
``ai_configs`` rows remain decryptable.
"""

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from app.config import settings


def _derive_key() -> bytes:
    return settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b"\0")


def encrypt_secret(plain: str) -> str:
    """Encrypt a plaintext secret and return it as hex."""
    cipher = AES.new(_derive_key(), AES.MODE_ECB)
    return cipher.encrypt(pad(plain.encode(), 16)).hex()


def decrypt_secret(hex_str: str) -> str:
    """Decrypt a hex-encoded secret back to plaintext."""
    try:
        cipher = AES.new(_derive_key(), AES.MODE_ECB)
        return unpad(cipher.decrypt(bytes.fromhex(hex_str)), 16).decode()
    except Exception:
        raise Exception("AI Key解密失败，请前往 设置→AI配置 重新输入API Key保存后重试")


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
