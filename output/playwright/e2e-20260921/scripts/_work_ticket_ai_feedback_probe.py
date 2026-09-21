"""AI 生成反馈实测（浏览器）：点「AI 生成」后必须立刻有 loading 与提示。

背景（用户反馈）：JSA 点「AI 生成」后界面毫无变化，过一会儿结果突然出现，
用户不知道点上没有。修完之后本探针验证三件事：
  1. 点击后 1 秒内：按钮进入 loading（disabled/loading 态）且页面出现「AI 生成中…」
  2. 结果返回后：提示变为完成（或明确告知 AI 不可用），按钮恢复可点
  3. 全程 0 console error

用法（仓库根目录）：
    python output/playwright/e2e-20260921/scripts/_work_ticket_ai_feedback_probe.py
证据输出：同目录 work-ticket-ai-feedback.json（含点击瞬间截图）
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
AI_TIMEOUT_MS = 90_000


def click_button(page, text: str) -> None:
    """antd 会给两字按钮插空格，故用允许空白的正则。"""
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

        # 打开开票向导并走到第 4 步（JSA）
        page.goto(f"{BASE}/enterprises/{ENT}/work-ticket/new", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        for _ in range(4):
            click_button(page, "下一步")
            page.wait_for_timeout(1500)
        detail["step4_text_has_jsa"] = "JSA" in page.inner_text("body")

        # 点击「AI 生成」并立刻采集反馈
        click_button(page, "AI 生成")
        page.wait_for_timeout(900)
        instant_text = page.inner_text("body")
        detail["instant_snapshot"] = instant_text[:300]
        checks["loading_hint_visible"] = "AI 生成中" in instant_text
        checks["button_shows_progress"] = "生成中" in instant_text
        page.screenshot(path=str(OUT / "work-ticket-ai-loading.png"), full_page=True)

        # 等结果（AI 慢时可达 60s；未配置时几乎立刻返回）
        outcome = "timeout"
        try:
            page.wait_for_function(
                """() => {
                    const t = document.body.innerText;
                    return t.includes('AI 生成完成') || t.includes('AI 暂不可用')
                        || t.includes('未配置') || t.includes('失败');
                }""",
                timeout=AI_TIMEOUT_MS,
            )
            final_text = page.inner_text("body")
            if "AI 生成完成" in final_text:
                outcome = "completed"
            else:
                outcome = "unavailable"
        except Exception:
            outcome = "timeout"
            final_text = page.inner_text("body")

        detail["outcome"] = outcome
        detail["final_snapshot"] = final_text[:400]
        checks["ai_call_reached_outcome"] = outcome in ("completed", "unavailable")
        # 结束后按钮必须恢复可点（不能一直转）
        checks["button_recovered"] = "生成中" not in final_text
        checks["no_console_error"] = len(errors) == 0
        detail["errors"] = errors[:5]

        browser.close()

    (OUT / "work-ticket-ai-feedback.json").write_text(
        json.dumps(
            {"checks": checks, "detail": detail, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print("outcome:", detail.get("outcome"))
    if errors:
        print("errors:", errors[:3])
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
