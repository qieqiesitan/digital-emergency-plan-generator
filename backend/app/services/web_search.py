"""Bing cn search - rate-limited, backed by Scrapling for adaptive parsing."""
import logging, threading, time

from scrapling import Fetcher

logger = logging.getLogger("web_search")

MIN_INTERVAL = 2.0  # seconds between requests


class BingSearch:
    """Thread-safe Bing cn search with built-in rate limiting.

    Uses Scrapling for HTML parsing -- auto-adapts when Bing changes page structure.
    """

    def __init__(self, min_interval: float = MIN_INTERVAL):
        self._min_interval = min_interval
        self._last_call = 0.0
        self._lock = threading.Lock()

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search cn.bing.com, return list of {title, url, snippet}.

        Blocks automatically if called faster than min_interval.
        Returns empty list when max_results <= 0.
        """
        if max_results <= 0:
            return []

        with self._lock:
            elapsed = time.time() - self._last_call
            if elapsed < self._min_interval:
                wait = self._min_interval - elapsed
                logger.debug("web_search: rate-limiting, sleeping %.1fs", wait)
                time.sleep(wait)

            try:
                results = _do_search(query, max_results)
            except Exception:
                logger.exception("web_search: search failed for query=%r", query)
                results = []
            finally:
                self._last_call = time.time()
        return results


def _do_search(query: str, max_results: int) -> list[dict]:
    import urllib.parse

    q = urllib.parse.quote(query)
    url = f"https://cn.bing.com/search?q={q}&count={max_results}"
    d = Fetcher.get(url)

    results: list[dict] = []
    for item in d.css("li.b_algo"):
        title_el = item.css("h2 a")
        snippet_el = item.css(".b_caption p")
        if not title_el:
            continue

        href = (title_el[0].attrib or {}).get("href", "")
        title = (title_el[0].text or "").strip()
        snippet = (snippet_el[0].text or "").strip()[:200] if snippet_el else ""

        if title and href and "bing.com" not in href:
            results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results
