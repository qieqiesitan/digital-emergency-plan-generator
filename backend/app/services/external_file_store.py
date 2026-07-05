"""从外部 URL 下载文件到本地 uploads 目录"""
import os, uuid, logging, httpx
from urllib.parse import urlparse

logger = logging.getLogger("external_file_store")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def download_external_file(url: str, name: str | None = None) -> dict | None:
    """下载外部文件到本地，返回 {name, path, type, size} 或 None"""
    try:
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1] or ".bin"
        safe_name = f"ext_{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_DIR, safe_name)

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            with open(file_path, "wb") as f:
                f.write(resp.content)

        return {
            "name": name or os.path.basename(parsed.path) or safe_name,
            "path": file_path,
            "type": ext.lstrip("."),
            "size": len(resp.content),
        }
    except Exception as e:
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
