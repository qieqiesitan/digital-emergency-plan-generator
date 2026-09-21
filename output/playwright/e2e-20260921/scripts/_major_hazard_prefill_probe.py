"""重大危险源单元「从风险点带出填写项」浏览器实测。

覆盖规格 2026-09-21-major-hazard-riskpoint-prefill-design.md 的验收清单：
  1. 选风险点后 4 项空白字段被填，已填的人工值不被覆盖
  2. 带出字段显示「来自风险点」标记，改过的字段标记消失
  3. 点保存后：关联仍在（P0 回归）、带出与手改的值都落库
  4. 全程 0 console error

用法（仓库根目录）：
    python output/playwright/e2e-20260921/scripts/_major_hazard_prefill_probe.py
证据输出：同目录 major-hazard-prefill.json（含保存前/重载后两张截图）

夹具数据（企业/分区/风险点/单元）故意不清理：与其他 E2E 探针一致，留证据便于人工复核。
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

RISK = {
    "location": "厂区北侧罐区东侧",
    "responsible_unit": "生产运行部",
    "responsible_person": "张峰",
    "contact_phone": "13800000000",
}
FIELDS = ("address", "department", "responsible_person", "responsible_phone")
MANUAL_DEPARTMENT = "人工填的部门"
TAG = "来自风险点"


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
    """隔离夹具：企业 → 分区 → 带 4 项信息的风险点 → 空单元。"""
    stamp = int(time.time() * 1000)
    ent = call_data("POST", "/enterprises", token, {"name": f"E2E_Prefill_{stamp}"})["id"]
    zone = call_data(
        # 风险分级管控挂在 /enterprises/{id}/risk-management 下：enterprise_id 是路径参数
        "POST",
        f"/enterprises/{ent}/risk-management/zones",
        token,
        {"name": f"分区{stamp}"},
    )
    obj = call_data(
        "POST",
        f"/enterprises/{ent}/risk-management/objects",
        token,
        {
            "name": "罐区A风险点",
            "zone_id": zone["id"],
            "location_x": 10.0,
            "location_y": 20.0,
            "is_risk_point": True,
            **RISK,
        },
    )
    unit = call_data(
        "POST",
        f"/major-hazard/units?enterprise_id={ent}",
        token,
        {"name": "罐区A", "unit_type": "storage"},
    )
    return {"enterprise": ent, "zone": zone["id"], "object": obj["id"], "unit": unit["id"]}


def main() -> int:
    checks: dict[str, bool] = {}
    detail: dict = {}
    errors: list[str] = []

    token = call_data("POST", "/auth/login", None, {"email": U, "password": P})["access_token"]
    fx = build_fixture(token)
    detail["fixture"] = fx

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
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

        before = {f: page.input_value(f"#{f}") for f in FIELDS}
        detail["before"] = before
        checks["fields_start_blank"] = all(v == "" for v in before.values())

        # 先人工填一项：验证「空白才填、已填不覆盖」
        page.fill("#department", MANUAL_DEPARTMENT)
        page.wait_for_timeout(300)

        # 选择风险点。
        # 注意两处 antd 细节：
        # 1) Select 不把 placeholder 放在 input 上（渲染成独立的
        #    .ant-select-selection-placeholder），所以按卡片范围定位，避免撞上表单里的
        #    「单元类型」选择器；
        # 2) rc-select 会额外渲染一份**不可见**的无障碍 option 列表（role="option"），
        #    点它会超时，必须点可见的 .ant-select-item-option。
        picker = page.locator(".ant-card", has_text="关联风险点").locator(".ant-select")
        picker.click()
        page.wait_for_timeout(800)
        page.locator(".ant-select-item-option", has_text="罐区A风险点").first.click()
        page.wait_for_timeout(2000)

        after = {f: page.input_value(f"#{f}") for f in FIELDS}
        detail["after_pick"] = after
        checks["prefilled_blank_fields"] = (
            after["address"] == RISK["location"]
            and after["responsible_person"] == RISK["responsible_person"]
            and after["responsible_phone"] == RISK["contact_phone"]
        )
        checks["manual_value_not_overwritten"] = after["department"] == MANUAL_DEPARTMENT

        body = page.inner_text("body")
        detail["tag_count_after_pick"] = body.count(TAG)
        checks["source_tag_shown_for_three"] = detail["tag_count_after_pick"] == 3
        page.screenshot(path=str(OUT / "major-hazard-prefill-before-save.png"), full_page=True)

        # 改掉一个带出字段 → 该字段标记消失，其余仍标记
        edited_address = f"{RISK['location']}（改过）"
        page.fill("#address", edited_address)
        page.wait_for_timeout(800)
        detail["tag_count_after_edit"] = page.inner_text("body").count(TAG)
        checks["tag_cleared_after_edit"] = detail["tag_count_after_edit"] == 2

        click_button(page, "保存")
        page.wait_for_timeout(2500)

        # P0 回归：保存后关联必须还在（走接口判定，避免被页面文本干扰）
        units = call_data("GET", f"/major-hazard/units?enterprise_id={fx['enterprise']}", token)
        saved = next(u for u in units if u["id"] == fx["unit"])
        detail["saved_unit"] = saved
        checks["link_survived_save"] = saved["risk_object_id"] == fx["object"]
        checks["prefilled_value_persisted"] = (
            saved["responsible_person"] == RISK["responsible_person"]
        )
        checks["edited_value_persisted"] = saved["address"] == edited_address
        checks["manual_value_persisted"] = saved["department"] == MANUAL_DEPARTMENT

        # 重载后界面仍应显示落库的值
        page.reload(wait_until="load")
        page.wait_for_timeout(3000)
        after_reload = {f: page.input_value(f"#{f}") for f in FIELDS}
        detail["after_reload"] = after_reload
        checks["reload_shows_persisted"] = (
            after_reload["responsible_person"] == RISK["responsible_person"]
            and after_reload["address"] == edited_address
        )
        # 重载后没有"刚带出"的上下文，标记不该留着（<=1 容错：页面说明文字里含该词的变体）
        detail["tag_count_after_reload"] = page.inner_text("body").count(TAG)
        checks["reload_has_no_tag"] = detail["tag_count_after_reload"] <= 1

        checks["no_console_error"] = len(errors) == 0
        detail["errors"] = errors[:5]
        page.screenshot(path=str(OUT / "major-hazard-prefill-after-reload.png"), full_page=True)
        browser.close()

    (OUT / "major-hazard-prefill.json").write_text(
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
