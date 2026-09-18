"""外部文件下载的 SSRF / 体积防护（2026-09-18 审计修复）。"""

import pytest

from app.services.external_file_store import (
    ExternalDownloadBlocked,
    assert_url_allowed,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/api/v1/enterprises",
        "http://localhost/x",
        "http://169.254.169.254/latest/meta-data/",      # 云元数据
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://0.0.0.0/",
        "file:///etc/passwd",
        "ftp://example.com/a.pdf",
        "http://[::ffff:10.0.0.1]/",                      # IPv4-mapped 内网
    ],
)
def test_assert_url_allowed_rejects_unsafe_targets(url):
    with pytest.raises(ExternalDownloadBlocked):
        assert_url_allowed(url)


def test_assert_url_allowed_rejects_empty_host():
    with pytest.raises(ExternalDownloadBlocked):
        assert_url_allowed("http:///no-host")


def test_assert_url_allowed_accepts_public_https(monkeypatch):
    """公网 https 地址应通过（解析结果用假公网 IP，避免依赖外网 DNS）。"""
    import app.services.external_file_store as store

    def fake_getaddrinfo(host, port, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(store.socket, "getaddrinfo", fake_getaddrinfo)
    assert_url_allowed("https://example.com/a.pdf")  # 不抛异常即通过


def test_allowed_hosts_whitelist_blocks_others(monkeypatch):
    import app.services.external_file_store as store

    monkeypatch.setattr(store, "_ALLOWED_HOSTS", {"files.partner.com"})
    with pytest.raises(ExternalDownloadBlocked):
        assert_url_allowed("https://evil.example.com/a.pdf")
