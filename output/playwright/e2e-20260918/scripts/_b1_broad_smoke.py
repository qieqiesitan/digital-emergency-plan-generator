"""B1 之后的广域冒烟：桌面 18 页 + 移动端 17 页，确认重构未破坏既有页面。

只读巡检：不写入业务数据；产物写 b1-broad-*.png，不覆盖 W4 证据。
"""

import json
import os
import re
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://host.docker.internal:8082")
OUT = "/app/exports/e2e-20260918"
U, P = "qa_e2e_test@test.com", "test123456"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

ENT = "10e11995-e682-405a-9035-fbde13cca213"   # qa_e2e_test 自己的企业
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"  # qa_e2e_test 自己的预案

DESKTOP = [
    ("dashboard", "/dashboard"),
    ("enterprises", "/enterprises"),
    ("enterprise-cockpit", f"/enterprises/{ENT}"),
    ("enterprise-edit", f"/enterprises/{ENT}/edit"),
    ("enterprise-org", f"/enterprises/{ENT}/org"),
    ("plans", "/plans"),
    ("plan-editor", f"/plans/{PLAN}/edit"),
    ("chat", "/chat"),
    ("profile", "/settings/profile"),
    ("hazard", f"/enterprises/{ENT}/hazard"),
    ("risk-overview", f"/enterprises/{ENT}/risk-management/overview"),
    ("risk-workbench", f"/enterprises/{ENT}/risk-management/workbench"),
    ("risk-control-list", f"/enterprises/{ENT}/risk-management/control-list"),
    ("risk-methods", f"/enterprises/{ENT}/risk-management/methods"),
    ("risk-notice-cards", f"/enterprises/{ENT}/risk-management/notice-cards"),
    ("risk-data-dicts", f"/enterprises/{ENT}/risk-management/data-dicts"),
    ("major-hazard", f"/enterprises/{ENT}/major-hazard"),
    ("work-ticket", f"/enterprises/{ENT}/work-ticket"),
    ("risk-assessment-preview", f"/enterprises/{ENT}/risk-assessment/preview"),
    ("resource-investigation-preview", f"/enterprises/{ENT}/resource-investigation/preview"),
]

MOBILE = [
    ("m-dashboard", "/m/dashboard"),
    ("m-enterprises", "/m/enterprises"),
    ("m-enterprise-detail", f"/m/enterprises/{ENT}"),
    ("m-enterprise-edit", f"/m/enterprises/{ENT}/edit"),
    ("m-enterprise-risk", f"/m/enterprises/{ENT}/risk-management"),
    ("m-enterprise-resources", f"/m/enterprises/{ENT}/resources"),
    ("m-enterprise-risk-assessment", f"/m/enterprises/{ENT}/risk-assessment"),
    ("m-enterprise-resource-investigation", f"/m/enterprises/{ENT}/resource-investigation"),
    ("m-enterprise-plans", f"/m/enterprises/{ENT}/plans"),
    ("m-plans", "/m/plans"),
    ("m-plan-new", "/m/plans/new"),
    ("m-plan-editor", f"/m/plans/{PLAN}/edit"),
    ("m-plan-versions", f"/m/plans/{PLAN}/versions"),
    ("m-plan-preview", f"/m/plans/{PLAN}/preview"),
    ("m-settings", "/m/settings"),
    ("m-settings-profile", "/m/settings/profile"),
    ("m-chat", "/m/chat"),
]


def run(browser, label: str, pages, mobile: bool) -> list:
    ctx = (browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                               has_touch=True, locale="zh-CN", user_agent=UA)
           if mobile else browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN"))
    page = ctx.new_page()
    bucket = {"console": [], "pageerror": [], "http500": []}
    page.on("console", lambda m: bucket["console"].append(m.text[:200]) if m.type == "error" else None)
    page.on("pageerror", lambda e: bucket["pageerror"].append(str(e)[:200]))
    page.on("response", lambda r: bucket["http500"].append(f"{r.status} {r.request.method} {r.url[:110]}")
            if r.status >= 500 else None)

    if mobile:
        page.goto(BASE + "/m/login", wait_until="load", timeout=45000)
        page.wait_for_timeout(1200)
        page.fill('input[placeholder="请输入邮箱"]', U)
        page.fill('input[placeholder="请输入密码"]', P)
        page.locator("button:has-text('登录')").last.click()
    else:
        page.goto(BASE + "/login", wait_until="load", timeout=45000)
        page.wait_for_timeout(1200)
        page.fill('input[id*="email"]', U)
        page.fill('input[type="password"]', P)
        page.click('button[type="submit"]')
    page.wait_for_timeout(3500)

    rows = []
    for name, path in pages:
        rec = {"name": f"{label}-{name}", "path": path, "console": [], "pageerror": [], "http500": []}
        t0 = time.time()
        for key in ("console", "pageerror", "http500"):
            bucket[key].clear()
        try:
            page.goto(BASE + path, wait_until="load", timeout=45000)
            page.wait_for_timeout(2500)
            body = page.locator("body").inner_text()
            rec.update(url=page.url, text_len=len(body), text_head=re.sub(r"\s+", " ", body)[:160],
                       status="ok")
            page.screenshot(path=os.path.join(OUT, f"b1-broad-{label}-{name}.png"), full_page=False)
        except Exception as exc:  # noqa: BLE001
            rec.update(status="error", error=f"{type(exc).__name__}: {exc}"[:200])
        rec["console"] = list(bucket["console"])
        rec["pageerror"] = list(bucket["pageerror"])
        rec["http500"] = list(bucket["http500"])
        rec["ms"] = int((time.time() - t0) * 1000)
        rows.append(rec)
        flag = "OK " if rec["status"] == "ok" and not rec["pageerror"] else "!! "
        print(f"{flag}{rec['name']:42s} len={rec.get('text_len')} "
              f"consoleErr={len(rec['console'])} pageErr={len(rec['pageerror'])} 5xx={len(rec['http500'])}",
              flush=True)
    ctx.close()
    return rows


with sync_playwright() as pw:
    only = os.environ.get("ONLY", "").strip()
    if only:
        DESKTOP = [p for p in DESKTOP if only in p[0]]
        MOBILE = [p for p in MOBILE if only in p[0]]
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    desktop_rows = run(browser, "desktop", DESKTOP, mobile=False)
    mobile_rows = run(browser, "mobile", MOBILE, mobile=True)
    browser.close()

rows = desktop_rows + mobile_rows
with open(os.path.join(OUT, "summary-b1-broad-smoke.json"), "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=1)

bad = [r for r in rows if r["status"] != "ok" or r["pageerror"]]
console_err = [r for r in rows if r["console"]]
five = [r for r in rows if r["http500"]]
print(f"\n==== 冒烟汇总：{len(rows)} 页；页面异常 {len(bad)}；有 console error 的页 {len(console_err)}；5xx {len(five)}")
for r in bad:
    print(f"  ERROR {r['name']} {r.get('error', '')}")
for r in console_err:
    print(f"  CONSOLE {r['name']}: {r['console'][:1]}")
for r in five:
    print(f"  5XX {r['name']}: {r['http500'][:1]}")
