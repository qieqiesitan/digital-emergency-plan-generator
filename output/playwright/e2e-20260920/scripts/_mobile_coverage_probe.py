"""移动端完成度探测（只读，一次性）。

目的：用真账号在 390x844 视口跑完移动端全部路由 + 尝试桌面专有深链，
记录：是否被兜底重定向、可见文本长度、关键标题、console error、API 4xx。
不写库、不改代码。
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("MOBILE_BASE", "http://localhost:8082")
OUT = os.environ.get("PROBE_OUT", "output/playwright/e2e-20260920")
U, P = "qa_e2e_test@test.com", "test123456"
MOBILE = {"width": 390, "height": 844}
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

MOBILE_ROUTES = [
    "/m/dashboard",
    "/m/enterprises",
    "/m/enterprises/new",
    "/m/enterprises/{eid}",
    "/m/enterprises/{eid}/edit",
    "/m/enterprises/{eid}/risk-management",
    "/m/enterprises/{eid}/resources",
    "/m/enterprises/{eid}/risk-assessment",
    "/m/enterprises/{eid}/resource-investigation",
    "/m/enterprises/{eid}/plans",
    "/m/plans",
    "/m/plans/new",
    "/m/plans/{pid}/edit",
    "/m/plans/{pid}/versions",
    "/m/plans/{pid}/preview",
    "/m/settings",
    "/m/settings/profile",
    "/m/settings/password",
    "/m/chat",
]

# 桌面端存在、移动端路由表里没有的深链（手机上访问会发生什么）
DESKTOP_ONLY = [
    "/enterprises/{eid}/hazard",
    "/enterprises/{eid}/hazard/dashboard",
    "/enterprises/{eid}/major-hazard",
    "/enterprises/{eid}/work-ticket",
    "/enterprises/{eid}/org",
    "/enterprises/{eid}/emergency-org",
    "/enterprises/{eid}/risk-management/notice-cards",
    "/enterprises/{eid}/risk-management/workbench",
    "/enterprises/{eid}/risk-management/methods",
    "/settings/users",
    "/settings/regulations",
    "/settings/data-hub",
    "/settings/prompts",
    "/onboarding",
    "/platform/overview",
    "/chat",
]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    results = {"mobile": [], "desktop_only": [], "context": {}}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport=MOBILE,
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="zh-CN",
            user_agent=UA,
        )
        page = ctx.new_page()

        # 登录
        page.goto(BASE + "/m/login", wait_until="load", timeout=30000)
        page.wait_for_timeout(1200)
        page.fill('input[type="email"]', U)
        page.fill('input[type="password"]', P)
        page.locator('button:has-text("登录")').last.click()
        page.wait_for_timeout(4000)
        results["context"]["after_login"] = page.url
        token = page.evaluate("() => localStorage.getItem('access_token') || ''")
        results["context"]["token_len"] = len(token)

        # 取一家企业 + 一份预案 id（走前端同源 API）
        ids = page.evaluate(
            """async (tok) => {
              const h = {Authorization: 'Bearer ' + tok};
              const ents = await (await fetch('/api/v1/enterprises?page=1&page_size=1', {headers: h})).json();
              const list = ents?.data?.items || ents?.items || [];
              const eid = list[0]?.id || '';
              let pid = '';
              if (eid) {
                const ps = await (await fetch(`/api/v1/enterprises/${eid}/plans`, {headers: h})).json();
                const pl = ps?.data?.items || ps?.items || [];
                pid = pl[0]?.id || '';
              }
              let plan_from = 'enterprise';
              if (!pid) {
                // 兜底：全局取任意一份预案，保证 /m/plans/{id}/* 三条路由也能被探到
                const all = await (await fetch('/api/v1/plans?page=1&page_size=1', {headers: h})).json();
                const al = all?.data?.items || all?.items || [];
                pid = al[0]?.id || '';
                plan_from = 'global';
              }
              return {eid, pid, plan_from, name: list[0]?.name || ''};
            }""",
            token,
        )
        results["context"]["ids"] = ids

        def probe(path: str) -> dict:
            console: list[str] = []
            http4xx: list[str] = []
            failed: list[str] = []
            page.on("console", lambda m: console.append(f"{m.type}: {m.text[:200]}"))
            page.on(
                "response",
                lambda r: http4xx.append(f"{r.status} {r.request.method} {r.url[:120]}")
                if "/api/" in r.url and r.status >= 400
                else None,
            )
            page.on(
                "requestfailed",
                lambda r: failed.append(f"{r.method} {r.url[:120]} <- {r.failure}"),
            )
            try:
                page.goto(BASE + path, wait_until="load", timeout=30000)
            except Exception as exc:  # noqa: BLE001 - 探测脚本需记录任意失败
                return {"path": path, "error": str(exc)}
            page.wait_for_timeout(3500)
            try:
                text = page.locator("body").inner_text()
            except Exception:  # noqa: BLE001
                text = ""
            shots = [s for s in console if s.startswith("error")]
            return {
                "path": path,
                "final_url": page.url,
                "redirected": page.url.replace(BASE, "") != path,
                "text_len": len(text),
                "text_head": text.replace("\n", " | ")[:160],
                "console_error": shots[:4],
                "api_4xx": http4xx[:4],
                "request_failed": failed[:3],
            }

        for tpl in MOBILE_ROUTES:
            p = tpl.format(eid=ids.get("eid", ""), pid=ids.get("pid", ""))
            if "{eid}" in tpl and not ids.get("eid"):
                continue
            if "{pid}" in tpl and not ids.get("pid"):
                continue
            results["mobile"].append(probe(p))

        for tpl in DESKTOP_ONLY:
            p = tpl.format(eid=ids.get("eid", ""))
            results["desktop_only"].append(probe(p))

        # 关键页面截图（视觉复核用）
        for path, name in [
            (f"/m/enterprises/{ids.get('eid','')}", "m-enterprise-detail"),
            (f"/m/enterprises/{ids.get('eid','')}/risk-management", "m-risk-management"),
            (f"/m/enterprises/{ids.get('eid','')}/resources", "m-resources"),
            (f"/m/plans/{ids.get('pid','')}/edit", "m-plan-editor"),
            ("/m/dashboard", "m-dashboard"),
            ("/m/chat", "m-chat"),
        ]:
            if "//" in path or path.endswith("/"):
                continue
            page.goto(BASE + path, wait_until="load", timeout=30000)
            page.wait_for_timeout(2500)
            page.screenshot(path=os.path.join(OUT, f"{name}.png"), full_page=True)

        browser.close()

    with open(os.path.join(OUT, "mobile-coverage.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)

    print("=== context ===")
    print(json.dumps(results["context"], ensure_ascii=False))
    print("=== mobile routes ===")
    for it in results["mobile"]:
        print(
            "[{st}] {p} -> {u} len={l} cons_err={c} api4xx={a}".format(
                st="REDIR" if it.get("redirected") else "OK",
                p=it.get("path"),
                u=it.get("final_url", "").replace(BASE, ""),
                l=it.get("text_len"),
                c=len(it.get("console_error", [])),
                a=len(it.get("api_4xx", [])),
            )
        )
        if it.get("text_head"):
            print("      text: " + it["text_head"])
    print("=== desktop-only deep links on mobile UA ===")
    for it in results["desktop_only"]:
        print(
            "[{st}] {p} -> {u} len={l}".format(
                st="REDIR" if it.get("redirected") else "OK",
                p=it.get("path"),
                u=it.get("final_url", "").replace(BASE, ""),
                l=it.get("text_len"),
            )
        )
        if it.get("text_head"):
            print("      text: " + it["text_head"])


if __name__ == "__main__":
    main()
