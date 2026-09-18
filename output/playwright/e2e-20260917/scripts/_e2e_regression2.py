"""E2E 补测：修正后的桌面路由 + 移动端 390px 已登录遍历 + Chat 流式。

用法（容器内）: python /app/exports/_e2e_regression2.py
产出: /app/exports/e2e-20260917/round2-*.png + summary-round2.json
"""

import json
import os
import re
import time

from playwright.sync_api import sync_playwright

BASE = "http://shuzihuayuan:8080"
OUT = "/app/exports/e2e-20260917"
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "e62bb772-a29f-4e48-89a4-9182f13ca86f"
ENT2 = "69b205cd-c316-47a7-89d7-cc6c6f402bee"
PLAN = "aa8244ab-ff8f-45a4-8814-15629041095f"

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

DESKTOP_PATHS = [
    ("ent-plans-list", f"/enterprises/{ENT}/plans"),
    ("ent-org", f"/enterprises/{ENT}/org"),
    ("hazard-plans", f"/enterprises/{ENT}/hazard/plans"),
    ("hazard-tasks", f"/enterprises/{ENT}/hazard/tasks"),
    ("hazard-templates", f"/enterprises/{ENT}/hazard/templates"),
    ("plan-preview", f"/plans/{PLAN}/preview"),
    ("risk-assessment-preview", f"/enterprises/{ENT}/risk-assessment/preview"),
    ("resource-investigation-preview", f"/enterprises/{ENT}/resource-investigation/preview"),
]

MOBILE_PATHS = [
    ("m-dashboard", "/m/dashboard"),
    ("m-enterprises", "/m/enterprises"),
    ("m-enterprise-detail", f"/m/enterprises/{ENT}"),
    ("m-enterprise-risk", f"/m/enterprises/{ENT}/risk-management"),
    ("m-enterprise-resources", f"/m/enterprises/{ENT}/resources"),
    ("m-enterprise-assessment", f"/m/enterprises/{ENT}/risk-assessment"),
    ("m-enterprise-investigation", f"/m/enterprises/{ENT}/resource-investigation"),
    ("m-enterprise-plans", f"/m/enterprises/{ENT2}/plans"),
    ("m-plans", "/m/plans"),
    ("m-plan-editor", f"/m/plans/{PLAN}/edit"),
    ("m-plan-versions", f"/m/plans/{PLAN}/versions"),
    ("m-plan-preview", f"/m/plans/{PLAN}/preview"),
    ("m-settings", "/m/settings"),
    ("m-profile", "/m/settings/profile"),
    ("m-chat", "/m/chat"),
    ("m-enterprise-new", "/m/enterprises/new"),
    ("m-plan-new", "/m/plans/new"),
]

results = []


def slug(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def attach(page, rec):
    hs = {
        "console": lambda m: rec["console"].append(f"{m.type}: {m.text[:300]}")
        if m.type in ("error", "warning") else None,
        "pageerror": lambda e: rec["pageerror"].append(str(e)[:400]),
        "requestfailed": lambda r: rec["requestfailed"].append(f"{r.method} {r.url[:160]} <- {r.failure}"),
        "response": lambda r: rec["http4xx"].append(f"{r.status} {r.url[:160]}") if r.status >= 400 else None,
    }
    for ev, h in hs.items():
        page.on(ev, h)
    return hs


def detach(page, hs):
    for ev, h in hs.items():
        try:
            page.remove_listener(ev, h)
        except Exception:  # noqa: BLE001
            pass


def visit(page, name, path, vp, full=False):
    rec = {"name": name, "path": path, "viewport": vp, "console": [], "pageerror": [],
           "requestfailed": [], "http4xx": []}
    hs = attach(page, rec)
    t0 = time.time()
    try:
        page.goto(BASE + path, wait_until="load", timeout=30000)
        page.wait_for_timeout(2600)
        body = page.locator("body").inner_text(timeout=8000)
        rec.update(final_url=page.url, text_len=len(body),
                   text_head=re.sub(r"\s+", " ", body)[:160],
                   spinner=page.locator(".ant-spin-spinning").count())
        if rec["spinner"]:
            page.wait_for_timeout(2500)
            rec["spinner_after_5s"] = page.locator(".ant-spin-spinning").count()
        rec["overflow_x"] = page.evaluate(
            "() => document.documentElement.scrollWidth > window.innerWidth + 1")
        shot = os.path.join(OUT, f"round2-{vp}-{slug(name)}.png")
        page.screenshot(path=shot, full_page=full)
        rec["screenshot"] = shot
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
    detach(page, hs)
    rec["ms"] = int((time.time() - t0) * 1000)
    results.append(rec)
    print(f"[{vp}] {name:30s} {rec['status']:5s} {rec['ms']:6d}ms "
          f"http4xx={len(rec['http4xx'])} consoleErr={len([c for c in rec['console'] if c.startswith('error')])}",
          flush=True)
    return rec


TABBAR_JS = """() => {
  const all = Array.from(document.querySelectorAll('*'));
  const tb = all.find(el => {
    const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
    return cs.position === 'fixed' && r.bottom >= window.innerHeight - 2
        && r.height > 40 && r.width > 200;
  });
  const out = {tabbarHeight: tb ? Math.round(tb.getBoundingClientRect().height) : null,
               tabbarTop: tb ? Math.round(tb.getBoundingClientRect().top) : null,
               overlapPx: null, maxBottom: null, bodyText: document.body.innerText || ''};
  if (!tb) return out;
  let maxBottom = 0;
  for (const el of all) {
    if (tb.contains(el) || el.contains(tb)) continue;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed' || r.height === 0 || r.width === 0) continue;
    if (r.bottom > maxBottom) maxBottom = r.bottom;
  }
  out.maxBottom = Math.round(maxBottom);
  out.overlapPx = Math.round(maxBottom - out.tabbarTop);
  out.hasFakeEmail = out.bodyText.includes('user@example.com');
  out.dupTitle = (out.bodyText.match(/工作台/g) || []).length;
  return out;
}"""


def mobile_login(page):
    page.goto(BASE + "/m/login", wait_until="load", timeout=30000)
    page.wait_for_timeout(1500)
    page.fill('input[type="email"]', U)
    page.fill('input[type="password"]', P)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    return page.url


def chat_stream(page):
    rec = {"name": "chat-stream", "console": [], "pageerror": [], "requestfailed": [], "http4xx": []}
    hs = attach(page, rec)
    try:
        page.goto(BASE + "/chat", wait_until="load", timeout=30000)
        page.wait_for_timeout(2500)
        if page.locator("textarea").count() == 0:
            page.click("text=新建对话")
            page.wait_for_timeout(2500)
        box = page.locator("textarea").first
        box.click()
        box.fill("请用一句话回复：流式测试")
        page.keyboard.press("Enter")
        samples, t0 = [], time.time()
        while time.time() - t0 < 75:
            page.wait_for_timeout(1500)
            txt = page.locator("body").inner_text()
            samples.append({"t": round(time.time() - t0, 1), "len": len(txt)})
            if len(samples) > 4 and samples[-1]["len"] == samples[-2]["len"] == samples[-3]["len"]:
                break
        rec["samples"] = samples
        rec["grow_steps"] = sum(1 for a, b in zip(samples, samples[1:]) if b["len"] > a["len"])
        rec["streaming_evidence"] = rec["grow_steps"] >= 2
        rec["text_tail"] = re.sub(r"\s+", " ", page.locator("body").inner_text())[-300:]
        page.screenshot(path=os.path.join(OUT, "round2-desktop-chat-stream.png"), full_page=True)
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:300]
    detach(page, hs)
    results.append(rec)
    print(f"[desktop] chat-stream grow_steps={rec.get('grow_steps')} err={rec.get('error','')}",
          flush=True)
    return rec


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport=DESKTOP, locale="zh-CN")
        page = ctx.new_page()
        page.goto(BASE + "/login", wait_until="load")
        page.fill('input[id*="email"]', U)
        page.fill('input[type="password"]', P)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)
        for name, path in DESKTOP_PATHS:
            visit(page, name, path, "desktop-1440", full=name.endswith("preview"))
        chat_stream(page)

        mctx = browser.new_context(viewport=MOBILE, device_scale_factor=3, is_mobile=True,
                                   has_touch=True, locale="zh-CN", user_agent=MOBILE_UA)
        mpage = mctx.new_page()
        try:
            url = mobile_login(mpage)
            results.append({"name": "m-login-flow", "status": "ok", "final_url": url})
            print(f"[mobile] login ok -> {url}", flush=True)
        except Exception as exc:  # noqa: BLE001
            results.append({"name": "m-login-flow", "status": "error", "error": str(exc)[:200]})
            print(f"[mobile] login FAILED {exc}", flush=True)
        structural = []
        for name, path in MOBILE_PATHS:
            r = visit(mpage, name, path, "mobile-390",
                      full=name in ("m-dashboard", "m-enterprises", "m-plans", "m-settings"))
            try:
                info = mpage.evaluate(TABBAR_JS)
                info.pop("bodyText", None)
                r["mobile_struct"] = info
                structural.append({"name": name, **info})
            except Exception as exc:  # noqa: BLE001
                r["mobile_struct_error"] = str(exc)[:200]
        results.append({"name": "mobile-structural", "items": structural})
        for item in structural:
            print(f"[mobile-struct] {item['name']:28s} tabbar={item.get('tabbarHeight')} "
                  f"overlapPx={item.get('overlapPx')} overflow?=see rec fakeEmail={item.get('hasFakeEmail')}",
                  flush=True)
        browser.close()
    with open(os.path.join(OUT, "summary-round2.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    bad = [r for r in results if r.get("status") == "error"]
    print(f"\n==== round2 汇总：{len(results)} 项，失败 {len(bad)} 项 ====")
    for r in bad:
        print("  FAIL", r.get("name"), r.get("error"))


if __name__ == "__main__":
    main()
