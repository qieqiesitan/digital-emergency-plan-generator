"""公开链接（扫码上报/公示）在手机 UA 下是否可达（只读，一次性）。

对照：同一 URL 在桌面 UA 下 vs iPhone UA 下的最终落地页。
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("MOBILE_BASE", "http://localhost:8082")
OUT = os.environ.get("PROBE_OUT", "output/playwright/e2e-20260920")
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
PATHS = ["/h/report/FAKE_TOKEN", "/h/FAKE_TOKEN", "/r/FAKE_TOKEN", "/p/risk/FAKE_TOKEN"]


def run(pw, ua: str, label: str) -> list:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844} if "iPhone" in ua else {"width": 1440, "height": 900},
        is_mobile="iPhone" in ua,
        has_touch="iPhone" in ua,
        locale="zh-CN",
        user_agent=ua,
    )
    page = ctx.new_page()
    rows = []
    for path in PATHS:
        page.goto(BASE + path, wait_until="load", timeout=30000)
        page.wait_for_timeout(2500)
        text = page.locator("body").inner_text().replace("\n", " | ")[:120]
        rows.append({"ua": label, "path": path, "final_url": page.url.replace(BASE, ""), "text": text})
    browser.close()
    return rows


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        rows = run(pw, UA_MOBILE, "iPhone") + run(pw, UA_DESKTOP, "Desktop")
    with open(os.path.join(OUT, "mobile-public-link.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    for r in rows:
        print(f"[{r['ua']}] {r['path']} -> {r['final_url']}  :: {r['text']}")


if __name__ == "__main__":
    main()
