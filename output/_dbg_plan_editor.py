"""调试：预案编辑页为什么不显示 ⚠。打印路由、接口响应与页面文本。"""
import json
import os
import subprocess
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
API = "http://localhost:8000/api/v1"
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]


def api_token():
    req = urllib.request.Request(
        API + "/auth/login", method="POST",
        data=json.dumps({"email": U, "password": P}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["data"]["access_token"]


token = api_token()


def call(method, path, body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


# 造 stale 状态
floors = call("GET", f"/enterprises/{ENT}/risk-management/floors")["data"]
fid = next(f["id"] for f in floors if f.get("is_default"))
z = call("POST", f"/enterprises/{ENT}/risk-management/zones",
         {"floor_id": fid, "name": "探针分区"})["data"]["id"]
o = call("POST", f"/enterprises/{ENT}/risk-management/objects",
         {"zone_id": z, "name": "探针对象"})["data"]["id"]
u = call("POST", f"/enterprises/{ENT}/risk-management/objects/{o}/units", {"name": "探针单元"})["data"]["id"]
ev = call("POST", f"/enterprises/{ENT}/risk-management/units/{u}/events",
          {"accident_type": "火灾", "risk_level": "一般"})["data"]["id"]
sections = call("GET", f"/plans/{PLAN}/sections")["data"]
target = next(s for s in sections if "risk_sources" in (s.get("data_dependencies") or []))
key, title = target["section_key"], target["title"]
call("PUT", f"/plans/{PLAN}/sections/{key}", {"content": "探针正文（依赖风险数据）"})
call("DELETE", f"/enterprises/{ENT}/risk-management/events/{ev}")
sections = call("GET", f"/plans/{PLAN}/sections")["data"]
print("接口返回章节数:", len(sections))
print("含 stale 的章节:", [(s["section_key"], s.get("stale_domains")) for s in sections
                           if s.get("stale_domains")])
print("目标章节:", key, title)

fetched = {}

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    saw = []
    page.on("response", lambda r: saw.append((r.status, r.url))
            if "/sections" in r.url else None)

    def grab(resp):
        if "/sections" in resp.url and resp.status == 200:
            try:
                fetched["data"] = resp.json()
            except Exception as exc:  # noqa: BLE001
                fetched["err"] = str(exc)

    page.on("response", grab)
    page.goto(BASE + "/login", wait_until="load", timeout=45000)
    page.wait_for_timeout(1200)
    page.fill('input[type="email"], input[id*="email"]', U)
    page.fill('input[type="password"]', P)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3000)
    page.goto(BASE + f"/plans/{PLAN}/edit", wait_until="load", timeout=45000)
    page.wait_for_timeout(5000)
    print("\n编辑页 URL:", page.url)
    print("sections 请求:", saw)
    data = (fetched.get("data") or {}).get("data") or []
    print("浏览器实际拿到 stale:", [(s.get("section_key"), s.get("stale_domains")) for s in data
                                     if s.get("stale_domains")])
    tgt = next((s for s in data if s.get("section_key") == key), None)
    print("浏览器拿到的目标章节:", None if tgt is None else
          {k: tgt.get(k) for k in ("section_key", "data_dependencies", "stale_domains")},
          "内容长度=", 0 if tgt is None else len(tgt.get("content") or ""))
    body = page.inner_text("body")
    print("\n页面文本前 500 字:\n", body[:500].replace("\n", " | "))
    print("\n⚠ 计数:", page.locator('text=⚠').count(),
          " 图例计数:", page.locator('text=图例').count(),
          " ant-tree 节点:", page.locator('.ant-tree-treenode').count())
    ctx.close()
    b.close()

# 清理
call("PUT", f"/plans/{PLAN}/sections/{key}", {"content": ""})
call("DELETE", f"/enterprises/{ENT}/risk-management/zones/{z}")
subprocess.run(DB + [f"delete from enterprise_data_marks where enterprise_id='{ENT}';"],
               capture_output=True, text=True)
print("已清理探针数据")
