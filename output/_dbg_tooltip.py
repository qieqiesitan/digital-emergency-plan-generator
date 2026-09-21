"""调试：定位章节树 ⚠ 的 tooltip DOM（antd v6 类名与渲染位置）。"""
import json
import os
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
API = "http://localhost:8000/api/v1"
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"


def token():
    req = urllib.request.Request(API + "/auth/login", method="POST",
                                 data=json.dumps({"email": U, "password": P}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["data"]["access_token"]


t = token()


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {t}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


# 造待更新状态
floors = call("GET", f"/enterprises/{ENT}/risk-management/floors")["data"]
fid = next(f["id"] for f in floors if f.get("is_default"))
z = call("POST", f"/enterprises/{ENT}/risk-management/zones",
         {"floor_id": fid, "name": "探针分区"})["data"]["id"]
o = call("POST", f"/enterprises/{ENT}/risk-management/objects",
         {"zone_id": z, "name": "探针对象"})["data"]["id"]
u = call("POST", f"/enterprises/{ENT}/risk-management/objects/{o}/units", {"name": "探针单元"})["data"]["id"]
ev = call("POST", f"/enterprises/{ENT}/risk-management/units/{u}/events",
          {"accident_type": "火灾", "risk_level": "一般"})["data"]["id"]
secs = call("GET", f"/plans/{PLAN}/sections")["data"]
key = next(s["section_key"] for s in secs if "risk_sources" in (s.get("data_dependencies") or []))
call("PUT", f"/plans/{PLAN}/sections/{key}", {"content": "探针正文"})
call("DELETE", f"/enterprises/{ENT}/risk-management/events/{ev}")

try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(BASE + "/login", wait_until="load", timeout=45000)
        page.wait_for_timeout(1000)
        page.fill('input[type="email"], input[id*="email"]', U)
        page.fill('input[type="password"]', P)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)
        page.goto(BASE + f"/plans/{PLAN}/edit", wait_until="load", timeout=45000)
        page.wait_for_timeout(4500)
        spans = page.locator('span:has-text("⚠")')
        print("含 ⚠ 的 span 数:", spans.count())
        for i in range(min(spans.count(), 6)):
            print(f"  [{i}] text={spans.nth(i).inner_text()[:40]!r} cls={spans.nth(i).get_attribute('class')}")
        # 悬停树里的那个（排除图例里的）
        target = page.locator('.ant-tree-treenode span:has-text("⚠")').first
        print("树内 ⚠ 数:", page.locator('.ant-tree-treenode span:has-text("⚠")').count())
        target.hover()
        page.wait_for_timeout(1500)
        print("hover 后 tooltip 相关元素:")
        for sel in (".ant-tooltip", ".ant-tooltip-inner", "[role='tooltip']", ".ant-tooltip-content"):
            n = page.locator(sel).count()
            print(f"  {sel}: {n}", page.locator(sel).first.inner_text()[:80] if n else "")
        html = page.evaluate("""() => {
            const el = document.querySelector('[role=tooltip]') || document.querySelector('.ant-tooltip');
            return el ? el.outerHTML.slice(0, 300) : 'NO_TOOLTIP';
        }""")
        print("tooltip DOM:", html)
        page.screenshot(path="backend/exports/e2e-20260918/dbg-tooltip.png")
        b.close()
finally:
    call("PUT", f"/plans/{PLAN}/sections/{key}", {"content": ""})
    call("DELETE", f"/enterprises/{ENT}/risk-management/zones/{z}")
    print("已清理探针数据")
