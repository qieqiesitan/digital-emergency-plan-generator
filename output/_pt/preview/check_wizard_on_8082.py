"""在验收产物（8082 静态站）上确认：排查计划页有「AI 智能引导」入口，且弹窗能打开（不点生成 → 零额度）。"""
import sys

from playwright.sync_api import sync_playwright

BASE = "http://host.docker.internal:8082"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
OUT = "/app/exports/_preview"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
    errs: list[str] = []
    page.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:160]}"))
    page.goto(f"{BASE}/login", wait_until="load", timeout=45000)
    page.wait_for_timeout(1500)
    page.fill('input[id*="email"]', "qa_e2e_test@test.com")
    page.fill('input[type="password"]', "test123456")
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    page.goto(f"{BASE}/enterprises/{ENT}/hazard/plans", wait_until="load", timeout=45000)
    page.wait_for_timeout(2500)
    btn = page.get_by_role("button", name="AI 智能引导")
    has_btn = btn.count() > 0
    print(f"{'OK ' if has_btn else '!! '}8082 排查计划页「AI 智能引导」按钮存在：{has_btn}")
    if has_btn:
        btn.click()
        page.wait_for_timeout(900)
        body = page.locator("body").inner_text()
        opened = "填写基础信息" in body and "生成建议" in body
        print(f"{'OK ' if opened else '!! '}弹窗能打开且停在第一步（未调用 AI）：{opened}")
        page.screenshot(path=f"{OUT}/wizard-8082-entry.png", full_page=True)
    print(f"console/pageerror：{len(errs)} 条")
    for e in errs[:4]:
        print(f"   !! {e}")
    browser.close()
sys.exit(0 if has_btn else 1)
