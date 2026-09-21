"""AI 一键生成排查计划：浏览器端到端探针（建议 → 采用 → 分区映射 → 落库）。

背景：`/ai/plan-builder` 后端与前端 service 早已存在，但**没有任何页面调用**——
契约里写的"页面整批确认/逐条调整后映射为企业成员 id 与分区 id，再经 POST /plans 落库"
那一跳从未实现。本探针验证补齐后的真实链路（AI 响应用 route 拦截伪造，零 LLM 费用）。

清理：探针自建的楼层/分区/计划在 finally 里按 id 删除。
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

API = "http://localhost:8000/api/v1"
BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
ZONE_A = "AI探针分区A"
ZONE_B = "AI探针分区B"
PLAN_NAME = "AI探针-罐区日常排查"

results = []
page_errors = []
console_errors = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True, check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""), flush=True)


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {}


def main():
    os.makedirs(OUT, exist_ok=True)
    token = floor_id = zone_a = zone_b = created_plan = None
    try:
        status, payload = call("POST", "/auth/login", body={"email": U, "password": P})
        assert status == 200, (status, payload)
        token = payload["data"]["access_token"]

        floor_id = sql(
            "insert into enterprise_floors (enterprise_id, name, sort_order) values "
            f"('{ENT}','AI探针楼层',0) returning id;"
        )
        zone_a = sql(
            "insert into risk_zones (id, enterprise_id, name, sort_order, floor_id) values "
            f"(gen_random_uuid(),'{ENT}','{ZONE_A}',0,'{floor_id}') returning id;"
        )
        zone_b = sql(
            "insert into risk_zones (id, enterprise_id, name, sort_order, floor_id) values "
            f"(gen_random_uuid(),'{ENT}','{ZONE_B}',1,'{floor_id}') returning id;"
        )
        print(f"setup ok: floor={floor_id} zones={zone_a},{zone_b}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda e: page_errors.append(str(e)[:300]))
            page.on("console", lambda m: console_errors.append(m.text[:300])
                    if m.type == "error" else None)

            def _builder(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "success": True,
                            "code": 200,
                            "data": {
                                "available": True,
                                "plans": [
                                    {
                                        "name": PLAN_NAME,
                                        "category": "daily",
                                        "frequency": "daily",
                                        "zone_names": [ZONE_A, ZONE_B],
                                        "responsible_user_name": None,
                                    }
                                ],
                            },
                        },
                        ensure_ascii=False,
                    ).encode("utf-8"),
                )

            page.route("**/hazard-inspection/ai/plan-builder", _builder)
            page.goto(BASE + "/login", wait_until="load", timeout=45000)
            page.wait_for_timeout(1200)
            page.fill('input[type="email"], input[id*="email"]', U)
            page.fill('input[type="password"]', P)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3500)
            check("登录成功", "/login" not in page.url, page.url)

            page.goto(BASE + f"/enterprises/{ENT}/hazard/plans", wait_until="load", timeout=45000)
            page.wait_for_timeout(3000)
            check("计划页出现「AI 生成计划」按钮", page.locator("text=AI 生成计划").count() > 0)
            page.click("text=AI 生成计划")
            page.wait_for_timeout(1200)
            page.fill('textarea', "罐区、生产车间；动火作业较多")
            page.fill('input[placeholder*="日常每天"]', "日常每天一次，罐区每周一次")
            page.click("text=生成计划建议")
            page.wait_for_timeout(1800)
            check("展示 AI 计划建议", page.locator(f"text={PLAN_NAME}").count() > 0)
            page.screenshot(path=os.path.join(OUT, "plan-builder-suggestions.png"))

            # 注意两点：①`text=采用` 会命中提示文案"采用后仍需…"；
            # ②antd 会给恰好两个汉字的按钮插空格（"采 用"），所以直接定位 Alert 的 action 按钮
            page.click(".ant-modal .ant-alert button")
            page.wait_for_timeout(1500)
            check("采用后打开新建计划弹窗",
                  page.locator(".ant-modal-title:has-text('新建计划')").count() > 0)
            # 诊断信息：失败时能直接看出弹窗是否真的打开、有无前端异常
            titles = page.locator(".ant-modal-title").all_inner_texts()
            print("modal titles:", titles, "page_errors:", page_errors,
                  "console_errors:", console_errors[-3:], flush=True)
            name_value = page.input_value('.ant-modal input[maxlength="255"]')
            check("计划名称已预填", name_value == PLAN_NAME, name_value)
            zone_labels = page.locator(".ant-modal .ant-select-selection-item").all_inner_texts()
            check("分区名已映射为分区并选中",
                  ZONE_A in " ".join(zone_labels) and ZONE_B in " ".join(zone_labels),
                  " | ".join(zone_labels))
            page.screenshot(path=os.path.join(OUT, "plan-builder-prefilled.png"))

            # 同理："保存" 也被 antd 渲染成 "保 存"，直接点弹窗主按钮
            page.locator(".ant-modal-footer button.ant-btn-primary").last.click()
            page.wait_for_timeout(2500)
            status, listing = call("GET", f"/enterprises/{ENT}/hazard-inspection/plans", token=token)
            names = [p["name"] for p in listing.get("data", [])]
            check("计划已落库（映射后的分区 id）", PLAN_NAME in names, f"plans={names[:5]}")
            created = next((p for p in listing.get("data", []) if p["name"] == PLAN_NAME), None)
            if created:
                created_plan = created["id"]
                check("落库分区就是探针分区",
                      set(created["zone_ids"]) == {zone_a, zone_b},
                      str(created["zone_ids"]))
            browser.close()

        check("无未捕获前端异常", len(page_errors) == 0, json.dumps(page_errors, ensure_ascii=False)[:200])
    finally:
        try:
            if created_plan:
                sql(f"delete from hazard_inspection_plans where id='{created_plan}';")
            sql(f"delete from hazard_inspection_plans where name='{PLAN_NAME}';")
            if zone_a and zone_b:
                sql(f"delete from risk_zones where id in ('{zone_a}','{zone_b}');")
            if floor_id:
                sql(f"delete from enterprise_floors where id='{floor_id}';")
            print("cleanup done: 探针计划/分区/楼层已删除")
        except Exception as exc:  # noqa: BLE001
            print("CLEANUP FAILED:", exc)

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-plan-builder.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "base": BASE, "results": results},
                  fh, ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
