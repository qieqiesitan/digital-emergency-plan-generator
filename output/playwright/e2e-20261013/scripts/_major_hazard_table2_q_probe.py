"""重大危险源「表2 按危险性类别取临界量」浏览器实测。

背景：GB 18218 的 Q 取值顺序是「先表1 按品种名、不在表1 则表2 按危险性类别」，
表2 与表4（β）共用同一套符号（J1~J5、W1.1~W11）。修复前这段没接上，
汽油这类品种的 Q 拿不到；修复后要求：**选一次危险性类别就把 Q 和 β 一起带出**。

验证点：
  1. 手打「汽油」（表1 没列举，下拉里搜不到）→ 失焦后能触发查表
  2. Q 列提示「未在表1列举，请选右侧危险性类别」，β 列出现类别下拉
  3. 下拉选项里同时写明 Q 与 β
  4. 选 W5.1 → Q=10（表2）、β=1.5（表4），Q 列标明来源
  5. 全程 0 console error

用法（仓库根目录）：
    python output/playwright/e2e-20261013/scripts/_major_hazard_table2_q_probe.py
证据输出：同目录 major-hazard-table2-q.json
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

API = os.environ.get("E2E_API", "http://localhost:8000/api/v1")
BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
OUT = Path(__file__).resolve().parent
U, P = "qa_e2e_test@test.com", "test123456"

# 汽油不在表1（85 个列举品种）里，也不在表3（14 种毒性气体）里，
# 所以 Q 和 β 都得靠表2/表4 的同一套类别符号定下来。
CHEMICAL = "汽油"
SYMBOL = "W5.1"
# 断言比数值不比字符串：Q 的 InputNumber 带 step=0.1，antd 据此把小数位定为 1，
# 于是 10 会显示成 "10.0"（β=1.5 同一规则）。那是显示格式，不是取值错误。
EXPECT_Q = 10.0
EXPECT_BETA = 1.5

# 品种与存量表格的列序：0 危险化学品 / 1 关联台账 / 2 设计最大量 / 3 临界量Q / 4 β
COL_NAME, COL_DESIGN, COL_Q, COL_BETA = 0, 2, 3, 4


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def call_data(method, path, token, body=None):
    return call(method, path, token, body)["data"]


def click_button(page, text: str) -> None:
    """antd 会给两字按钮插空格，故用允许空白的正则。"""
    page.get_by_role("button", name=re.compile(r"\s*".join(text))).first.click()


def build_fixture(token: str) -> dict:
    """只建企业 + 空单元：本探针只关心品种表的取值链路。"""
    stamp = int(time.time() * 1000)
    ent = call_data("POST", "/enterprises", token, {"name": f"E2E_Table2Q_{stamp}"})["id"]
    unit = call_data(
        "POST",
        f"/major-hazard/units?enterprise_id={ent}",
        token,
        {"name": "罐区Q", "unit_type": "storage"},
    )
    return {"enterprise": ent, "unit": unit["id"]}


def main() -> int:
    checks: dict[str, bool] = {}
    detail: dict = {}
    errors: list[str] = []

    token = call_data("POST", "/auth/login", None, {"email": U, "password": P})["access_token"]
    fx = build_fixture(token)
    detail["fixture"] = fx

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1600, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: errors.append(f"console:{m.text[:120]}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))

        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        page.fill('input[placeholder="邮箱"]', U)
        page.fill('input[placeholder="密码"]', P)
        click_button(page, "登录")
        page.wait_for_timeout(4000)

        url = f"{BASE}/enterprises/{fx['enterprise']}/major-hazard/units/{fx['unit']}"
        page.goto(url, wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)
        page.get_by_role("tab", name="品种与存量").click()
        page.wait_for_timeout(1500)

        click_button(page, "添加品种")
        page.wait_for_timeout(800)
        row = page.locator("tbody tr.ant-table-row").first
        name_cell = row.locator("td").nth(COL_NAME)
        q_cell = row.locator("td").nth(COL_Q)
        beta_cell = row.locator("td").nth(COL_BETA)

        # 手打名字（下拉里搜不到这个品种），失焦触发查表
        name_cell.locator("input").first.fill(CHEMICAL)
        page.keyboard.press("Tab")
        page.wait_for_timeout(2500)

        detail["q_cell_after_blur"] = q_cell.inner_text()
        detail["beta_cell_after_blur"] = beta_cell.inner_text()
        checks["q_hint_says_not_in_table1"] = "未在表1列举" in q_cell.inner_text()
        checks["category_picker_appears"] = "选危险性类别" in beta_cell.inner_text()

        beta_cell.locator(".ant-select").click()
        page.wait_for_timeout(600)
        # 24 个类别选项超出可视区，rc-select 虚拟滚动只渲染可见项——
        # 直接点会找不到元素。下拉支持搜索，输入符号先过滤再点。
        page.keyboard.type(SYMBOL)
        page.wait_for_timeout(900)
        # 页面上有多个 Select（关联台账/品种名/危险性类别），各自带一个 dropdown 节点，
        # 未展开的那些是 ant-select-dropdown-hidden —— 只看可见的那个，否则撞严格模式
        dropdown_loc = page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden)")
        dropdown = dropdown_loc.inner_text()
        detail["dropdown_sample"] = dropdown[:400]
        checks["option_shows_q_and_beta"] = "Q=10 t" in dropdown and "β=1.5" in dropdown
        page.screenshot(path=str(OUT / "table2-q-dropdown.png"), full_page=True)

        dropdown_loc.locator(".ant-select-item-option", has_text=SYMBOL).first.click()
        page.wait_for_timeout(2500)

        q_val = q_cell.locator("input.ant-input-number-input").first.input_value()
        beta_val = beta_cell.locator("input.ant-input-number-input").first.input_value()
        detail["q_value"] = q_val
        detail["beta_value"] = beta_val
        detail["q_cell_after_pick"] = q_cell.inner_text()
        checks["q_filled_from_table2"] = float(q_val) == EXPECT_Q
        checks["beta_filled_from_table4"] = float(beta_val) == EXPECT_BETA
        checks["q_source_hint_shown"] = "按所选危险性类别取自表2" in q_cell.inner_text()
        page.screenshot(path=str(OUT / "table2-q-after-pick.png"), full_page=True)

        # 保存前必须补设计最大量：它是必填项，前端会拦住"资料不全"的行不提交。
        # 12 t 只是随手给的示例（q/Q = 1.2）；本探针关心的是 Q 与 β 的取值链路。
        row.locator("td").nth(COL_DESIGN).locator("input.ant-input-number-input").first.fill("12")
        page.wait_for_timeout(400)

        # 关闭回路：存下去再读回来，确认带出的值真的落库（不只是界面上好看）
        click_button(page, "保存品种清单")
        page.wait_for_timeout(2500)
        saved = call_data("GET", f"/major-hazard/units/{fx['unit']}/chemicals", token)
        detail["saved_rows"] = saved
        row0 = saved[0] if saved else {}
        checks["q_persisted"] = float(row0.get("critical_quantity_t") or 0) == EXPECT_Q
        checks["beta_persisted"] = float(row0.get("beta") or 0) == EXPECT_BETA
        checks["beta_source_is_table4"] = row0.get("beta_source") == "table4"

        checks["no_console_error"] = len(errors) == 0
        detail["errors"] = errors[:5]
        browser.close()

    (OUT / "major-hazard-table2-q.json").write_text(
        json.dumps(
            {"checks": checks, "detail": detail, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if errors:
        print("errors:", errors[:3])
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
