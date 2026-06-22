# -*- coding: utf-8 -*-
"""E2E: Risk Source & Resource AI + Import test"""
import sys, io, os
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://localhost:5173"
# Use a path without Chinese chars for screenshots
DIR = Path(os.path.expanduser(r"~\Documents\screenshots"))
DIR.mkdir(parents=True, exist_ok=True)

console_errors = []
api_errors = []
results = []

def ok(step, passed, detail=""):
    results.append((step, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {step} {'(' + detail + ')' if detail else ''}")

def on_console(msg):
    if msg.type == "error":
        console_errors.append(msg.text)

def on_req_failed(req):
    if req.failure:
        api_errors.append(f"{req.url} -> {req.failure}")

def on_resp(resp):
    if resp.status >= 400:
        api_errors.append(f"[{resp.status}] {resp.url}")

def ss(page, name):
    page.screenshot(path=str(DIR / f"{name}.png"), full_page=True)

def click_btn(page, text, wait=1000):
    try:
        btn = page.locator(f'button:has-text("{text}"):visible')
        if btn.count() == 0:
            btn = page.locator(f'button:has-text("{text}")')
        if btn.count() > 0:
            btn.first.click(timeout=5000)
            page.wait_for_timeout(wait)
            return True
    except Exception as e:
        print(f"    click_btn({text}) err: {str(e)[:150]}")
    return False

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()
    page.set_default_timeout(10000)
    page.on("console", on_console)
    page.on("requestfailed", on_req_failed)
    page.on("response", on_resp)

    # ---- Login ----
    print("STEP 1: Login")
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.wait_for_selector("#login_email", timeout=10000)
    page.wait_for_timeout(500)

    page.locator("#login_email").fill("550614706@qq.com")
    page.locator("#login_password").fill("cl12345678")
    page.locator('button[type="submit"]').first.click()
    page.wait_for_timeout(3000)

    try:
        page.wait_for_url(f"{BASE}/dashboard", timeout=10000)
        ok("Login", True)
    except:
        ok("Login", False, page.url)
        ss(page, "login-fail")
        browser.close()
        sys.exit(1)

    ss(page, "01-dashboard")

    # ---- Enterprise Detail ----
    print("STEP 2: Enterprise Detail")
    page.goto(f"{BASE}/enterprises", wait_until="networkidle")
    page.wait_for_timeout(1000)

    link = page.locator("table tbody tr td a").first
    if link.count() == 0:
        link = page.locator(".ant-table-row a").first
    if link.count() == 0:
        ok("Enterprise", False, "No records")
        ss(page, "no-enterprise")
        browser.close()
        sys.exit(1)

    link.click()
    page.wait_for_timeout(2000)
    ok("Enterprise Detail", True)
    ss(page, "02-detail")

    # ---- Risk Source: AI ----
    print("STEP 3: Risk Source AI Generate")
    page.locator('.ant-tabs-tab:has-text("风险源")').first.click()
    page.wait_for_timeout(2000)
    ok("Risk tab", True)

    if click_btn(page, "AI智能生成"):
        title = page.locator('.ant-modal:visible .ant-modal-title').text_content() or ""
        ok("Risk AI Modal", True, title)
        ss(page, "03a-risk-ai")
        page.locator('.ant-modal-close').first.click()
        page.wait_for_timeout(500)
        ok("Risk AI close", True)
    else:
        ok("Risk AI Modal", False)

    # ---- Risk Source: Import ----
    print("STEP 4: Risk Source Import")
    page.wait_for_timeout(500)
    if click_btn(page, "导入Excel"):
        title = page.locator('.ant-modal:visible .ant-modal-title').last.text_content() or ""
        ok("Risk Import Modal", True, title)
        ss(page, "04a-risk-import")
        page.locator('.ant-modal-close').last.click()
        page.wait_for_timeout(500)
        ok("Risk Import close", True)
    else:
        ok("Risk Import Modal", False)

    # ---- Resource: AI ----
    print("STEP 5: Resource AI Generate")
    page.wait_for_timeout(500)
    page.locator('.ant-tabs-tab:has-text("应急资源")').first.click()
    page.wait_for_timeout(2000)
    ok("Resource tab", True)
    ss(page, "05-resource-tab")

    page.wait_for_timeout(500)
    if click_btn(page, "AI智能生成"):
        title = page.locator('.ant-modal:visible .ant-modal-title').last.text_content() or ""
        ok("Resource AI Modal", True, title)
        ss(page, "06a-resource-ai")
        page.locator('.ant-modal-close').last.click()
        page.wait_for_timeout(500)
        ok("Resource AI close", True)
    else:
        ok("Resource AI Modal", False)

    # ---- Resource: Import ----
    print("STEP 6: Resource Import")
    page.wait_for_timeout(500)
    if click_btn(page, "导入Excel"):
        title = page.locator('.ant-modal:visible .ant-modal-title').last.text_content() or ""
        ok("Resource Import Modal", True, title)
        ss(page, "07a-resource-import")
        page.locator('.ant-modal-close').last.click()
        page.wait_for_timeout(500)
        ok("Resource Import close", True)
    else:
        ok("Resource Import Modal", False)

    # ---- Report ----
    print("\n" + "=" * 50)
    print("FINAL REPORT")
    print("=" * 50)
    passed = sum(1 for r in results if r[1])
    total = len(results)
    print(f"  {passed}/{total} passed, {total - passed} failed")
    for s, p, d in results:
        print(f"  [{'PASS' if p else 'FAIL'}] {s} {d}")

    filtered_console = [e for e in console_errors
                        if "401" not in e and "deprecated" not in e.lower()
                        and "will be removed" not in e.lower()]
    if filtered_console:
        print(f"\n** REAL CONSOLE ERRORS ({len(filtered_console)}):")
        for e in filtered_console:
            print(f"  {e[:200]}")
    else:
        print("\n** Console: clean (only pre-auth 401 + antd deprecation)")

    filtered_api = [e for e in api_errors if "401" not in e]
    if filtered_api:
        print(f"\n** API ERRORS ({len(filtered_api)}):")
        for e in filtered_api:
            print(f"  {e[:200]}")

    ss(page, "99-final")
    browser.close()
    print("\nDone.")
