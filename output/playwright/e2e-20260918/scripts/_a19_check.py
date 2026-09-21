"""A19 复验：隐患驾驶舱统计卡不应再出现"条条/个个"（一次性脚本）。"""
import re

from playwright.sync_api import sync_playwright

BASE = "http://172.26.0.3:5173"
ENT = "e62bb772-a29f-4e48-89a4-9182f13ca86f"
U, P = "qa_e2e_test@test.com", "test123456"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
    page.goto(BASE + "/login", wait_until="load", timeout=40000)
    page.fill('input[id*="email"]', U)
    page.fill('input[type="password"]', P)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    page.goto(BASE + f"/enterprises/{ENT}/hazard/dashboard", wait_until="load", timeout=40000)
    page.wait_for_timeout(3500)
    txt = page.locator("body").inner_text()
    dup = re.findall(r"条\s*条|个\s*个", txt)
    single = re.findall(r"未闭环隐患\s*\n?\s*(\d+条)", txt)
    print("重复单位命中:", dup[:5])
    print("单单位样本:", single[:3])
    page.screenshot(path="/app/exports/a19-after.png", full_page=True)
    b.close()
