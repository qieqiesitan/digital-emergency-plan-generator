"""真浏览器验证：法规详情弹窗里的「法规体系链」（零 AI）。"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_BASE", "http://host.docker.internal:8082")
OUT = "/app/exports/_preview"
rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:34s} {detail}", flush=True)


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
    errs: list[str] = []
    page.on("console", lambda m: errs.append(f"{m.type}: {m.text[:160]}")
            if m.type == "error" and "404" not in m.text else None)
    page.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:160]}"))

    page.goto(f"{APP}/login", wait_until="load", timeout=60000)
    page.wait_for_timeout(1500)
    page.fill('input[id*="email"]', "qa_e2e_test@test.com")
    page.fill('input[type="password"]', "test123456")
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)

    page.goto(f"{APP}/settings/regulations", wait_until="load", timeout=60000)
    page.wait_for_timeout(3000)
    body = page.locator("body").inner_text()
    rec("法规管理页可打开", "法规" in body, f"{len(body)} 字")

    # 搜索"生产安全事故应急条例"并打开详情
    box = page.locator('input[placeholder*="搜索"], input[placeholder*="法规"]').first
    if box.count() > 0:
        box.fill("生产安全事故应急条例")
        page.wait_for_timeout(2000)
    row = page.locator("tr", has_text="生产安全事故应急条例").first
    rec("列表能查到目标法规", row.count() > 0)
    if row.count() > 0:
        row.get_by_role("button", name=re.compile(r"详\s*情")).first.click()
        page.wait_for_timeout(2500)
        modal = page.locator("[role=dialog]").first.inner_text()
        rec("详情弹窗出现体系链区块", "法规体系链" in modal)
        rec("上位法链含安全生产法", "安全生产法" in modal, modal[-160:].replace("\n", " ")[:120])
        rec("展示直接下级", "直接下级" in modal)
        page.screenshot(path=os.path.join(OUT, "regulation-lineage-ui.png"), full_page=False)
    rec("无 console/pageerror", not errs, f"{len(errs)} 条")
    browser.close()

bad = [r for r in rows if not r[1]]
print(f"\n==== 法规体系链 UI：{len(rows)} 项，失败 {len(bad)}")
for n, _, d in bad:
    print(f"   FAIL {n}: {d}")
sys.exit(1 if bad else 0)
