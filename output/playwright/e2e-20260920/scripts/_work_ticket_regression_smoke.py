"""桌面主要页面冒烟（只读）：确认本次作业票改动未波及其他模块。

判定：pageerror = 0 且无 5xx 才算通过；console error 单独统计并列出（便于人工判断）。

用法（仓库根目录）：
    python output/playwright/e2e-20260920/scripts/_work_ticket_regression_smoke.py
证据输出：同目录 work-ticket-regression-smoke.json
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
OUT = Path(__file__).resolve().parent
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"

ROUTES = [
    "/dashboard",
    "/enterprises",
    f"/enterprises/{ENT}",
    f"/enterprises/{ENT}/edit",
    f"/enterprises/{ENT}/org",
    f"/enterprises/{ENT}/emergency-org",
    f"/enterprises/{ENT}/risk-management/overview",
    f"/enterprises/{ENT}/risk-management/workbench",
    f"/enterprises/{ENT}/risk-management/control-list",
    f"/enterprises/{ENT}/risk-management/notice-cards",
    f"/enterprises/{ENT}/hazard",
    f"/enterprises/{ENT}/hazard/plans",
    f"/enterprises/{ENT}/hazard/tasks",
    f"/enterprises/{ENT}/major-hazard",
    f"/enterprises/{ENT}/modules/resources",
    f"/enterprises/{ENT}/modules/risk-assessment",
    f"/enterprises/{ENT}/modules/resource-investigation",
    f"/enterprises/{ENT}/work-ticket",
    f"/enterprises/{ENT}/work-ticket/new",
    f"/enterprises/{ENT}/work-ticket/batches/new",
    f"/enterprises/{ENT}/work-ticket/approval",
    "/plans",
    f"/enterprises/{ENT}/plans",
    "/settings/profile",
    "/settings/ai-config",
    "/settings/regulations",
    "/settings/ai-capabilities",
    "/platform/overview",
    "/chat",
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    page_errors: list[str] = []
    console_errors: list[str] = []
    http_5xx: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on("pageerror", lambda exc: page_errors.append(f"{page.url} :: {exc}"))
        page.on(
            "console",
            lambda msg: console_errors.append(f"{page.url} :: {msg.text[:160]}")
            if msg.type == "error"
            else None,
        )
        page.on(
            "response",
            lambda resp: http_5xx.append(f"{resp.status} {resp.url[:120]}")
            if resp.status >= 500
            else None,
        )

        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        page.wait_for_selector('input[placeholder="邮箱"]', timeout=30000)
        page.fill('input[placeholder="邮箱"]', U)
        page.fill('input[placeholder="密码"]', P)
        page.get_by_role("button", name=re.compile(r"登\s*录")).first.click()
        page.wait_for_timeout(4000)

        for route in ROUTES:
            entry = {"route": route}
            try:
                before = len(page_errors)
                resp = page.goto(BASE + route, wait_until="load", timeout=40000)
                page.wait_for_timeout(1800)
                entry["status"] = resp.status if resp else None
                entry["text_len"] = len(page.inner_text("body"))
                entry["pageerror"] = len(page_errors) > before
                entry["ok"] = (
                    (entry["status"] or 0) < 400
                    and entry["text_len"] > 40
                    and not entry["pageerror"]
                )
            except Exception as exc:
                entry["ok"] = False
                entry["error"] = f"{type(exc).__name__}: {str(exc)[:100]}"
            results.append(entry)

        page.screenshot(path=str(OUT / "work-ticket-smoke-last.png"), full_page=False)
        browser.close()

    failed = [r for r in results if not r["ok"]]
    checks = {
        "all_routes_ok": len(failed) == 0,
        "no_page_error": len(page_errors) == 0,
        "no_5xx": len(http_5xx) == 0,
    }
    (OUT / "work-ticket-regression-smoke.json").write_text(
        json.dumps(
            {
                "routes": results,
                "failed": failed,
                "page_errors": page_errors[:10],
                "console_errors": console_errors[:10],
                "http_5xx": http_5xx[:10],
                "checks": checks,
                "all_passed": all(checks.values()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({**checks, "route_count": len(results), "failed_count": len(failed)}, ensure_ascii=False, indent=2))
    if failed:
        print("failed routes:", [r["route"] for r in failed])
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
