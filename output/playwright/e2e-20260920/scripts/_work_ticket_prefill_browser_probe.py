"""作业票智能预填 / 措施三态 浏览器实测（桌面 1440x900，真账号，只读）。

逐票种打开开票向导第 1 步，检查：
  - 8 个票种都能进入票面步骤且渲染出字段
  - 自动带出的字段出现来源徽标（企业档案 / 上次同类票 / 系统默认 / 向导联动）
  - 动火票第 3 步的措施条数为 16（修复 106 条缺陷后的真实界面）
  - 列表页出现「新建作业包」入口
  - 全程 0 console error / 0 pageerror

用法（仓库根目录）：
    python output/playwright/e2e-20260920/scripts/_work_ticket_prefill_browser_probe.py
证据输出：同目录 work-ticket-prefill-browser.json（含逐票种明细与截图）
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

TYPES = [
    "动火作业",
    "受限空间作业",
    "盲板抽堵作业",
    "高处作业",
    "吊装作业",
    "临时用电作业",
    "动土作业",
    "断路作业",
]

BADGE_TEXTS = ["企业档案", "上次同类票", "系统默认", "向导联动", "成员台账", "AI 生成"]


def click_button(page, text: str) -> None:
    """点按钮：antd 会给两字按钮自动插入空格（"登 录"），故用允许空白的正则。"""
    page.get_by_role("button", name=re.compile(r"\s*".join(text))).first.click()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    per_type: list[dict] = []
    checks: dict[str, bool] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on(
            "console",
            lambda msg: errors.append(f"console:{msg.text}") if msg.type == "error" else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))

        # 登录（桌面入口）
        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        # antd 的 Input 默认 type=text（邮箱只体现在校验规则里），故按 placeholder 定位
        page.wait_for_selector('input[placeholder="邮箱"]', timeout=30000)
        page.fill('input[placeholder="邮箱"]', U)
        page.fill('input[placeholder="密码"]', P)
        click_button(page, "登录")
        page.wait_for_timeout(4000)
        token = page.evaluate("() => localStorage.getItem('access_token') || ''")
        checks["login_ok"] = bool(token)

        # 列表页应出现「新建作业包」入口
        page.goto(f"{BASE}/enterprises/{ENT}/work-ticket", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        checks["batch_entry_visible"] = page.get_by_text("新建作业包").count() > 0

        # 逐票种打开向导
        page.goto(f"{BASE}/enterprises/{ENT}/work-ticket/new", wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)
        for label in TYPES:
            entry = {"type": label}
            # 每轮重新打开向导页，保证状态干净（不依赖「上一步」按钮）
            page.goto(
                f"{BASE}/enterprises/{ENT}/work-ticket/new", wait_until="load", timeout=40000
            )
            page.wait_for_timeout(2500)
            target = page.get_by_text(label, exact=True).first
            if target.count() == 0:
                entry["reachable"] = False
                per_type.append(entry)
                continue
            target.click()
            page.wait_for_timeout(600)
            click_button(page, "下一步")
            page.wait_for_timeout(2000)
            body = page.inner_text("body")
            entry["reachable"] = True
            entry["field_labels"] = len(page.locator("form label").all())
            entry["badges"] = [b for b in BADGE_TEXTS if b in body]
            per_type.append(entry)

        # 动火票：继续走到第 3 步看措施条数（16 条；修复前是 106 条）
        page.goto(f"{BASE}/enterprises/{ENT}/work-ticket/new", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        measure_text, measure_count, step_error = "", -1, ""
        try:
            page.get_by_text("动火作业", exact=True).first.click()
            page.wait_for_timeout(600)
            click_button(page, "下一步")  # → 票面内容
            page.wait_for_timeout(1800)
            click_button(page, "下一步")  # → 气体检测
            page.wait_for_timeout(1500)
            click_button(page, "下一步")  # → 安全措施
            page.wait_for_timeout(1800)
            measure_text = page.inner_text("body")
            match = re.search(r"已表态\s*\d+\s*/\s*(\d+)\s*条", measure_text)
            measure_count = int(match.group(1)) if match else -1
        except Exception as exc:  # 点击链失败不影响其余断言的产出
            step_error = f"{type(exc).__name__}: {str(exc)[:120]}"
            measure_text = page.inner_text("body")
        page.screenshot(path=str(OUT / "work-ticket-browser-measures.png"), full_page=True)

        browser.close()

    checks["eight_types_reachable"] = len(per_type) == 8 and all(
        item.get("reachable") for item in per_type
    )
    checks["fields_rendered"] = all((item.get("field_labels") or 0) >= 5 for item in per_type)
    checks["prefill_badges_visible"] = any(item.get("badges") for item in per_type)
    checks["fire_measures_is_16"] = measure_count == 16
    checks["no_console_error"] = len(errors) == 0

    (OUT / "work-ticket-prefill-browser.json").write_text(
        json.dumps(
            {
                "per_type": per_type,
                "fire_measure_count": measure_count,
                "fire_step_error": step_error,
                "fire_page_excerpt": measure_text[:400],
                "errors": errors[:20],
                "checks": checks,
                "all_passed": all(checks.values()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if errors:
        print("errors:", errors[:5])
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
