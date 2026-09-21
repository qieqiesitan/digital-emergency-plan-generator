"""诊断：点「对比」后到底发生了什么（模态框数量 / console 错误 / 截图）。"""
import os
import re

from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_BASE", "http://host.docker.internal:8082")
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
OUT = "/app/exports/_preview"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
    errs: list[str] = []
    page.on("console", lambda m: errs.append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:200]}"))

    page.goto(f"{APP}/login", wait_until="load", timeout=60000)
    page.wait_for_timeout(1500)
    page.fill('input[id*="email"]', "qa_e2e_test@test.com")
    page.fill('input[type="password"]', "test123456")
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    page.goto(f"{APP}/plans/{PLAN}/versions", wait_until="load", timeout=60000)
    page.wait_for_timeout(3000)

    btn = page.get_by_role("button", name=re.compile(r"对\s*比")).first
    print("对比按钮存在：", btn.count() > 0, "禁用：", btn.is_disabled())
    btn.click()
    page.wait_for_timeout(3000)
    for sel in (".ant-modal", ".ant-modal-content", ".ant-modal-wrap", "[role=dialog]"):
        print(f"{sel} 数量 = {page.locator(sel).count()}")
    print("body 末尾片段：", " ".join(page.locator("body").inner_text().split())[-200:])
    page.screenshot(path=os.path.join(OUT, "compare-modal-diag.png"), full_page=False)
    print(f"console/pageerror {len(errs)} 条：")
    for e in errs[:8]:
        print("   !!", e)
    browser.close()
