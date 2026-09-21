"""AI 清单补全端到端探针（前端入口 → 建议 → 勾选落库 → 去重）。

背景：`/ai/checklist` 端点与前端 service 早已存在，但**页面从未调用**、后端也没有
落库端点——即"AI 建议 → 勾选合并去重"整条链路的最后一跳是断的。本探针验证补齐后
的真实行为（浏览器点击 + 后端落库 + 去重），AI 响应用 route 拦截伪造，不调用 LLM。

清理：探针自建的计划/任务/清单项在 finally 里按 id 删除。
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
OWNER_ID = "506a380e-a2fe-4fd8-9430-f7f4c61f3d4b"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
TASK_TITLE = "AI补全探针任务"
EXISTING = "探针-既有项：灭火器压力表指针在绿区"
NEW_ITEM = "探针-AI建议新增：罐区可燃气体浓度 ≤ 25% LEL"

results = []
page_errors = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True, check=True)
    # psql 的返回里可能混有 "INSERT 0 1" 之类命令标签：只取第一行有效值
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
    plan_id = None
    task_id = None
    token = None
    try:
        status, payload = call("POST", "/auth/login", body={"email": U, "password": P})
        assert status == 200, (status, payload)
        token = payload["data"]["access_token"]

        # 计划直接建库：API 要求 zone_ids 非空且分区必须挂在楼层下，探针没必要为此
        # 造楼层/分区链；本探针验证的是 AI 补全链路，不是计划创建校验。
        plan_id = sql(
            "insert into hazard_inspection_plans "
            "(enterprise_id, name, category, frequency, zone_ids, enabled) values "
            f"('{ENT}','AI补全探针计划','daily','daily','[]'::jsonb,true) returning id;"
        )
        task_id = sql(
            "insert into hazard_inspection_tasks "
            "(plan_id, enterprise_id, title, status, responsible_user_id, due_at) values "
            f"('{plan_id}','{ENT}','{TASK_TITLE}','pending','{OWNER_ID}', now() + interval '1 day') "
            "returning id;"
        )
        sql(
            "insert into hazard_inspection_items (task_id, content, expected_note, result) values "
            f"('{task_id}','{EXISTING}','指针在绿区','pending');"
        )
        print(f"setup ok: plan={plan_id} task={task_id}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda e: page_errors.append(str(e)[:300]))

            def _ai_handler(route):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "success": True,
                            "code": 200,
                            "data": {
                                "available": True,
                                "items": [
                                    {"content": NEW_ITEM, "expected_note": "≤25% LEL"},
                                    {"content": EXISTING, "expected_note": "应与既有项去重"},
                                ],
                            },
                        },
                        ensure_ascii=False,
                    ).encode("utf-8"),
                )

            page.route("**/hazard-inspection/ai/checklist", _ai_handler)
            page.goto(BASE + "/login", wait_until="load", timeout=45000)
            page.wait_for_timeout(1200)
            page.fill('input[type="email"], input[id*="email"]', U)
            page.fill('input[type="password"]', P)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3500)
            check("登录成功", "/login" not in page.url, page.url)

            page.goto(BASE + f"/enterprises/{ENT}/hazard/tasks", wait_until="load", timeout=45000)
            page.wait_for_timeout(3000)
            check("任务列表出现探针任务", page.locator(f"text={TASK_TITLE}").count() > 0)
            page.click(f"text={TASK_TITLE}")
            page.wait_for_timeout(1800)
            check("任务详情弹窗打开", page.locator("text=AI 补全清单").count() > 0)
            page.screenshot(path=os.path.join(OUT, "ai-checklist-task-detail.png"))

            page.click("text=AI 补全清单")
            page.wait_for_timeout(1500)
            check("AI 建议弹窗展示建议项", page.locator(f"text={NEW_ITEM}").count() > 0)
            page.screenshot(path=os.path.join(OUT, "ai-checklist-suggest-modal.png"))
            page.click("text=加入清单")
            page.wait_for_timeout(2500)
            check("出现落库成功提示", page.locator("text=已补充").count() > 0)
            page.screenshot(path=os.path.join(OUT, "ai-checklist-after-append.png"))
            browser.close()

        status, detail = call("GET", f"/enterprises/{ENT}/hazard-inspection/tasks/{task_id}", token=token)
        contents = [i["content"] for i in detail["data"]["items"]] if status == 200 else []
        check("新建议项已写入清单", NEW_ITEM in contents, f"items={len(contents)}")
        check("与既有项重复的建议被去重", contents.count(EXISTING) == 1,
              f"dup_count={contents.count(EXISTING)}")
    finally:
        try:
            if task_id:
                sql(f"delete from hazard_inspection_tasks where id='{task_id}';")
            if plan_id:
                sql(f"delete from hazard_inspection_plans where id='{plan_id}';")
            print("cleanup done: 探针计划/任务/清单项已删除")
        except Exception as exc:  # noqa: BLE001
            print("CLEANUP FAILED:", exc)

    check("无未捕获前端异常", len(page_errors) == 0, json.dumps(page_errors, ensure_ascii=False)[:200])
    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-ai-checklist.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "base": BASE,
                   "results": results}, fh, ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
