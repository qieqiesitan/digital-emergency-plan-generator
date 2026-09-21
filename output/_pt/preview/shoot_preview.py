"""给"智能引导预演 + 4 个无引用文件"的临时预览页截图。"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("PREVIEW_BASE", "http://127.0.0.1:8099")
OUT = os.environ.get("PREVIEW_OUT", "/app/exports/_preview")
os.makedirs(OUT, exist_ok=True)

JOBS = [
    ("desktop", "/src/preview-desktop.html", 1500, 1000, 1500, "wizard-and-risk-source-form.png"),
    ("mobile", "/src/preview-mobile.html", 1400, 1000, 3200, "mobile-three-files.png"),
]

bad = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    for label, path, w, h, wait_ms, png in JOBS:
        page = browser.new_page(viewport={"width": w, "height": h}, locale="zh-CN")
        errs: list[str] = []
        page.on("console", lambda m, e=errs: e.append(f"{m.type}: {m.text[:220]}") if m.type == "error" else None)
        page.on("pageerror", lambda exc, e=errs: e.append(f"pageerror: {str(exc)[:220]}"))
        page.goto(BASE + path, wait_until="load", timeout=60000)
        page.wait_for_timeout(wait_ms)
        page.screenshot(path=os.path.join(OUT, png), full_page=True)
        text = page.locator("body").inner_text()
        print(f"{label}: {len(text)} 字 · console/pageerror {len(errs)} 条 → {png}")
        for e in errs[:6]:
            print(f"   !! {e}")
        bad.extend(errs)
        page.close()
    browser.close()

sys.exit(1 if bad else 0)
