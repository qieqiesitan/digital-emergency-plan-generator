"""W2 XSS 复验：注入 payload 到章节 → 打开导出预览 → 断言脚本未执行（一次性脚本）。"""
import json

from playwright.sync_api import sync_playwright

BASE = "http://172.26.0.3:5173"
PLAN = "aa8244ab-ff8f-45a4-8814-15629041095f"
U, P = "qa_e2e_test@test.com", "test123456"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
    page.goto(BASE + "/login", wait_until="load", timeout=40000)
    page.fill('input[id*="email"]', U)
    page.fill('input[type="password"]', P)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    page.goto(BASE + f"/plans/{PLAN}/preview", wait_until="load", timeout=40000)
    page.wait_for_timeout(4000)
    body = page.locator("body").inner_text()
    out = {
        "url": page.url,
        "xss_executed": page.evaluate("() => window.__xss === 1"),
        "marker_visible": "XSSPROBE" in body,
        "body_text_len": len(body),
    }
    page.screenshot(path="/app/exports/xss-after.png", full_page=True)
    b.close()

print(json.dumps(out, ensure_ascii=False))
