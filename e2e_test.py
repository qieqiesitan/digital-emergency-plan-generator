# -*- coding: utf-8 -*-
"""端到端验证"""
from playwright.sync_api import sync_playwright
import time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SAVE = r"C:\Users\55061\Documents\数字化预案自动生成 2\screenshots"
RESULTS = []

def log(msg, ok=True):
    mark = "[OK]" if ok else "[FAIL]"
    print(f"  {mark} {msg}")
    RESULTS.append((ok, msg))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    try:
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.set_default_timeout(20000)

        print("\n[1/5] Login...")
        page.goto("http://localhost:80/login")
        page.wait_for_selector('input[placeholder]', timeout=10000)
        inputs = page.locator('input[placeholder]')
        inputs.nth(0).fill("admin")
        inputs.nth(1).fill("admin123")
        page.locator('button[type="submit"], button.el-button--primary').first.click()
        page.wait_for_url("**/home**", timeout=15000)
        log("Login OK", "/login" not in page.url)
        page.screenshot(path=f"{SAVE}/e2e-01-login.png")

        print("\n[2/5] Find sub-app menu...")
        page.wait_for_selector(".el-menu", timeout=10000)
        time.sleep(2)
        menu_item = page.locator('.el-menu-item, .el-sub-menu__title').filter(has_text="数字化应急")
        count = menu_item.count()
        if count > 0:
            log(f"Found menu item (count={count})", True)
        else:
            all_submenus = page.locator('.el-sub-menu__title')
            for i in range(all_submenus.count()):
                try:
                    all_submenus.nth(i).click()
                    time.sleep(0.5)
                except:
                    pass
            menu_item = page.locator('.el-menu-item, .el-sub-menu__title').filter(has_text="数字化应急")
            count = menu_item.count()
            log(f"Found after expand (count={count})", count > 0)
        page.screenshot(path=f"{SAVE}/e2e-02-sidebar.png")

        if count > 0:
            print("\n[3/5] Click sub-app...")
            menu_item.first.click()
            time.sleep(5)

            subapp_container = page.locator('.sub-app-container, [id^="qiankun-"]')
            container_ok = subapp_container.count() > 0
            log("Sub-app container exists", container_ok)
            page.screenshot(path=f"{SAVE}/e2e-03-loaded.png")

            print("\n[4/5] Verify content...")
            page.wait_for_timeout(3000)
            content = page.content()
            has_content = "dashboard" in content.lower() or "工作台" in content or "预案" in content
            log("Sub-app has content", has_content)
            page.screenshot(path=f"{SAVE}/e2e-04-content.png")

            print("\n[5/5] Check console...")
            console_msgs = []
            page.on("console", lambda msg: console_msgs.append(msg.text))
            page.wait_for_timeout(2000)
            ywt_msgs = [m for m in console_msgs if any(k in m.lower() for k in ["ywt","emergency-plan","bootstrap","mount"])]
            for m in ywt_msgs[:5]:
                print(f"     console: {m[:150]}")
            log(f"YWT logs found ({len(ywt_msgs)})", len(ywt_msgs) > 0)
        else:
            log("Menu not found - skip", False)

        page.screenshot(path=f"{SAVE}/e2e-final.png")

        print("\n" + "="*50)
        passed = sum(1 for ok,_ in RESULTS if ok)
        total = len(RESULTS)
        print(f"  Results: {passed}/{total} passed")
        for ok, msg in RESULTS:
            mark = "[OK]" if ok else "[FAIL]"
            print(f"  {mark} {msg}")
    finally:
        browser.close()
