"""诊断：/settings/regulations 实际渲染成什么（URL、正文、console）。"""
import os

from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_BASE", "http://host.docker.internal:8082")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
    msgs: list[str] = []
    page.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:160]}"))
    page.on("pageerror", lambda e: msgs.append(f"pageerror: {str(e)[:160]}"))

    page.goto(f"{APP}/login", wait_until="load", timeout=60000)
    page.wait_for_timeout(1500)
    page.fill('input[id*="email"]', "qa_e2e_test@test.com")
    page.fill('input[type="password"]', "test123456")
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    page.goto(f"{APP}/settings/regulations", wait_until="load", timeout=60000)
    page.wait_for_timeout(4000)
    print("URL =", page.url)
    print("正文 =", " ".join(page.locator("body").inner_text().split())[:300])
    print("输入框数 =", page.locator("input").count(), " 表格行数 =", page.locator("tr").count())
    page.screenshot(path="/app/exports/_preview/regulations-page-diag.png", full_page=False)
    print(f"console {len(msgs)} 条：")
    for m in msgs[:6]:
        print("   !!", m)
    browser.close()
