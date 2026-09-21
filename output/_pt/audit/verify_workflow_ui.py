"""真浏览器验证：预案页「生成并复核」按钮 → 弹窗停在确认门控（零 AI，不点确认）。"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_BASE", "http://host.docker.internal:8082")
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
OUT = "/app/exports/_preview"
rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:36s} {detail}", flush=True)


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
    errs: list[str] = []
    page.on("console", lambda m: errs.append(f"{m.type}: {m.text[:160]}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:160]}"))

    page.goto(f"{APP}/login", wait_until="load", timeout=60000)
    page.wait_for_timeout(1500)
    page.fill('input[id*="email"]', "qa_e2e_test@test.com")
    page.fill('input[type="password"]', "test123456")
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)

    page.goto(f"{APP}/plans/{PLAN}/edit", wait_until="load", timeout=60000)
    page.wait_for_timeout(3000)
    btn = page.get_by_role("button", name=re.compile(r"生成并复核"))
    rec("预案页出现「生成并复核」按钮", btn.count() > 0, f"{btn.count()} 个")
    if btn.count() > 0:
        btn.first.click()
        page.wait_for_timeout(4000)
        modal = page.locator("[role=dialog]").first.inner_text()
        rec("弹窗显示两个步骤", "生成正文" in modal and "质量复核" in modal)
        rec("停在确认门控", "等待你确认" in modal, modal[:120].replace("\n", " "))
        ok_btn = page.get_by_role("button", name=re.compile(r"确认并开始生成"))
        rec("出现确认按钮（未自动开工）", ok_btn.count() > 0)
        page.screenshot(path=os.path.join(OUT, "plan-generate-review-ui.png"), full_page=False)
    rec("无 console/pageerror", not errs, f"{len(errs)} 条")
    for e in errs[:4]:
        print("   !!", e)
    browser.close()

bad = [r for r in rows if not r[1]]
print(f"\n==== 生成并复核 UI：{len(rows)} 项，失败 {len(bad)}")
sys.exit(1 if bad else 0)
