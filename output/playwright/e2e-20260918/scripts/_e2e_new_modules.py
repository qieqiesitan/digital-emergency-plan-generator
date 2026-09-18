"""新增模块真实浏览器回归 + 跨用户越权实测（一次性脚本，只读）。"""

import json
import os
import re
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://172.26.0.3:5173")
OUT = "/app/exports/e2e-20260918"
U, P = "qa_e2e_test@test.com", "test123456"
OWN = "e62bb772-a29f-4e48-89a4-9182f13ca86f"          # qa_e2e_test 自己的企业
OTHER_TICKETS = "94804158-cc33-464d-9aef-025ec90226be"  # test@test.com 的企业（28 张票）
OTHER_HAZARD = "a1866bd9-5a30-43de-9c28-1853fd6164fa"  # 550614706@qq.com 的企业（3 个单元）

PAGES = [
    ("platform-overview", "/platform/overview"),
    ("ai-capabilities", "/settings/ai-capabilities"),
    ("datahub", "/settings/data-hub"),
    ("datahub-import", "/settings/data-hub/import"),
    ("mh-own-list", f"/enterprises/{OWN}/major-hazard"),
    ("mh-own-compute", f"/enterprises/{OWN}/major-hazard/compute"),
    ("mh-own-record", f"/enterprises/{OWN}/major-hazard/record"),
    ("ticket-own-list", f"/enterprises/{OWN}/work-ticket"),
    ("ticket-own-new", f"/enterprises/{OWN}/work-ticket/new"),
    ("ticket-own-approval", f"/enterprises/{OWN}/work-ticket/approval"),
    ("IDOR-ticket-other", f"/enterprises/{OTHER_TICKETS}/work-ticket"),
    ("IDOR-mh-other", f"/enterprises/{OTHER_HAZARD}/major-hazard"),
]

TICKET_WORDS = ("动火", "受限空间", "高处", "吊装", "临时用电", "动土", "断路", "盲板")
STATUS_WORDS = ("待提交", "审批中", "已通过", "已驳回", "已过期", "已完成")

results = []


def attach(page, rec):
    hs = {
        "console": lambda m: rec["console"].append(f"{m.type}: {m.text[:200]}")
        if m.type in ("error", "warning") else None,
        "pageerror": lambda e: rec["pageerror"].append(str(e)[:250]),
        "response": lambda r: rec["http4xx"].append(f"{r.status} {r.request.method} {r.url[:150]}")
        if r.status >= 400 else None,
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


def visit(page, name, path):
    rec = {"name": name, "path": path, "console": [], "pageerror": [], "http4xx": []}
    hs = attach(page, rec)
    t0 = time.time()
    try:
        page.goto(BASE + path, wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)
        body = page.locator("body").inner_text(timeout=10000)
        rec.update(final_url=page.url, text_len=len(body),
                   text_head=re.sub(r"\s+", " ", body)[:260],
                   forbidden="无权限访问" in body,
                   ticket_words=[w for w in TICKET_WORDS if w in body],
                   status_words=[w for w in STATUS_WORDS if w in body])
        page.screenshot(path=os.path.join(OUT, f"new-{name}.png"), full_page=True)
        rec["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:250]
    detach(page, hs)
    rec["ms"] = int((time.time() - t0) * 1000)
    results.append(rec)
    print(f"{name:22s} {rec['status']:5s} {rec['ms']:6d}ms len={rec.get('text_len')} "
          f"403页={'Y' if rec.get('forbidden') else 'N'} http4xx={len(rec['http4xx'])} "
          f"票种词={len(rec.get('ticket_words') or [])} 状态词={len(rec.get('status_words') or [])}", flush=True)
    return rec


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.goto(BASE + "/login", wait_until="load", timeout=40000)
        page.fill('input[id*="email"]', U)
        page.fill('input[type="password"]', P)
        page.click('button[type="submit"]')
        page.wait_for_timeout(4000)
        print("[login]", page.url, flush=True)
        for name, path in PAGES:
            visit(page, name, path)
        browser.close()
    with open(os.path.join(OUT, "summary-new-modules.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print("\n==== 汇总 ====")
    for r in results:
        print(f"{r['name']:22s} len={r.get('text_len')} forbidden={r.get('forbidden')} "
              f"tickets={r.get('ticket_words')} statuses={r.get('status_words')} "
              f"http4xx={r['http4xx'][:2]}")


if __name__ == "__main__":
    main()
