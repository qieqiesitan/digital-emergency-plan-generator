"""诊断：打印版本页上所有按钮的可见文案、aria-label、禁用态。"""
import os

from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_BASE", "http://host.docker.internal:8082")
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
    page.goto(f"{APP}/login", wait_until="load", timeout=60000)
    page.wait_for_timeout(1500)
    page.fill('input[id*="email"]', "qa_e2e_test@test.com")
    page.fill('input[type="password"]', "test123456")
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    page.goto(f"{APP}/plans/{PLAN}/versions", wait_until="load", timeout=60000)
    page.wait_for_timeout(3000)
    body = page.locator("body").inner_text()
    print("页面文本片段：", " ".join(body.split())[:200])
    count = page.locator("button").count()
    print(f"按钮数：{count}")
    for i in range(min(count, 12)):
        b = page.locator("button").nth(i)
        txt = (b.inner_text() or "").strip()
        print(f"  [{i}] text={txt!r} disabled={b.is_disabled()} aria={b.get_attribute('aria-label')!r}")
    browser.close()
