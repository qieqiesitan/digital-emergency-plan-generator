"""向导「步骤状态 + 草稿续填 + 提交跳转」实测（浏览器）。

对应用户 2026-09-21 的两条反馈：
  1. 前面没表态却能一路走到提交 —— 现在步骤条显示「待补 N 项」，提交失败跳到出问题的步骤
  2. 草稿只能存不能改 —— 现在列表页有「继续填写」，点进去回填草稿内容

顺序上先验草稿链路、把「提交失败跳转」放在最后一步（跳转后页面很长，不再继续操作，避免误判）。

用法（仓库根目录）：
    python output/playwright/e2e-20260921/scripts/_work_ticket_step_draft_probe.py
证据输出：同目录 work-ticket-step-draft.json（含两张截图）
探针会创建一张草稿票用于验证，结束时按 id 清理。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
OUT = Path(__file__).resolve().parent
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
MARK = "探针草稿-步骤验证"
PSQL = [
    "docker", "exec", "emergency-plan-db", "psql", "-U", "postgres",
    "-d", "emergency_plan", "-tA", "-c",
]


def click_button(page, text: str, timeout: int = 15000) -> None:
    """antd 会给两字按钮插空格，故用允许空白的正则；超时抛出由调用方决定。"""
    page.get_by_role("button", name=re.compile(r"\s*".join(text))).first.click(
        timeout=timeout
    )


def sql(query: str) -> str:
    return subprocess.run(
        PSQL + [query], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout.strip()


def main() -> int:
    errors: list[str] = []
    checks: dict[str, bool] = {}
    detail: dict = {}
    draft_id = ""

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
        page.fill('input[placeholder="邮箱"]', U)
        page.fill('input[placeholder="密码"]', P)
        click_button(page, "登录")
        page.wait_for_timeout(4000)

        # ── 1) 步骤条显示待补项（新票还什么都没填） ──
        page.goto(f"{BASE}/enterprises/{ENT}/work-ticket/new", wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)
        checks["step_bar_shows_missing"] = "待补" in page.inner_text("body")

        click_button(page, "下一步")  # → 第 1 步
        page.wait_for_timeout(2000)
        page.fill('input[placeholder="作业申请单位"]', MARK)
        page.wait_for_timeout(800)

        # ── 2) 未填完也允许继续（放行），但给出提示 ──
        click_button(page, "下一步")
        page.wait_for_timeout(1500)
        detail["advance_hint"] = "未完成" in page.inner_text("body")
        for _ in range(3):  # → 第 5 步
            click_button(page, "下一步")
            page.wait_for_timeout(1200)
        checks["advance_allowed_with_hint"] = detail["advance_hint"]

        # ── 3) 保存草稿 → 列表页出现「继续填写」 ──
        click_button(page, "保存草稿")
        page.wait_for_timeout(2500)
        draft_id = sql(
            "SELECT id FROM work_ticket_instances "
            f"WHERE enterprise_id = '{ENT}' AND status = 'draft' "
            f"AND values->>'applicant_unit' = '{MARK}' ORDER BY created_at DESC LIMIT 1;"
        )
        detail["draft_id"] = draft_id
        checks["draft_created"] = bool(draft_id)

        page.goto(f"{BASE}/enterprises/{ENT}/work-ticket", wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)
        checks["list_has_continue_entry"] = "继续填写" in page.inner_text("body")
        page.screenshot(path=str(OUT / "work-ticket-draft-list.png"), full_page=True)

        # ── 4) 点「继续填写」应回填草稿内容 ──
        if draft_id:
            page.goto(
                f"{BASE}/enterprises/{ENT}/work-ticket/{draft_id}/edit",
                wait_until="load",
                timeout=40000,
            )
            page.wait_for_timeout(4500)
            click_button(page, "下一步")
            page.wait_for_timeout(2200)
            value = page.input_value('input[placeholder="作业申请单位"]')
            body = page.inner_text("body")
            detail["refilled_applicant_unit"] = value
            detail["draft_loaded_hint"] = "已加载草稿" in body
            checks["draft_values_refilled"] = value == MARK
            checks["draft_loaded_hint_visible"] = detail["draft_loaded_hint"]

        # ── 5) 新票走到第 5 步提交：应跳到第一个出问题的步骤（最后一步，不再继续操作） ──
        page.goto(f"{BASE}/enterprises/{ENT}/work-ticket/new", wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)
        click_button(page, "下一步")
        page.wait_for_timeout(1800)
        page.fill('input[placeholder="作业申请单位"]', MARK)
        for _ in range(4):
            click_button(page, "下一步")
            page.wait_for_timeout(1200)
        click_button(page, "提交审批")
        page.wait_for_timeout(2500)
        after_submit = page.inner_text("body")
        detail["after_submit_snippet"] = after_submit[:300]
        checks["jumped_to_problem_step"] = "本步还有" in after_submit
        checks["jump_toast_shown"] = "已跳到" in after_submit
        page.screenshot(path=str(OUT / "work-ticket-step-missing.png"), full_page=True)

        checks["no_console_error"] = len(errors) == 0
        detail["errors"] = errors[:5]
        browser.close()

    if draft_id:
        sql(f"DELETE FROM work_ticket_instances WHERE id = '{draft_id}';")
        detail["cleaned"] = (
            sql(f"SELECT count(*) FROM work_ticket_instances WHERE id = '{draft_id}';") == "0"
        )

    (OUT / "work-ticket-step-draft.json").write_text(
        json.dumps(
            {"checks": checks, "detail": detail, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print("draft_id:", detail.get("draft_id"), "| 回填:", detail.get("refilled_applicant_unit"))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
