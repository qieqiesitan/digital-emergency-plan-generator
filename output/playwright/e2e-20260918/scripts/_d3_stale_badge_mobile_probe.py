"""D-3 移动端（390px）验证：进入待更新章节时编辑区顶部出现提示条。

前置与桌面探针一致（造 stale 状态）；移动端断言点在 PlanEditorScreen，
不改动移动端 ChapterTree（该文件由并行会话负责）。
"""

import json
import os
import subprocess
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
API = "http://localhost:8000/api/v1"
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = os.environ.get("E2E_PLAN", "6792266d-cd5f-41fc-b591-648fcb64b435")
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]

results = []
errors = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


def call(method, path, token=None, body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        return exc.code, {"detail": exc.read()[:200].decode("utf-8", "replace")}


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""), flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    zone_id = object_id = unit_id = event_id = None
    section_key = title = None
    token = None
    try:
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]
        _, r = call("GET", f"/enterprises/{ENT}/risk-management/floors", token)
        floor_id = next((f["id"] for f in (r.get("data") or []) if f.get("is_default")), None)
        _, r = call("POST", f"/enterprises/{ENT}/risk-management/zones",
                    token, {"floor_id": floor_id, "name": "探针分区"})
        zone_id = r["data"]["id"]
        _, r = call("POST", f"/enterprises/{ENT}/risk-management/objects",
                    token, {"zone_id": zone_id, "name": "探针对象"})
        object_id = r["data"]["id"]
        _, r = call("POST", f"/enterprises/{ENT}/risk-management/objects/{object_id}/units",
                    token, {"name": "探针单元"})
        unit_id = r["data"]["id"]
        _, r = call("POST", f"/enterprises/{ENT}/risk-management/units/{unit_id}/events",
                    token, {"accident_type": "火灾", "risk_level": "一般"})
        event_id = r["data"]["id"]
        _, r = call("GET", f"/plans/{PLAN}/sections", token)
        target = next(s for s in r["data"] if "risk_sources" in (s.get("data_dependencies") or []))
        section_key, title = target["section_key"], target["title"]
        call("PUT", f"/plans/{PLAN}/sections/{section_key}", token, {"content": "探针正文（依赖风险数据）"})
        call("DELETE", f"/enterprises/{ENT}/risk-management/events/{event_id}", token)
        event_id = None
        _, r = call("GET", f"/plans/{PLAN}/sections", token)
        cur = next(s for s in r["data"] if s["section_key"] == section_key)
        check("前置：接口已返回 stale_domains", cur["stale_domains"] == ["risk_sources"],
              f"stale={cur['stale_domains']} title={title}")

        with sync_playwright() as pw:
            b = pw.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": 844},
                                user_agent=UA, is_mobile=True, has_touch=True,
                                device_scale_factor=3)
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)[:200]))
            page.on("console", lambda m: errors.append("console:" + m.text[:150])
                    if m.type == "error" else None)
            page.goto(BASE + "/m/login", wait_until="load", timeout=45000)
            page.wait_for_timeout(1200)
            page.fill('input[type="email"]', U)
            page.fill('input[type="password"]', P)
            page.get_by_role("button", name="登录").first.click()
            page.wait_for_timeout(3500)
            page.goto(BASE + f"/m/plans/{PLAN}/edit", wait_until="load", timeout=45000)
            page.wait_for_timeout(4000)
            check("移动端进入预案编辑页", "/m/login" not in page.url, page.url)

            node = page.get_by_text(title, exact=False).first
            check("找到目标章节节点", node.count() > 0, f"title={title}")
            node.click()
            page.wait_for_timeout(2500)
            body = page.inner_text("body")
            check("移动端编辑区出现「依赖数据已更新」提示",
                  "依赖数据已更新" in body and "风险分级管控" in body,
                  body[:120].replace("\n", " | "))
            page.screenshot(path=os.path.join(OUT, "d3-stale-badge-mobile.png"))
            check("移动端 0 pageerror / 0 console error", not errors, str(errors[:2]))
            ctx.close()
            b.close()
    finally:
        if token:
            if section_key:
                call("PUT", f"/plans/{PLAN}/sections/{section_key}", token, {"content": ""})
            if event_id:
                call("DELETE", f"/enterprises/{ENT}/risk-management/events/{event_id}", token)
            if zone_id:
                call("DELETE", f"/enterprises/{ENT}/risk-management/zones/{zone_id}", token)
        leftover = sql("select (select count(*) from risk_zones where name='探针分区')"
                       " || '/' || (select count(*) from plan_sections where plan_project_id='"
                       + PLAN + "' and section_key='" + str(section_key)
                       + "' and coalesce(content,'')<>'');")
        print("清理后残留（探针分区/带正文的探针章节）:", leftover)
        with open(os.path.join(OUT, "summary-d3-stale-badge-mobile.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"results": results, "leftover": leftover,
                       "passed": sum(1 for r in results if r["ok"]),
                       "total": len(results)}, fh, ensure_ascii=False, indent=2)
    fails = [r["name"] for r in results if not r["ok"]]
    print(f"\n=== {len(results) - len(fails)}/{len(results)} PASS ===")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
