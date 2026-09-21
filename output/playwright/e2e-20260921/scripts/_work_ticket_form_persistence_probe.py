"""开票向导表单值保全实测（浏览器）。

背景（用户反馈 2026-09-21）：按步骤填完所有字段后点提交，却报「所有必填项尚未填写」。
根因：`<Form>` 只在第 1 步挂载，走到第 5 步时组件已卸载，antd 的 Form store 随之销毁，
`form.getFieldsValue()` 返回空 → 全部必填项一起报未填写。

本探针验证修复：在第 1 步填字段（含预填的默认值），跳到第 5 步后点提交，
断言错误清单里**不再出现「必填项 … 尚未填写」**（措施/气体检测的提示属于预期，不在此断言内）。

用法（仓库根目录）：
    python output/playwright/e2e-20260921/scripts/_work_ticket_form_persistence_probe.py
证据输出：同目录 work-ticket-form-persistence.json
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


def click_button(page, text: str) -> None:
    page.get_by_role("button", name=re.compile(r"\s*".join(text))).first.click()


def main() -> int:
    errors: list[str] = []
    checks: dict[str, bool] = {}
    detail: dict = {}

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

        page.goto(f"{BASE}/enterprises/{ENT}/work-ticket/new", wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)
        click_button(page, "下一步")  # → 第 1 步（票面内容）
        page.wait_for_timeout(2000)

        # 填两个手工字段；其余必填项靠预填的默认值（apply_time / work_period 等）
        page.fill('input[placeholder="作业申请单位"]', "自动化探针单位")
        page.fill('textarea[placeholder="作业内容"]', "自动化探针作业内容")
        detail["filled_applicant_unit"] = page.input_value('input[placeholder="作业申请单位"]')

        # 走到第 5 步（人员与提交）
        for _ in range(4):
            click_button(page, "下一步")
            page.wait_for_timeout(1200)

        click_button(page, "提交审批")
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        detail["submit_panel"] = body[-600:]

        required_errors = re.findall(r"必填项「[^」]+」尚未填写", body)
        detail["required_field_errors"] = required_errors
        # 探针填过或预填成功的字段：修复前它们会全部出现在错误里（实测 11 条），修复后必须一条不剩
        kept_fields = {
            "作业申请单位",      # 探针手工填
            "作业内容",          # 探针手工填
            "作业申请时间",      # 预填（系统默认）
            "动火作业实施时间",  # 预填（系统默认）
            "动火作业级别",      # 第 0 步级别联动写入
            "作业单位",          # 预填
        }
        detail["lost_fields"] = [
            err for err in required_errors if any(f"「{name}」" in err for name in kept_fields)
        ]
        checks["no_required_field_lost"] = len(detail["lost_fields"]) == 0
        # 措施与气体检测的提示属于预期（本探针不处理它们），只确认它们仍在，说明校验确实跑了
        checks["validation_still_runs"] = ("未表态" in body) or ("气体检测" in body)
        checks["no_console_error"] = len(errors) == 0
        detail["errors"] = errors[:5]

        page.screenshot(path=str(OUT / "work-ticket-form-submit.png"), full_page=True)
        browser.close()

    (OUT / "work-ticket-form-persistence.json").write_text(
        json.dumps(
            {"checks": checks, "detail": detail, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print("必填项错误条数:", len(required_errors), "| 其中已填/预填字段被误报:", len(detail["lost_fields"]))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
