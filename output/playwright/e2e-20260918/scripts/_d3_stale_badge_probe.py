"""D-3 前端验证（真浏览器，8082 产物）：章节树显示「⚠ 依赖数据已更新」。

前置用真实 API 造出"待更新"状态（建风险事件 → 写章节正文 → 删风险事件打点），
浏览器断言章节树上该章节出现 ⚠ 且 tooltip 文案正确；同时顺带核对 D-1 改动后的
企业页 KPI（不再有重复的「风险源」卡片）。结束清理探针数据。
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
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]

results = []
page_errors = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        return exc.code, {"detail": exc.read()[:200].decode("utf-8", "replace")}


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""), flush=True)


def login(page):
    page.goto(BASE + "/login", wait_until="load", timeout=45000)
    page.wait_for_timeout(1200)
    page.fill('input[type="email"], input[id*="email"]', U)
    page.fill('input[type="password"]', P)
    if page.locator('button[type="submit"]').count() > 0:
        page.click('button[type="submit"]')
    else:
        page.get_by_role("button", name="登录").first.click()
    page.wait_for_timeout(3500)


def main():
    os.makedirs(OUT, exist_ok=True)
    zone_id = object_id = unit_id = event_id = None
    section_key = None
    token = None
    try:
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]

        # 造「待更新」状态：风险数据 → 章节正文 → 删除风险事件（打点）
        st, r = call("GET", f"/enterprises/{ENT}/risk-management/floors", token)
        floor_id = next((f["id"] for f in (r.get("data") or []) if f.get("is_default")), None)
        st, r = call("POST", f"/enterprises/{ENT}/risk-management/zones",
                     token, {"floor_id": floor_id, "name": "探针分区"})
        zone_id = r.get("data", {}).get("id")
        st, r = call("POST", f"/enterprises/{ENT}/risk-management/objects",
                     token, {"zone_id": zone_id, "name": "探针对象"})
        object_id = r.get("data", {}).get("id")
        st, r = call("POST", f"/enterprises/{ENT}/risk-management/objects/{object_id}/units",
                     token, {"name": "探针单元"})
        unit_id = r.get("data", {}).get("id")
        st, r = call("POST", f"/enterprises/{ENT}/risk-management/units/{unit_id}/events",
                     token, {"accident_type": "火灾", "risk_level": "一般"})
        event_id = r.get("data", {}).get("id")

        st, r = call("GET", f"/plans/{PLAN}/sections", token)
        target = next((s for s in (r.get("data") or [])
                       if "risk_sources" in (s.get("data_dependencies") or [])), None)
        section_key = target.get("section_key") if target else None
        call("PUT", f"/plans/{PLAN}/sections/{section_key}", token, {"content": "探针正文（依赖风险数据）"})
        call("DELETE", f"/enterprises/{ENT}/risk-management/events/{event_id}", token)
        event_id = None
        st, r = call("GET", f"/plans/{PLAN}/sections", token)
        cur = next((s for s in (r.get("data") or []) if s.get("section_key") == section_key), {})
        check("前置：接口已返回 stale_domains", cur.get("stale_domains") == ["risk_sources"],
              f"stale={cur.get('stale_domains')}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.on("pageerror", lambda e: page_errors.append(str(e)[:300]))
            page.on("console", lambda m: page_errors.append("console:" + m.text[:200])
                    if m.type == "error" else None)
            login(page)
            check("浏览器登录成功", "/login" not in page.url, page.url)

            # 预案编辑页：章节树上的 ⚠
            page.goto(BASE + f"/plans/{PLAN}/edit", wait_until="load", timeout=45000)
            page.wait_for_timeout(4000)
            warn = page.locator('span:has-text("⚠")')
            check("章节树出现 ⚠ 依赖数据已更新标记", warn.count() >= 1, f"count={warn.count()}")
            # 悬停内层徽标（外层的 tree 包装 span 不触发 tooltip）；tooltip 走 portal，
            # 用只可能出现在 tooltip 里的句子断言，避免依赖 antd 版本相关的类名
            # 精确文本 "⚠"：树节点标题里的是「✓事故风险描述🤖⚠」，图例里的是「⚠ 依赖数据已更新」，
            # 只有徽标自身是单独的 ⚠，所以 exact=True 能唯一命中
            badges = page.get_by_text("⚠", exact=True)
            badge = badges.first
            tip_ok = False
            if badges.count() > 0:
                badge.hover()
                page.wait_for_timeout(1500)
                text = page.inner_text("body")
                tip_ok = "依赖数据已更新：风险分级管控" in text and "建议重新生成本章节" in text
            check("⚠ tooltip 文案正确（悬停后出现依赖域与建议）", tip_ok,
                  f"badges={badges.count()}")
            page.screenshot(path=os.path.join(OUT, "d3-stale-badge.png"), full_page=False)
            legend = page.locator("text=⚠ 依赖数据已更新").count()
            check("图例已补充 ⚠ 说明", legend >= 1, f"legend={legend}")

            # 企业页 KPI：不再有重复的「风险源」卡片
            page.goto(BASE + f"/enterprises/{ENT}/modules/info", wait_until="load", timeout=45000)
            page.wait_for_timeout(3500)
            body = page.inner_text("body")
            check("企业页显示「风险事件」KPI", "风险事件" in body)
            check("企业页不再有重复的「风险源」KPI", "风险源" not in body, body[:80].replace("\n", " "))
            page.screenshot(path=os.path.join(OUT, "d1-enterprise-kpi.png"), full_page=False)

            check("浏览器 0 pageerror / 0 console error", not page_errors, str(page_errors[:2]))
            ctx.close()
            browser.close()
    finally:
        if token:
            if section_key:
                call("PUT", f"/plans/{PLAN}/sections/{section_key}", token, {"content": ""})
            if event_id:
                call("DELETE", f"/enterprises/{ENT}/risk-management/events/{event_id}", token)
            if zone_id:
                call("DELETE", f"/enterprises/{ENT}/risk-management/zones/{zone_id}", token)
        # 只统计本预案的探针章节（section_key 在其他预案里也常见，不能全局聚合）
        leftover = sql("select (select count(*) from risk_zones where name='探针分区')"
                       " || '/' || (select count(*) from plan_sections where plan_project_id='"
                       + PLAN + "' and section_key='" + str(section_key)
                       + "' and coalesce(content,'')<>'');")
        print("清理后残留（探针分区/带正文的探针章节）:", leftover)
        with open(os.path.join(OUT, "summary-d3-stale-badge.json"), "w", encoding="utf-8") as fh:
            json.dump({"results": results, "leftover": leftover,
                       "passed": sum(1 for r in results if r["ok"]), "total": len(results)},
                      fh, ensure_ascii=False, indent=2)
    fails = [r["name"] for r in results if not r["ok"]]
    print(f"\n=== {len(results) - len(fails)}/{len(results)} PASS ===")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
