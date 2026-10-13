"""智能导引「补全现有风险树」浏览器实测。

背景：用户要求「风险树中 AI 智能生成要根据企业基本情况 + 用户输入完善风险树」。
本轮改动：AI 读企业档案扩展字段 + 现有树完整结构，输出查漏补缺（同名并入、
缺下级补齐）；弹窗描述可选、预览标「新增/并入」。

验证点：
  1. 场景 B（留空描述）：AI 分析完成，预览出现层级（历史树缺下级被补）
  2. 场景 A（填描述）：描述被利用；预览出现「并入/新增」标签与「将新增 X · 并入 Y」汇总
  3. 导入后回读：现有「储罐区」未被重复创建；「1号储罐」下补出单元/事件
  4. 全程 0 console error

用法（仓库根目录）：
    python output/playwright/e2e-20261013/scripts/_smart_guide_completion_probe.py
证据输出：同目录 smart-guide-completion.json + 2 张截图
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

ZONE = "储罐区"
TANK = "1号储罐"
DESC = "储罐区有2个汽油储罐，配备液位监测报警和防火堤"
AI_WAIT_MS = 170_000  # 后端 LLM 超时 150s，留缓冲


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def call_data(method, path, token, body=None):
    return call(method, path, token, body)["data"]


def build_fixture(token: str) -> dict:
    """造一棵「缺下级」的树：分区储罐区 + 对象 1号储罐（无单元/事件），并填企业档案。"""
    stamp = int(time.time() * 1000)
    ent = call_data("POST", "/enterprises", token, {"name": f"E2E_SmartGuide_{stamp}"})["id"]
    call_data("PUT", f"/enterprises/{ent}", token, {
        "name": f"E2E_SmartGuide_{stamp}",
        "industry": "加油站",
        "business_scope": "汽油、柴油零售；润滑油销售",
        "main_products": "汽油、柴油",
        "main_equipment_list": "汽油储罐2台（每台30m³）、柴油储罐1台",
        "hazardous_chemicals": "汽油、柴油",
    })
    zone = call_data("POST", f"/enterprises/{ent}/risk-management/zones", token, {"name": ZONE})["id"]
    call_data("POST", f"/enterprises/{ent}/risk-management/objects", token, {
        "zone_id": zone, "name": TANK, "is_risk_point": False,
    })
    return {"enterprise": ent, "zone": zone}


def hierarchy_stats(token: str, ent: str) -> dict:
    zones = call_data("GET", f"/enterprises/{ent}/risk-management/hierarchy", token)
    stats = {"zone_count": len(zones), "zone_names": [z["name"] for z in zones], "tank": None}
    for z in zones:
        for o in z.get("objects", []):
            if o["name"] == TANK:
                stats["tank"] = {
                    "under_zone": z["name"],
                    "unit_count": len(o.get("units", [])),
                    "unit_event_count": sum(len(u.get("events", [])) for u in o.get("units", [])),
                    "obj_event_count": len(o.get("events", [])),
                }
    return stats


def open_guide_modal(page) -> None:
    page.get_by_role("button", name=re.compile(r"智能导引")).first.click()
    page.wait_for_timeout(800)


def run_analysis(page, description: str) -> None:
    textarea = page.locator(".ant-modal textarea").first
    if description:
        textarea.fill(description)
    page.get_by_role("button", name=re.compile("AI 分析")).first.click()
    page.get_by_text(re.compile("AI 已按企业档案与现有风险树查漏补缺")).wait_for(
        state="visible", timeout=AI_WAIT_MS
    )
    page.wait_for_timeout(600)


def main() -> int:
    checks: dict[str, bool] = {}
    detail: dict = {}
    errors: list[str] = []

    token = call_data("POST", "/auth/login", None, {"email": U, "password": P})["access_token"]
    fx = build_fixture(token)
    detail["fixture"] = fx
    detail["before_import"] = hierarchy_stats(token, fx["enterprise"])

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1600, "height": 950}, locale="zh-CN")
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: errors.append(f"console:{m.text[:140]}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))

        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2000)
        page.fill('input[placeholder="邮箱"]', U)
        page.fill('input[placeholder="密码"]', P)
        page.get_by_role("button", name=re.compile(r"\s*".join("登录"))).first.click()
        page.wait_for_timeout(3500)

        page.goto(f"{BASE}/enterprises/{fx['enterprise']}/risk-management", wait_until="load", timeout=40000)
        page.get_by_role("button", name=re.compile("添加分区")).first.wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(1500)

        # ── 场景 B：留空描述，AI 应能依据企业档案+现有树补全 ──
        open_guide_modal(page)
        run_analysis(page, "")
        modal = page.locator(".ant-modal:visible").last
        b_zone_visible = modal.get_by_text(ZONE, exact=True).count() > 0
        b_tree_nonempty = modal.locator(".ant-tree-treenode").count() > 0
        checks["B_blank_desc_preview_ok"] = b_zone_visible and b_tree_nonempty
        detail["B_preview"] = {
            "zone_visible": b_zone_visible,
            "tree_nodes": modal.locator(".ant-tree-treenode").count(),
        }
        page.screenshot(path=str(OUT / "smart-guide-blank-desc-preview.png"), full_page=True)
        page.keyboard.press("Escape")
        page.wait_for_timeout(900)

        # ── 场景 A：填描述 → 分析 → 断言标签/汇总 → 导入 → 回读 ──
        open_guide_modal(page)
        run_analysis(page, DESC)
        modal = page.locator(".ant-modal:visible").last
        a_zone_visible = modal.get_by_text(ZONE, exact=True).count() > 0
        merge_tag = modal.get_by_text("并入", exact=True).count() > 0
        new_tag = modal.get_by_text("新增", exact=True).count() > 0
        summary_text = modal.inner_text()
        summary_ok = "将新增" in summary_text and "并入" in summary_text
        checks["A_preview_zone_path"] = a_zone_visible
        checks["A_merge_badge_shown"] = merge_tag
        checks["A_new_badge_shown"] = new_tag
        checks["A_summary_shown"] = summary_ok
        detail["A_preview"] = {
            "zone_visible": a_zone_visible,
            "merge_badge": merge_tag,
            "new_badge": new_tag,
            "summary_has_counts": summary_ok,
        }
        page.screenshot(path=str(OUT / "smart-guide-desc-preview.png"), full_page=True)

        modal.get_by_role("button", name=re.compile("确认并导入全部")).first.click()
        page.get_by_text(re.compile("导入完成")).wait_for(state="visible", timeout=30000)
        page.wait_for_timeout(1200)
        detail["import_toast"] = page.get_by_text(re.compile("导入完成")).first.inner_text()
        checks["A_import_done"] = "新增" in detail["import_toast"]

        after = hierarchy_stats(token, fx["enterprise"])
        detail["after_import"] = after
        checks["zone_not_duplicated"] = after["zone_names"].count(ZONE) == 1
        tank = after.get("tank") or {}
        checks["tank_got_children"] = (tank.get("unit_count", 0) + tank.get("obj_event_count", 0)) > 0
        checks["tank_event_has_measures"] = tank.get("unit_event_count", 0) > 0 or tank.get("obj_event_count", 0) > 0
        detail["tank_after"] = tank

        checks["no_console_errors"] = len(errors) == 0
        ctx.close()
        browser.close()

    result = {
        "checks": checks,
        "detail": detail,
        "errors": errors[:20],
        "passed": all(checks.values()),
    }
    (OUT / "smart-guide-completion.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"checks": checks, "errors": errors[:5]}, ensure_ascii=False, indent=2))
    print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
