"""移动端登录失败定位（一次性脚本）。"""
import json
import os
import time

from playwright.sync_api import sync_playwright

BASE = "http://shuzihuayuan:8080"
OUT = "/app/exports/e2e-20260917"
U, P = "qa_e2e_test@test.com", "test123456"
MOBILE = {"width": 390, "height": 844}
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = browser.new_context(viewport=MOBILE, device_scale_factor=3, is_mobile=True,
                              has_touch=True, locale="zh-CN", user_agent=UA)
    page = ctx.new_page()
    log = {"console": [], "http": [], "failed": []}
    page.on("console", lambda m: log["console"].append(f"{m.type}: {m.text[:200]}"))
    page.on("response", lambda r: log["http"].append(f"{r.status} {r.request.method} {r.url[:140]}")
            if "/api/" in r.url else None)
    page.on("requestfailed", lambda r: log["failed"].append(f"{r.method} {r.url[:140]} <- {r.failure}"))
    page.goto(BASE + "/m/login", wait_until="load", timeout=30000)
    page.wait_for_timeout(1500)
    page.fill('input[type="email"]', U)
    page.fill('input[type="password"]', P)
    page.wait_for_timeout(300)
    log["email_value"] = page.input_value('input[type="email"]')
    log["password_len"] = len(page.input_value('input[type="password"]'))
    log["buttons"] = page.eval_on_selector_all(
        "button", "els => els.map(e => ({text: (e.innerText || '').trim().slice(0, 20), disabled: e.disabled}))")
    page.locator('button:has-text("登录")').last.click()
    page.wait_for_timeout(6000)
    log["url_after"] = page.url
    log["toast_text"] = page.locator("body").inner_text()[:400]
    log["storage"] = page.evaluate(
        "() => Object.fromEntries(Object.keys(localStorage).map(k => [k, (localStorage.getItem(k) || '').slice(0, 12)]))")
    page.screenshot(path=os.path.join(OUT, "debug-mobile-login.png"), full_page=True)
    browser.close()

print(json.dumps(log, ensure_ascii=False, indent=1))
