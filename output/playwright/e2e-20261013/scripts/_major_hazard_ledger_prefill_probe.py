"""重大危险源「从关联台账选入品种时也带出标准值」浏览器实测。

用户反馈：在品种表里从「关联台账」选汽油/柴油，Q 与 β 不会带出来。
根因是关联台账这条路径压根没接查表链路；另外台账名常与标准写法对不上——
台账「汽油」↔ 表1「汽油(乙醇汽油、甲醇汽油)」（CAS 86290-81-5(汽油)），
所以本轮加了 CAS 兜底。

验证点：
  1. 选台账「汽油」→ 品种名带出、**Q 自动=200**（靠 CAS 认出来的，不是名字匹配）
  2. 台账建议（设计最大量）同时出现，且这一行的「关联台账」仍显示汽油（关联没被带出的值冲掉）
  3. 选台账「柴油」（不在表1、台账也没有 CAS）→ 落到"选危险性类别"那条路，不瞎填
  4. 全程 0 console error

用法（仓库根目录）：
    python output/playwright/e2e-20261013/scripts/_major_hazard_ledger_prefill_probe.py
证据输出：同目录 major-hazard-ledger-prefill.json
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

# 汽油：台账 CAS 86290-81-5 ↔ 表1「汽油(乙醇汽油、甲醇汽油)」Q=200t
GASOLINE, GASOLINE_CAS, GASOLINE_Q = "汽油", "86290-81-5", 200.0
# 柴油：表1 未列举、台账也没有 CAS → 只能按危险性类别定
DIESEL = "柴油"

# 列序：0 危险化学品 / 1 关联台账 / 2 设计最大量 / 3 临界量Q / 4 β
COL_NAME, COL_LEDGER, COL_DESIGN, COL_Q, COL_BETA = 0, 1, 2, 3, 4


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
    page.get_by_role("button", name=re.compile(r"\s*".join(text))).first.click()


def visible_dropdown(page):
    """页面上多个 Select 各带一个 dropdown 节点，只看展开的那个。"""
    return page.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden)")


def pick_from_ledger(page, row, label: str) -> None:
    """点开该行的「关联台账」下拉，搜索后选中指定条目。"""
    row.locator("td").nth(COL_LEDGER).locator(".ant-select").click()
    page.wait_for_timeout(500)
    page.keyboard.type(label)
    page.wait_for_timeout(700)
    visible_dropdown(page).locator(".ant-select-item-option", has_text=label).first.click()
    page.wait_for_timeout(2500)


def build_fixture(token: str) -> dict:
    stamp = int(time.time() * 1000)
    ent = call_data("POST", "/enterprises", token, {"name": f"E2E_Ledger_{stamp}"})["id"]
    for name, cas, max_storage in ((GASOLINE, GASOLINE_CAS, "40t"), (DIESEL, None, None)):
        body = {"name": name, "max_storage": max_storage}
        if cas:
            body["cas_no"] = cas
        call_data("POST", f"/enterprises/{ent}/chemicals", token, body)
    unit = call_data(
        "POST",
        f"/major-hazard/units?enterprise_id={ent}",
        token,
        {"name": "罐区台账", "unit_type": "storage"},
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

        # --- 第一行：汽油（台账有 CAS，标准里是「汽油(乙醇汽油、甲醇汽油)」）---
        click_button(page, "添加品种")
        page.wait_for_timeout(800)
        row1 = page.locator("tbody tr.ant-table-row").first
        pick_from_ledger(page, row1, GASOLINE)

        name1 = row1.locator("td").nth(COL_NAME).locator("input").first.input_value()
        q1 = row1.locator("td").nth(COL_Q).locator("input.ant-input-number-input").first.input_value()
        # 汽油不在表3（14 种毒性气体）里，β 必须按危险性类别取，
        # 所以这一格是下拉而不是数字框——这是对的，不是缺陷
        beta1_cell = row1.locator("td").nth(COL_BETA).inner_text()
        design1 = row1.locator("td").nth(COL_DESIGN).inner_text()
        ledger1 = row1.locator("td").nth(COL_LEDGER).inner_text()
        detail["row1"] = {
            "name": name1,
            "q": q1,
            "beta_cell": beta1_cell,
            "design_cell": design1,
            "ledger_cell": ledger1,
        }
        checks["name_filled_from_ledger"] = name1 == GASOLINE
        checks["q_filled_by_cas"] = q1 != "" and float(q1) == GASOLINE_Q
        # Q 已知时占位符是「请选择危险性类别」、Q 未知时是「选危险性类别，Q 与 β 一并带出」，
        # 所以只断言共同子串「危险性类别」
        checks["gasoline_beta_asks_category"] = "危险性类别" in beta1_cell
        checks["design_max_suggestion_shown"] = "台账建议" in design1
        # 关联没被"带出标准值"那一步冲掉（patch 用闭包 rows 会踩这个坑）
        checks["ledger_link_survived"] = GASOLINE in ledger1
        page.screenshot(path=str(OUT / "ledger-prefill-row1.png"), full_page=True)

        # --- 第二行：柴油（表1 没列举、台账无 CAS）---
        click_button(page, "添加品种")
        page.wait_for_timeout(800)
        row2 = page.locator("tbody tr.ant-table-row").nth(1)
        pick_from_ledger(page, row2, DIESEL)

        name2 = row2.locator("td").nth(COL_NAME).locator("input").first.input_value()
        q2_cell = row2.locator("td").nth(COL_Q)
        beta2_cell = row2.locator("td").nth(COL_BETA)
        detail["row2"] = {
            "name": name2,
            "q_cell": q2_cell.inner_text(),
            "beta_cell": beta2_cell.inner_text(),
        }
        checks["diesel_name_filled"] = name2 == DIESEL
        # 柴油不在表1：不瞎填，落在"选危险性类别"那条路上
        checks["diesel_q_left_empty"] = "未在表1列举" in q2_cell.inner_text()
        checks["diesel_asks_category"] = "选危险性类别" in beta2_cell.inner_text()

        checks["no_console_error"] = len(errors) == 0
        detail["errors"] = errors[:5]
        page.screenshot(path=str(OUT / "ledger-prefill-row2.png"), full_page=True)
        browser.close()

    (OUT / "major-hazard-ledger-prefill.json").write_text(
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
