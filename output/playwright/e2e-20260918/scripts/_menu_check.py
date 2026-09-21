"""W2 权限种子复验：普通用户应能进企业管理、不再看到 AI 配置页。"""
import json

from playwright.sync_api import sync_playwright

BASE = "http://172.26.0.3:5173"
U, P = "qa_e2e_test@test.com", "test123456"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
    page.goto(BASE + "/login", wait_until="load", timeout=40000)
    page.fill('input[id*="email"]', U)
    page.fill('input[type="password"]', P)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    sidebar = page.locator("body").inner_text()
    page.goto(BASE + "/enterprises", wait_until="load", timeout=40000)
    page.wait_for_timeout(2500)
    ent_text = page.locator("body").inner_text()
    page.goto(BASE + "/settings/ai-config", wait_until="load", timeout=40000)
    page.wait_for_timeout(2500)
    ai_text = page.locator("body").inner_text()
    print(json.dumps({
        "sidebar_has_enterprise": "企业" in sidebar,
        "enterprises_forbidden": "无权限访问" in ent_text,
        "enterprises_head": ent_text[:80].replace("\n", " "),
        "ai_config_forbidden": "无权限访问" in ai_text,
    }, ensure_ascii=False))
    b.close()
