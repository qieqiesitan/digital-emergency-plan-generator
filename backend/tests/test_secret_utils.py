import pytest
from app.services.secret_utils import encrypt_secret, decrypt_secret, mask_secret

def test_encrypt_decrypt_roundtrip():
    enc = encrypt_secret("Bearer abc-123")
    assert enc != "Bearer abc-123"
    assert decrypt_secret(enc) == "Bearer abc-123"

def test_mask_secret_keeps_head_tail():
    assert mask_secret("M6cf4mymxeKxHtSlXSXr7EfrA5IwHahRZXSNqVfqxtgv2slL") == "M6cf****slL"

def test_mask_short_secret():
    assert mask_secret("ab") == "****"
