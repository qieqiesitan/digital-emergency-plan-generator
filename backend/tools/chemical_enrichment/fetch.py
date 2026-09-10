"""带磁盘缓存 / 限速 / 重试的 HTTP 抓取客户端（缓存命中即断点续跑）。"""
import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class CachedFetcher:
    def __init__(self, cache_dir, delay: float = 0.3, retries: int = 3, get=None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.retries = retries
        self._get = get or self._requests_get
        self._last_call = 0.0

    def _requests_get(self, url: str):
        return requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})

    @staticmethod
    def _decode(resp) -> str:
        """按 UTF-8 解码响应字节。

        ChemBlink / PubChem 页面为 UTF-8，但响应头不带 charset 时 requests 会猜成
        latin-1，导致中文变成乱码；这里统一用字节解码，失败再回退 requests 的推断。
        """
        content = getattr(resp, "content", None)
        if content:
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return resp.text
        return resp.text

    def _cache_path(self, url: str) -> Path:
        host = urlparse(url).netloc.replace(":", "_")
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{host}__{digest}.txt"

    def text(self, url: str, refresh: bool = False) -> str:
        path = self._cache_path(url)
        if path.exists() and not refresh:
            return path.read_text(encoding="utf-8")
        last_error = None
        for _ in range(self.retries):
            wait = self.delay - (time.time() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()
            try:
                resp = self._get(url)
            except Exception as exc:  # 网络异常同样重试
                last_error = exc
                continue
            if resp.status_code == 200:
                text = self._decode(resp)
                path.write_text(text, encoding="utf-8")
                return text
            last_error = RuntimeError(f"HTTP {resp.status_code}: {url}")
            if resp.status_code in (400, 404):
                break  # 资源不存在，无需重试
        raise last_error or RuntimeError(f"fetch failed: {url}")
