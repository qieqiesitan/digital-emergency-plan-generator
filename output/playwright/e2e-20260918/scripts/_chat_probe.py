"""排查 /m/chat 与 /chat 页面内容极少的原因（是否只是加载态/空态）。"""

import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://host.docker.internal:8082")
U, P = "qa_e2e_test@test.com", "test123456"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def probe(browser, mobile: bool, path: str, wait: int) -> None:
    ctx = (browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                               has_touch=True, locale="zh-CN", user_agent=UA)
           if mobile else browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN"))
    page = ctx.new_page()
    bad = []
    page.on("response", lambda r: bad.append(f"{r.status} {r.request.method} {r.url[:120]}")
            if r.status >= 400 else None)
    page.on("pageerror", lambda e: bad.append(f"pageerror {str(e)[:150]}"))
    page.goto(BASE + ("/m/login" if mobile else "/login"), wait_until="load", timeout=45000)
    page.wait_for_timeout(1200)
    if mobile:
        page.fill('input[placeholder="请输入邮箱"]', U)
        page.fill('input[placeholder="请输入密码"]', P)
        page.locator("button:has-text('登录')").last.click()
    else:
        page.fill('input[id*="email"]', U)
        page.fill('input[type="password"]', P)
        page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    page.goto(BASE + path, wait_until="load", timeout=45000)
    page.wait_for_timeout(wait)
    text = page.locator("body").inner_text()
    html_len = len(page.content())
    print(f"== {path} mobile={mobile} wait={wait}ms")
    print("  text:", repr(text[:400]))
    print("  html_len:", html_len, "url:", page.url)
    print("  4xx/pageerror:", bad[:6])
    page.screenshot(path=f"/app/exports/e2e-20260918/b1-chat-probe-{path.strip('/').replace('/', '-')}.png",
                    full_page=False)
    ctx.close()


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    probe(b, True, "/m/chat", 6000)
    probe(b, False, "/chat", 6000)
    b.close()
