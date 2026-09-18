"""E2E 补测第三轮：移动端 390px 已登录遍历 + Chat 流式增量采样。

用法（容器内）: python /app/exports/_e2e_regression3.py
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

MOBILE_PATHS = [
    ("m-dashboard", "/m/dashboard", True),
    ("m-enterprises", "/m/enterprises", True),
    ("m-enterprise-detail", f"/m/enterprises/{ENT}", False),
    ("m-enterprise-risk", f"/m/enterprises/{ENT}/risk-management", False),
    ("m-enterprise-resources", f"/m/enterprises/{ENT}/resources", False),
    ("m-enterprise-assessment", f"/m/enterprises/{ENT}/risk-assessment", False),
    ("m-enterprise-investigation", f"/m/enterprises/{ENT}/resource-investigation", False),
    ("m-enterprise-plans", f"/m/enterprises/{ENT2}/plans", False),
    ("m-plans", "/m/plans", True),
    ("m-plan-editor", f"/m/plans/{PLAN}/edit", False),
    ("m-plan-versions", f"/m/plans/{PLAN}/versions", False),
    ("m-plan-preview", f"/m/plans/{PLAN}/preview", False),
    ("m-settings", "/m/settings", True),
    ("m-profile", "/m/settings/profile", False),
    ("m-chat", "/m/chat", False),
    ("m-enterprise-new", "/m/enterprises/new", False),
    ("m-plan-new", "/m/plans/new", False),
]

LAYOUT_JS = """() => {
  const all = Array.from(document.querySelectorAll('*'));
  const fixedBottom = all.filter(el => {
    const r = el.getBoundingClientRect();
    return getComputedStyle(el).position === 'fixed' && r.bottom >= window.innerHeight - 2
        && r.height > 30 && r.width > 150;
  });
  const nav = all.filter(el => el.tagName === 'NAV' || el.getAttribute('role') === 'tablist');
  const out = {
    fixedBottomCount: fixedBottom.length,
    fixedBottomHeight: fixedBottom.length ? Math.round(fixedBottom[0].getBoundingClientRect().height) : null,
    navCount: nav.length,
    navHeight: nav.length ? Math.round(nav[0].getBoundingClientRect().height) : null,
    innerHeight: window.innerHeight,
    scrollHeight: document.body.scrollHeight,
    scrollHeightErr: Math.abs(document.body.scrollHeight - window.innerHeight),
    bodyText: document.body.innerText || ''
  };
  // 滚动到底部后，最后一个内容元素是否被固定底栏遮住
  window.scrollTo(0, document.body.scrollHeight);
  const anchor = fixedBottom[0] || nav[0];
  if (anchor && anchor.getBoundingClientRect().height > 0) {
    const top = anchor.getBoundingClientRect().top;
    let maxBottom = 0;
    for (const el of all) {
      if (anchor.contains(el) || el.contains(anchor)) continue;
      const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
      if (cs.position === 'fixed' || r.height === 0 || r.width === 0) continue;
      if (r.bottom > maxBottom) maxBottom = r.bottom;
    }
    out.overlapPx = Math.round(maxBottom - top);
  }
  out.hasFakeEmail = out.bodyText.includes('user@example.com');
  out.dupWorkbench = (out.bodyText.match(/工作台/g) || []).length;
  return out;
}"""

results = []


def slug(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)


def attach(page, rec):
    hs = {
        "console": lambda m: rec["console"].append(f"{m.type}: {m.text[:250]}")
        if m.type in ("error", "warning") else None,
        "pageerror": lambda e: rec["pageerror"].append(str(e)[:300]),
        "requestfailed": lambda r: rec["requestfailed"].append(f"{r.method} {r.url[:150]} <- {r.failure}"),
        "response": lambda r: rec["http4xx"].append(f"{r.status} {r.url[:150]}") if r.status >= 400 else None,
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
                   overflow_x=page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 1"))
        page.screenshot(path=os.path.join(OUT, f"round3-{vp}-{slug(name)}.png"), full_page=full)
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:250]
    detach(page, hs)
    rec["ms"] = int((time.time() - t0) * 1000)
    results.append(rec)
    print(f"[{vp}] {name:30s} {rec['status']:5s} {rec['ms']:6d}ms text={rec.get('text_len')} "
          f"http4xx={len(rec['http4xx'])}", flush=True)
    return rec


def chat_probe(page):
    """打开会话 → 发消息 → 每 400ms 采样最后一条助手消息文本长度，直到稳定。"""
    rec = {"name": "chat-stream-v2", "console": [], "pageerror": [], "requestfailed": [], "http4xx": []}
    hs = attach(page, rec)
    try:
        page.goto(BASE + "/chat", wait_until="load", timeout=30000)
        page.wait_for_timeout(2500)
        if page.locator("textarea").count() == 0:
            page.click("text=新建对话")
            page.wait_for_timeout(2500)
        box = page.locator("textarea").first
        box.click()
        marker = f"流式校验{int(time.time()) % 100000}"
        box.fill(f"请只回复这串字符：{marker}")
        page.keyboard.press("Enter")
        series, t0, last_change = [], time.time(), time.time()
        while time.time() - t0 < 90:
            page.wait_for_timeout(400)
            # 抓取聊天消息区域里最后一条助手消息的文本
            txt = page.evaluate(
                """() => {
                    const nodes = Array.from(document.querySelectorAll('div'))
                        .filter(d => d.children.length === 0 && (d.innerText || '').trim().length > 0);
                    const tail = nodes.filter(d => !d.closest('aside')).map(d => d.innerText.trim());
                    return tail.slice(-3).join(' | ');
                }"""
            )
            ln = len(txt)
            series.append({"t": round(time.time() - t0, 2), "len": ln})
            if len(series) > 2 and series[-1]["len"] != series[-2]["len"]:
                last_change = time.time()
            if marker in txt:
                break
            if time.time() - last_change > 20:
                break
        rec["series"] = series[-40:]
        rec["final_text"] = txt[:300]
        rec["marker_found"] = marker in txt
        rec["distinct_lengths"] = len({s["len"] for s in series})
        rec["grow_steps"] = sum(1 for a, b in zip(series, series[1:]) if b["len"] > a["len"])
        rec["streaming_evidence"] = rec["marker_found"] and rec["distinct_lengths"] >= 4
        page.screenshot(path=os.path.join(OUT, "round3-desktop-chat.png"), full_page=True)
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:250]
    detach(page, hs)
    results.append(rec)
    print(f"[desktop] chat-v2 marker_found={rec.get('marker_found')} "
          f"distinct_lengths={rec.get('distinct_lengths')} "
          f"streaming={rec.get('streaming_evidence')}", flush=True)
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
        chat_probe(page)

        mctx = browser.new_context(viewport=MOBILE, device_scale_factor=3, is_mobile=True,
                                   has_touch=True, locale="zh-CN", user_agent=MOBILE_UA)
        m = mctx.new_page()
        m.goto(BASE + "/m/login", wait_until="load", timeout=30000)
        m.wait_for_timeout(1800)
        m.screenshot(path=os.path.join(OUT, "round3-mobile-login.png"), full_page=True)
        m.fill('input[type="email"]', U)
        m.fill('input[type="password"]', P)
        m.locator('button:has-text("登录")').last.click()
        m.wait_for_timeout(5000)
        login_url = m.url
        results.append({"name": "m-login-flow", "status": "ok" if "/m/login" not in login_url else "suspect",
                        "final_url": login_url})
        print(f"[mobile] login -> {login_url}", flush=True)
        layout = []
        for name, path, full in MOBILE_PATHS:
            r = visit(m, name, path, "mobile-390", full=full)
            try:
                info = m.evaluate(LAYOUT_JS)
                body = info.pop("bodyText", "")
                info["bodyTextHead"] = re.sub(r"\s+", " ", body)[:120]
                r["layout"] = info
                layout.append({"name": name, **info})
            except Exception as exc:  # noqa: BLE001
                r["layout_error"] = str(exc)[:150]
        results.append({"name": "mobile-layout", "items": layout})
        for it in layout:
            print(f"[m-layout] {it['name']:28s} fixedBottom={it.get('fixedBottomHeight')} "
                  f"nav={it.get('navHeight')} overlapPx={it.get('overlapPx')} "
                  f"fakeEmail={it.get('hasFakeEmail')} dupTitle={it.get('dupWorkbench')}", flush=True)
        browser.close()
    with open(os.path.join(OUT, "summary-round3.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
