"""v6 前端改动真实浏览器验证（桌面 1440 + 移动 390）。

覆盖本轮两处前端改动：
  1. 作业票审批工作台新增「只看我的待办」开关：默认请求带 assigned_to_me=true，
     关掉后请求不再带该参数（企业主可看全部）；
  2. 移动端批量生成不再隐藏风格选择：选「简洁」后请求体的
     style_preference.detail_level 必须是 concise（此前会被静默忽略）。

默认跑开发服务器（5173，源码挂载，改动即时生效）；可用 E2E_BASE 指向 8082 产物环境。
批量生成请求被 route 拦截并伪造响应，不会真的触发 LLM。
"""

import json
import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:5173")
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = os.environ.get("E2E_PLAN", "6792266d-cd5f-41fc-b591-648fcb64b435")
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

results = []
page_errors = []


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""), flush=True)


def attach(page, tag):
    page.on("pageerror", lambda e: page_errors.append({"page": tag, "error": str(e)[:300]}))


def login(page, path="/login"):
    page.goto(BASE + path, wait_until="load", timeout=45000)
    page.wait_for_timeout(1200)
    # 桌面端 id 是 login_email，移动端没有 id 只有 type=email：两种都覆盖
    page.fill('input[type="email"], input[id*="email"]', U)
    page.fill('input[type="password"]', P)
    if page.locator('button[type="submit"]').count() > 0:
        page.click('button[type="submit"]')
    else:
        page.get_by_role("button", name="登录").first.click()
    page.wait_for_timeout(3500)


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # ---------- 桌面：审批工作台「只看我的待办」----------
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        attach(page, "desktop")
        ticket_urls = []
        page.on(
            "request",
            lambda r: ticket_urls.append(r.url)
            if "/api/v1/work-ticket/tickets" in r.url
            else None,
        )
        login(page)
        check("桌面登录成功", "/login" not in page.url, page.url)
        page.goto(BASE + f"/enterprises/{ENT}/work-ticket/approval",
                  wait_until="load", timeout=45000)
        page.wait_for_timeout(3500)
        check("桌面-审批工作台打开", "work-ticket/approval" in page.url, page.url)
        check("桌面-存在「只看我的待办」开关",
              page.locator("text=只看我的待办").count() > 0)
        default_hits = [u for u in ticket_urls if "assigned_to_me=true" in u]
        check("桌面-默认请求带 assigned_to_me=true", len(default_hits) > 0,
              f"captured={len(ticket_urls)}")
        page.screenshot(path=os.path.join(OUT, "v6-approval-mine-on.png"))

        before = len(ticket_urls)
        page.click(".ant-switch")
        page.wait_for_timeout(2500)
        after = [u for u in ticket_urls[before:] if "/work-ticket/tickets" in u]
        check("桌面-关掉开关后请求不再带该参数",
              bool(after) and all("assigned_to_me" not in u for u in after),
              f"new={len(after)}")
        page.screenshot(path=os.path.join(OUT, "v6-approval-mine-off.png"))
        ctx.close()

        # ---------- 移动端 390：批量生成风格选择 ----------
        mctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=UA,
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
        )
        mpage = mctx.new_page()
        attach(mpage, "mobile")
        login(mpage, "/m/login")
        check("移动端登录成功", "/m/login" not in mpage.url, mpage.url)
        mpage.goto(BASE + f"/m/plans/{PLAN}/edit", wait_until="load", timeout=45000)
        mpage.wait_for_timeout(4000)
        check("移动端-打开预案编辑页", "/m/plans/" in mpage.url, mpage.url)

        captured = {}

        def _handler(route):
            try:
                captured["body"] = route.request.post_data
            except Exception as exc:  # noqa: BLE001
                captured["error"] = str(exc)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"code": 0, "message": "探针拦截（未真实生成）"}),
            )

        mctx.route("**/generate/batch/background", _handler)
        mpage.click("text=批量生成")
        mpage.wait_for_timeout(1500)
        check("移动端-风格选择在批量模式下可见",
              mpage.locator("text=生成风格（可选）").count() > 0)
        mpage.screenshot(path=os.path.join(OUT, "v6-mobile-batch-sheet.png"))
        mpage.click("text=简洁")
        mpage.wait_for_timeout(400)
        mpage.click("text=开始生成")
        mpage.wait_for_timeout(2500)
        body = captured.get("body")
        parsed = {}
        if body:
            try:
                parsed = json.loads(body)
            except Exception:  # noqa: BLE001
                parsed = {}
        check("移动端-批量请求带上请求级风格覆盖",
              parsed.get("style_preference", {}).get("detail_level") == "concise",
              json.dumps(parsed, ensure_ascii=False)[:200])
        check("移动端-批量请求仍带章节列表",
              isinstance(parsed.get("section_keys"), list) and len(parsed["section_keys"]) > 0,
              str(parsed.get("section_keys"))[:120])
        mctx.close()
        browser.close()

    check("无未捕获前端异常", len(page_errors) == 0, json.dumps(page_errors, ensure_ascii=False)[:300])
    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-v6-ui.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "base": BASE,
                   "results": results, "page_errors": page_errors}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
