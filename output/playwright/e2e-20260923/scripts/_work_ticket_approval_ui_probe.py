"""开票页审批链预检的界面实测（浏览器）。

背景（2026-09-23 用户实测）：特级动火票提交后卡在审批中、不在任何人待办里，
而提交前毫无提示。修完之后，进开票向导第 0 步就应该直接看到红色警告。

本探针用一个"没有任何组织架构与成员"的空白企业复现该场景，
断言第 0 步出现「无人可签」提示并截图；结束时删除该临时企业。

用法（仓库根目录）：
    python output/playwright/e2e-20260923/scripts/_work_ticket_approval_ui_probe.py
证据输出：同目录 work-ticket-approval-ui.json + work-ticket-approval-warning.png
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

API = "http://localhost:8000/api/v1"
BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
OUT = Path(__file__).resolve().parent
USER = ("qa_e2e_test@test.com", "test123456")


def api(method: str, path: str, body: dict | None = None, token: str | None = None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def click_button(page, text: str) -> None:
    page.get_by_role("button", name=re.compile(r"\s*".join(text))).first.click(timeout=15000)


def main() -> int:
    errors: list[str] = []
    checks: dict[str, bool] = {}
    detail: dict = {}
    enterprise_id = ""

    token = api("POST", "/auth/login", {"email": USER[0], "password": USER[1]})[1]["data"][
        "access_token"
    ]
    status, created = api("POST", "/enterprises", {"name": "探针-审批提示-可删"}, token)
    checks["blank_enterprise_created"] = status == 201
    enterprise_id = created["data"]["id"] if status == 201 else ""

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on(
            "console",
            lambda msg: errors.append(f"console:{msg.text[:120]}")
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))

        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        page.wait_for_selector('input[placeholder="邮箱"]', timeout=30000)
        page.fill('input[placeholder="邮箱"]', USER[0])
        page.fill('input[placeholder="密码"]', USER[1])
        click_button(page, "登录")
        page.wait_for_timeout(4000)

        if enterprise_id:
            page.goto(
                f"{BASE}/enterprises/{enterprise_id}/work-ticket/new",
                wait_until="load",
                timeout=40000,
            )
            page.wait_for_timeout(4000)
            body = page.inner_text("body")
            detail["step0_snippet"] = body[:600]
            checks["warning_visible"] = "无人可签" in body
            checks["warning_explains_role"] = "主管领导" in body
            checks["warning_gives_action"] = "组织架构" in body
            page.screenshot(
                path=str(OUT / "work-ticket-approval-warning.png"), full_page=True
            )

        checks["no_console_error"] = len(errors) == 0
        detail["errors"] = errors[:5]
        browser.close()

    if enterprise_id:
        api("DELETE", f"/enterprises/{enterprise_id}", token=token)
        detail["cleaned_enterprise_id"] = enterprise_id

    (OUT / "work-ticket-approval-ui.json").write_text(
        json.dumps(
            {"checks": checks, "detail": detail, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
