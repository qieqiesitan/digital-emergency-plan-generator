"""真实浏览器端到端回归（一次性诊断脚本，不修改业务代码）。

用法（容器内）:
    python /app/exports/_e2e_regression.py user     # 以普通用户角色扫常规页面 + 403 断言
    python /app/exports/_e2e_regression.py super    # 以管理员角色扫全部设置页

产出:
    /app/exports/e2e-20260917/<name>.png            截图
    /app/exports/e2e-20260917/summary-<mode>.json   结构化结果
"""

import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://shuzihuayuan:8080")
OUT = "/app/exports/e2e-20260917"
U = "qa_e2e_test@test.com"
P = "test123456"

ENT = "e62bb772-a29f-4e48-89a4-9182f13ca86f"          # qa_e2e_test 名下企业（空数据态）
PLAN = "aa8244ab-ff8f-45a4-8814-15629041095f"          # 该账号下有 4 个已填章节的草稿预案
RISK_CARD_TOKEN = "9bf098ff1b5441c52150bd059f618b81586a841547c295c63715623994dc4985"
PUBLIC_RISK_TOKEN = "854352eaacbe6bf7635f47c1d7694ccadf5cc79389e9865b45692f27ed3d5d99"
HAZARD_TOKEN = "47679c4b8781243fc614b596436ddf8d2d5b087c058f52a6e7684f4c20c92879"

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}

COMMON_PAGES = [
    ("dashboard", "/dashboard"),
    ("chat", "/chat"),
    ("enterprises", "/enterprises"),
    ("enterprise-new", "/enterprises/new"),
    ("enterprise-cockpit", f"/enterprises/{ENT}"),
    ("enterprise-edit", f"/enterprises/{ENT}/edit"),
    ("ent-modules", f"/enterprises/{ENT}/modules/overview"),
    ("risk-overview", f"/enterprises/{ENT}/risk-management/overview"),
    ("risk-workbench", f"/enterprises/{ENT}/risk-management/workbench"),
    ("risk-control-list", f"/enterprises/{ENT}/risk-management/control-list"),
    ("risk-notice-cards", f"/enterprises/{ENT}/risk-management/notice-cards"),
    ("risk-publicity", f"/enterprises/{ENT}/risk-management/publicity"),
    ("risk-methods", f"/enterprises/{ENT}/risk-management/methods"),
    ("risk-data-dicts", f"/enterprises/{ENT}/risk-management/data-dicts"),
    ("hazard-plan", f"/enterprises/{ENT}/hazard/plan"),
    ("hazard-task", f"/enterprises/{ENT}/hazard/task"),
    ("hazard-dashboard", f"/enterprises/{ENT}/hazard/dashboard"),
    ("hazard-template", f"/enterprises/{ENT}/hazard/template"),
    ("hazard-publicity", f"/enterprises/{ENT}/hazard/publicity"),
    ("plans-cards", "/plans"),
    ("plans-list", "/plans/list"),
    ("plan-create", "/plans/new"),
    ("plan-editor", f"/plans/{PLAN}/edit"),
    ("plan-versions", f"/plans/{PLAN}/versions"),
    ("plan-export", f"/plans/{PLAN}/export"),
    ("settings-profile", "/settings/profile"),
    ("settings-ai", "/settings/ai-config"),
    ("not-found", "/definitely-not-exists-xyz"),
]

USER_ONLY_FORBIDDEN = [
    ("settings-users-403", "/settings/users"),
    ("settings-roles-403", "/settings/roles"),
    ("settings-regulations-403", "/settings/regulations"),
]

SUPER_PAGES = [
    ("settings-users", "/settings/users"),
    ("settings-roles", "/settings/roles"),
    ("settings-system", "/settings/system"),
    ("settings-prompts", "/settings/prompts"),
    ("settings-third-party", "/settings/third-party-config"),
    ("settings-regulations", "/settings/regulations"),
    ("settings-data-dicts", "/settings/data-dicts"),
    ("settings-chemical", "/settings/chemical-library"),
]

MOBILE_PAGES = [
    ("m-dashboard", "/m/dashboard"),
    ("m-enterprises", "/m/enterprises"),
    ("m-plans", "/m/plans"),
    ("m-settings", "/m/settings"),
]

PUBLIC_PAGES = [
    ("public-risk-card", f"/r/{RISK_CARD_TOKEN}"),
    ("public-risk-map", f"/p/risk/{PUBLIC_RISK_TOKEN}"),
    ("public-hazard", f"/h/{HAZARD_TOKEN}"),
]

results = []


def slug(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def attach(page, rec):
    handlers = {
        "console": lambda m: rec["console"].append(f"{m.type}: {m.text[:300]}")
        if m.type in ("error", "warning") else None,
        "pageerror": lambda e: rec["pageerror"].append(str(e)[:400]),
        "requestfailed": lambda r: rec["requestfailed"].append(
            f"{r.method} {r.url[:200]} <- {r.failure}"),
        "response": lambda r: rec["http4xx"].append(f"{r.status} {r.url[:200]}")
        if r.status >= 400 else None,
    }
    for event, handler in handlers.items():
        page.on(event, handler)
    return handlers


def detach(page, handlers):
    for event, handler in (handlers or {}).items():
        try:
            page.remove_listener(event, handler)
        except Exception:  # noqa: BLE001
            pass


def visit(page, mode, name, path, viewport_name, full=False, note="", extra=None):
    rec = {
        "mode": mode, "name": name, "path": path, "viewport": viewport_name,
        "console": [], "pageerror": [], "requestfailed": [], "http4xx": [],
        "note": note, "extra": extra or {},
    }
    handlers = attach(page, rec)
    t0 = time.time()
    try:
        page.goto(BASE + path, wait_until="load", timeout=30000)
        page.wait_for_timeout(2500)
        rec["final_url"] = page.url
        rec["title"] = page.title()
        body = page.locator("body").inner_text(timeout=8000)
        rec["text_len"] = len(body)
        rec["text_head"] = re.sub(r"\s+", " ", body)[:200]
        rec["spinner"] = page.locator(".ant-spin-spinning").count()
        if rec["spinner"]:
            page.wait_for_timeout(2500)
            rec["spinner_after_5s"] = page.locator(".ant-spin-spinning").count()
        rec["overflow_x"] = page.evaluate(
            "() => document.documentElement.scrollWidth > window.innerWidth + 1")
        shot = os.path.join(OUT, f"{viewport_name}-{slug(name)}.png")
        page.screenshot(path=shot, full_page=full)
        rec["screenshot"] = shot
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 - 单页失败不影响整体回归
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:400]
        try:
            page.screenshot(path=os.path.join(OUT, f"{viewport_name}-{slug(name)}-ERR.png"))
        except Exception:
            pass
    detach(page, handlers)
    rec["ms"] = int((time.time() - t0) * 1000)
    results.append(rec)
    print(f"[{viewport_name}] {name:32s} {rec['status']:5s} "
          f"{rec['ms']:6d}ms {rec.get('error', '')}"
          f"{' HTTP4xx=' + str(len(rec['http4xx'])) if rec['http4xx'] else ''}"
          f"{' consoleErr=' + str(len([c for c in rec['console'] if c.startswith('error')])) if rec['console'] else ''}",
          flush=True)
    return rec


def login(page):
    page.goto(BASE + "/login", wait_until="load", timeout=30000)
    page.fill('input[id*="email"]', U)
    page.fill('input[type="password"]', P)
    page.click('button[type="submit"]')
    page.wait_for_url(re.compile(r"/(dashboard|enterprises)"), timeout=20000)
    page.wait_for_timeout(1200)


def check_login_page(page):
    rec = {"name": "login-page", "path": "/login", "viewport": "desktop-1440"}
    try:
        page.goto(BASE + "/login", wait_until="load", timeout=30000)
        page.wait_for_timeout(1500)
        body = page.locator("body").inner_text()
        rec["has_forgot_password"] = "忘记密码" in body
        rec["text_head"] = re.sub(r"\s+", " ", body)[:200]
        page.screenshot(path=os.path.join(OUT, "desktop-login-page.png"))
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = str(exc)[:300]
    results.append(rec)
    print(f"[desktop] login-page has_forgot_password={rec.get('has_forgot_password')}", flush=True)


def mobile_structural_checks(page):
    return page.evaluate(
        """() => {
            const out = {tabbar: null, contentPaddingBottom: null, dupTitle: 0};
            const els = Array.from(document.querySelectorAll('*'));
            for (const el of els) {
                const cs = getComputedStyle(el);
                if (cs.position === 'fixed' && cs.bottom === '0px'
                    && el.getBoundingClientRect().height > 40
                    && el.getBoundingClientRect().width > 200) {
                    out.tabbar = {h: Math.round(el.getBoundingClientRect().height),
                                  cls: (el.className || '').toString().slice(0, 80)};
                    break;
                }
            }
            const main = document.querySelector('main') || document.body;
            out.contentPaddingBottom = getComputedStyle(main).paddingBottom;
            out.bodyText = document.body.innerText || '';
            out.dupTitle = (out.bodyText.match(/工作台/g) || []).length;
            out.hasFakeEmail = out.bodyText.includes('user@example.com');
            return out;
        }"""
    )


def targeted_text_checks(page, mode):
    checks = {}
    # A19：隐患驾驶舱单位重复
    try:
        page.goto(BASE + f"/enterprises/{ENT}/hazard/dashboard", wait_until="load", timeout=30000)
        page.wait_for_timeout(2500)
        txt = page.locator("body").inner_text()
        checks["A19_hazard_unit_dup"] = bool(re.search(r"条\s*条|个\s*个|条/0?个", txt))
        checks["A20_us_date_format"] = bool(re.search(r"\d{1,2}/\d{1,2}/\d{4}.*(AM|PM)", txt))
        checks["A8_emoji_in_hazard"] = any(e in txt for e in ("🤖", "⏳", "❗️", "⚠️"))
    except Exception as exc:  # noqa: BLE001
        checks["hazard_checks_error"] = str(exc)[:200]
    if mode == "super":
        # A9：提示词分类英文 / A17：数据字典 JSON 裸露
        for key, path, needles in (
            ("A9_prompt_category_english", "/settings/prompts", ("emergency_diagram",)),
            ("A17_datadict_json_raw", "/settings/data-dicts", ('{"level"', '"dict_type"')),
        ):
            try:
                page.goto(BASE + path, wait_until="load", timeout=30000)
                page.wait_for_timeout(2500)
                txt = page.locator("body").inner_text()
                checks[key] = any(n in txt for n in needles)
            except Exception as exc:  # noqa: BLE001
                checks[key + "_error"] = str(exc)[:200]
    # A8：编辑器 emoji
    try:
        page.goto(BASE + f"/plans/{PLAN}/edit", wait_until="load", timeout=30000)
        page.wait_for_timeout(3000)
        txt = page.locator("body").inner_text()
        checks["A8_emoji_in_editor"] = any(e in txt for e in ("🤖", "⏳", "❗️"))
        checks["editor_text_len"] = len(txt)
    except Exception as exc:  # noqa: BLE001
        checks["editor_checks_error"] = str(exc)[:200]
    return checks


def chat_stream_probe(page):
    """在真实浏览器里发一条消息，验证 SSE 流式是否逐段到达（不是一次性返回）。"""
    rec = {"name": "chat-stream", "path": "/chat"}
    try:
        page.goto(BASE + "/chat", wait_until="load", timeout=30000)
        page.wait_for_timeout(2500)
        box = page.locator("textarea").first
        box.click()
        box.fill("请用一句话回复：流式测试")
        page.keyboard.press("Enter")
        samples = []
        t0 = time.time()
        while time.time() - t0 < 60:
            page.wait_for_timeout(1500)
            txt = page.locator("body").inner_text()
            samples.append({"t": round(time.time() - t0, 1), "len": len(txt)})
            if len(samples) > 3 and samples[-1]["len"] == samples[-2]["len"] == samples[-3]["len"]:
                break
        rec["samples"] = samples
        rec["grew_after_first_sample"] = samples[-1]["len"] > samples[0]["len"]
        grew_steps = sum(1 for a, b in zip(samples, samples[1:]) if b["len"] > a["len"])
        rec["grow_steps"] = grew_steps
        rec["streaming_evidence"] = grew_steps >= 2
        page.screenshot(path=os.path.join(OUT, "desktop-chat-stream.png"), full_page=True)
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = str(exc)[:300]
    rec["ms"] = int(0)
    results.append(rec)
    print(f"[desktop] chat-stream grow_steps={rec.get('grow_steps')} "
          f"streaming={rec.get('streaming_evidence')}", flush=True)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "user"
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        # ── 桌面 ──
        ctx = browser.new_context(viewport=DESKTOP, locale="zh-CN")
        page = ctx.new_page()
        check_login_page(page)
        try:
            login(page)
            results.append({"name": "login-flow", "status": "ok", "path": "/login",
                            "final_url": page.url, "viewport": "desktop-1440"})
            print(f"[desktop] login-flow ok -> {page.url}", flush=True)
        except Exception as exc:  # noqa: BLE001
            results.append({"name": "login-flow", "status": "error", "error": str(exc)[:300]})
            print(f"[desktop] login-flow FAILED {exc}", flush=True)
        for name, path in COMMON_PAGES:
            if name in ("dashboard", "enterprises", "plan-editor"):
                full = True
            else:
                full = False
            visit(page, mode, name, path, "desktop-1440", full=full)
        if mode == "user":
            for name, path in USER_ONLY_FORBIDDEN:
                r = visit(page, mode, name, path, "desktop-1440")
                r["extra"]["expect_403_text"] = "无权限访问" in (r.get("text_head", "") or "")
                r["extra"]["forbidden_ok"] = r["extra"]["expect_403_text"] or "无权限" in (r.get("text_head", "") or "")
                print(f"    403 check: {r['extra']['forbidden_ok']}", flush=True)
        else:
            for name, path in SUPER_PAGES:
                visit(page, mode, name, path, "desktop-1440")
        results.append({"name": "targeted-text-checks", "mode": mode,
                        "checks": targeted_text_checks(page, mode)})
        print(f"[desktop] targeted checks: {json.dumps(results[-1]['checks'], ensure_ascii=False)}", flush=True)
        chat_stream_probe(page)
        # ── 移动端 390px ──
        mctx = browser.new_context(viewport=MOBILE, device_scale_factor=3, is_mobile=True,
                                   has_touch=True, locale="zh-CN",
                                   user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                                               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                                               "Mobile/15E148 Safari/604.1"))
        mpage = mctx.new_page()
        try:
            mpage.goto(BASE + "/m/login", wait_until="load", timeout=30000)
            mpage.wait_for_timeout(1500)
            body = mpage.locator("body").inner_text()
            if "邮箱" in body or "登录" in body:
                mpage.fill('input[id*="email"]', U)
                mpage.fill('input[type="password"]', P)
                mpage.click('button[type="submit"]')
                mpage.wait_for_timeout(3000)
            print(f"[mobile] login -> {mpage.url}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[mobile] login route fallback: {exc}", flush=True)
        for name, path in MOBILE_PAGES:
            visit(mpage, mode, name, path, "mobile-390")
        try:
            struct = mobile_structural_checks(mpage)
            results.append({"name": "mobile-structural", "data": {k: v for k, v in struct.items()
                                                                  if k != "bodyText"},
                            "hasFakeEmail": struct.get("hasFakeEmail"),
                            "dupTitleCount": struct.get("dupTitle")})
            print(f"[mobile] structural: {json.dumps({k: v for k, v in struct.items() if k != 'bodyText'}, ensure_ascii=False)}",
                  flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[mobile] structural error: {exc}", flush=True)
        # ── 公开页（无登录态） ──
        pctx = browser.new_context(viewport=DESKTOP, locale="zh-CN")
        ppage = pctx.new_page()
        for name, path in PUBLIC_PAGES:
            visit(ppage, mode, name, path, "public-1440", full=False)
        browser.close()
    with open(os.path.join(OUT, f"summary-{mode}.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    bad = [r for r in results if r.get("status") == "error"]
    print(f"\n==== 汇总[{mode}]：{len(results)} 项检查，失败 {len(bad)} 项 ====")
    for r in bad:
        print("  FAIL", r.get("name"), r.get("error"))


if __name__ == "__main__":
    main()
