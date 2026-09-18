"""从外部 URL 下载文件到本地 uploads 目录。

2026-09-18 审计加固（外部系统传入的 url 属于不可信输入）：

- **SSRF 防护**：仅允许 http/https；解析主机名的全部 IP，任一落在内网/回环/链路本地/
  保留/组播/未指定网段即拒绝（挡掉云元数据 169.254.169.254、localhost、内网服务）；
  需要更严时可设 ``EXTERNAL_DOWNLOAD_ALLOWED_HOSTS`` 白名单（逗号分隔）。
- **逐跳校验重定向**：不再一次 follow_redirects=True，最多 3 跳且每跳都重新校验地址。
- **体积上限**：流式落盘，超过 50MB 立即中断（此前 `resp.content` 会把整文件读进内存）。
"""
import ipaddress
import logging
import os
import socket
import uuid
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger("external_file_store")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_REDIRECTS = 3
_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_HOSTS = {
    h.strip().lower()
    for h in os.environ.get("EXTERNAL_DOWNLOAD_ALLOWED_HOSTS", "").split(",")
    if h.strip()
}


class ExternalDownloadBlocked(Exception):
    """URL 被安全策略拒绝（协议不支持 / 非公网地址 / 白名单外）。"""


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_url_allowed(url: str) -> None:
    """校验外部下载地址；不允许时抛 ExternalDownloadBlocked。"""
    parsed = urlparse(url or "")
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ExternalDownloadBlocked(f"仅允许 http/https，收到 {scheme or '空'} 协议")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ExternalDownloadBlocked("URL 缺少主机名")
    if _ALLOWED_HOSTS and host not in _ALLOWED_HOSTS:
        raise ExternalDownloadBlocked(f"目标主机不在白名单：{host}")
    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise ExternalDownloadBlocked(f"域名解析失败：{host}（{exc}）") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _ip_is_blocked(ip):
            raise ExternalDownloadBlocked(f"目标地址 {ip} 属内网/保留网段，已拒绝")


async def _stream_to_file(url: str, file_path: str, max_bytes: int) -> int:
    """流式下载到文件，逐跳校验重定向；返回实际字节数。"""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        assert_url_allowed(current)
        async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
            async with client.stream("GET", current) as resp:
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("location")
                    if not location:
                        raise ExternalDownloadBlocked("重定向响应缺少 Location")
                    current = urljoin(current, location)
                    continue
                resp.raise_for_status()
                total = 0
                with open(file_path, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise ExternalDownloadBlocked(
                                f"文件超过 {max_bytes // (1024 * 1024)}MB 上限"
                            )
                        f.write(chunk)
                return total
    raise ExternalDownloadBlocked("重定向次数过多")


async def download_external_file(
    url: str, name: str | None = None, *, max_bytes: int = MAX_DOWNLOAD_BYTES
) -> dict | None:
    """下载外部文件到本地，返回 {name, path, type, size} 或 None"""
    file_path = ""
    try:
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1] or ".bin"
        safe_name = f"ext_{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_DIR, safe_name)
        size = await _stream_to_file(url, file_path, max_bytes)

        return {
            "name": name or os.path.basename(parsed.path) or safe_name,
            "path": file_path,
            "type": ext.lstrip("."),
            "size": size,
        }
    except Exception as e:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                logger.warning("清理未完成的外部文件失败：%s", file_path)
        logger.error(f"Download failed for {url}: {e}")
        return None


async def download_external_files(documents: list[dict]) -> list[dict]:
    """批量下载外部文件"""
    results = []
    for doc in documents:
        url = doc.get("url", "")
        name = doc.get("name", "")
        if not url:
            continue
        result = await download_external_file(url, name)
        if result:
            result["doc_type"] = doc.get("type", "other")
            results.append(result)
    return results
