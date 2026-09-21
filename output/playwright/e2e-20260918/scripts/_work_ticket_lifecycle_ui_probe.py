"""作业票详情页生命周期按钮的真实浏览器校验。

做法：API 开一张草稿票 → 分别把状态置为 draft/approved/working/finished（直接改库，
只为驱动 UI 条件渲染）→ 每次打开详情页断言只出现该状态下应有的动作按钮 → 删票。
"""

import json
import os
import re
import subprocess
import sys
import urllib.request

from playwright.sync_api import sync_playwright

API = "http://localhost:8000/api/v1"
BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
TPL = "99f530de-2586-5f03-9751-b9db1bbb3777"

results = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True, check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""), flush=True)


def button_count(page, label: str) -> int:
    """按按钮角色计数；antd 会给恰好两字的按钮插空格（"作废" 渲染成 "作 废"），故用允许空格的正则。"""
    pattern = re.compile(r"\s*".join(re.escape(ch) for ch in label))
    return page.get_by_role("button", name=pattern).count()


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, json.loads(resp.read())


def main():
    os.makedirs(OUT, exist_ok=True)
    ticket_id = None
    try:
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]
        _, tpl_payload = call("GET", "/work-ticket/templates", token)
        tpl = next(t for t in tpl_payload["data"] if t["id"] == TPL)
        values = {f["field_key"]: "UI探针值" for f in tpl["fields"] if f.get("is_required")}
        values["confirmed_measures"] = [m["sort_order"] for m in tpl["measures"]]
        _, opened = call("POST", "/work-ticket/tickets", token,
                         {"enterprise_id": ENT, "enterprise_code": "UIPRB",
                          "ticket_type": "DHZY", "template_id": TPL, "level": None,
                          "values": values})
        ticket_id = opened["data"]["id"]

        expectations = [
            ("draft", ["提交审批", "作废", "打印票面"], ["开始作业", "完工", "归档"]),
            ("approved", ["开始作业", "作废", "打印票面"], ["提交审批", "完工", "归档"]),
            ("working", ["完工", "打印票面"], ["开始作业", "提交审批", "归档"]),
            ("finished", ["归档", "打印票面"], ["开始作业", "完工", "提交审批"]),
        ]
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(BASE + "/login", wait_until="load", timeout=45000)
            page.wait_for_timeout(1200)
            page.fill('input[type="email"], input[id*="email"]', U)
            page.fill('input[type="password"]', P)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3500)
            for status, present, absent in expectations:
                sql(f"update work_ticket_instances set status='{status}' where id='{ticket_id}';")
                page.goto(BASE + f"/enterprises/{ENT}/work-ticket/{ticket_id}",
                          wait_until="load", timeout=45000)
                page.wait_for_timeout(2200)
                miss = [b for b in present if button_count(page, b) == 0]
                extra = [b for b in absent if button_count(page, b) > 0]
                check(f"{status} 状态按钮正确", not miss and not extra,
                      f"缺={miss} 多={extra}")
            page.screenshot(path=os.path.join(OUT, "work-ticket-lifecycle-ui.png"))
            browser.close()
    finally:
        if ticket_id:
            sql(f"delete from work_ticket_instances where id='{ticket_id}';")
            print("cleanup done")

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-work-ticket-lifecycle-ui.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
