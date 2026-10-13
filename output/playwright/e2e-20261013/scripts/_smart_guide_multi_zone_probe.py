"""智能导引「同名多分区分发补全」浏览器实测。

背景：用户反馈永昇加油站有 4 个同名「加油机」分区（四色图识别的设备位置），
AI 补充时只补充了一个——根因是导入端同名分区只匹配单个 id、其余同名分区永远空。
本轮修复：同名分区列表化；AI 段数不足时分发到全部同名分区；预览显示「并入 ×N」。

验证（AI 响应用 route mock 固定，导入走真实后端，确定性驱动）：
  1. 造 3 个同名「加油机」分区 + 1 个「储罐区」对照
  2. mock AI 返回 1 段「加油机」（1 对象/1 单元/1 事件/2 措施）+ 1 段「储罐区」
  3. 预览断言：「并入 ×3」标签出现
  4. 导入后回读：3 个「加油机」分区**各自**有「加油机本体」对象+单元+事件+措施
  5. 全程 0 console error

用法（仓库根目录）：
    python output/playwright/e2e-20261013/scripts/_smart_guide_multi_zone_probe.py
证据输出：同目录 smart-guide-multi-zone.json + 1 张截图
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

PUMPS = "加油机"
TANK_ZONE = "储罐区"

MOCK_HIERARCHY = [
    {
        "name": PUMPS,
        "objects": [{
            "name": "加油机本体", "category": "设备", "is_risk_point": False,
            "units": [{
                "name": "机体", "unit_type": "设备",
                "events": [{
                    "accident_type": "泄漏", "risk_level": "一般", "risk_score": "R=8",
                    "method_type": "LS", "method_params": {"l": 2, "s": 4},
                    "measures": [
                        {"measure_category": "engineering", "description": "定期检查连接件"},
                        {"measure_category": "management", "description": "按规程操作"},
                    ],
                }],
            }],
        }],
    },
    {
        "name": TANK_ZONE,
        "objects": [{
            "name": "1号储罐", "category": "储罐", "is_risk_point": False,
            "units": [{"name": "罐体", "unit_type": "设备", "events": []}],
        }],
    },
]


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def call_data(method, path, token, body=None):
    return call(method, path, token, body)["data"]


def build_fixture(token: str) -> dict:
    stamp = int(time.time() * 1000)
    ent = call_data("POST", "/enterprises", token, {"name": f"E2E_SGMulti_{stamp}"})["id"]
    pump_ids = [
        call_data("POST", f"/enterprises/{ent}/risk-management/zones", token, {"name": PUMPS})["id"]
        for _ in range(3)
    ]
    tank_zone = call_data("POST", f"/enterprises/{ent}/risk-management/zones", token, {"name": TANK_ZONE})["id"]
    return {"enterprise": ent, "pump_zones": pump_ids, "tank_zone": tank_zone}


def zone_stats(token: str, ent: str) -> list[dict]:
    zones = call_data("GET", f"/enterprises/{ent}/risk-management/hierarchy", token)
    out = []
    for z in zones:
        objs = []
        for o in z.get("objects", []):
            units = o.get("units", [])
            evs = o.get("events", [])
            measures = sum(len(m.get("measures", [])) for e in evs for m in [e])
            unit_measures = sum(
                len(m.get("measures", []))
                for u in units for e in u.get("events", []) for m in [e]
            )
            objs.append({
                "name": o["name"],
                "unit_count": len(units),
                "event_count": len(evs) + sum(len(u.get("events", [])) for u in units),
                "measure_count": measures + unit_measures,
            })
        out.append({"zone": z["name"], "objects": objs})
    return out


def main() -> int:
    checks: dict[str, bool] = {}
    detail: dict = {}
    errors: list[str] = []

    token = call_data("POST", "/auth/login", None, {"email": U, "password": P})["access_token"]
    fx = build_fixture(token)
    detail["fixture"] = fx

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1600, "height": 950}, locale="zh-CN")
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: errors.append(f"console:{m.text[:140]}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))

        # mock AI 响应（固定 1 段「加油机」，验证前端分发），其余请求走真实后端
        def fulfill_guide(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"code": 0, "message": "ok",
                                 "data": {"hierarchy": MOCK_HIERARCHY, "summary": {}}}),
            )

        page.route(re.compile(r".*/risk-management/ai/smart-guide.*"), fulfill_guide)

        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2000)
        page.fill('input[placeholder="邮箱"]', U)
        page.fill('input[placeholder="密码"]', P)
        page.get_by_role("button", name=re.compile(r"\s*".join("登录"))).first.click()
        page.wait_for_timeout(3500)

        page.goto(f"{BASE}/enterprises/{fx['enterprise']}/risk-management", wait_until="load", timeout=40000)
        page.get_by_role("button", name=re.compile("添加分区")).first.wait_for(state="visible", timeout=15000)
        page.wait_for_timeout(1500)

        page.get_by_role("button", name=re.compile(r"智能导引")).first.click()
        page.wait_for_timeout(800)
        page.locator(".ant-modal textarea").first.fill("加油机区域需要补全")
        page.get_by_role("button", name=re.compile("AI 分析")).first.click()
        page.get_by_text(re.compile("AI 已按企业档案与现有风险树查漏补缺")).wait_for(
            state="visible", timeout=30000
        )
        page.wait_for_timeout(600)

        modal = page.locator(".ant-modal:visible").last
        distribute_badge = modal.get_by_text("并入 ×3", exact=True).count() > 0
        checks["distribute_badge_shown"] = distribute_badge
        detail["preview"] = {"distribute_badge_x3": distribute_badge,
                             "tree_nodes": modal.locator(".ant-tree-treenode").count()}
        page.screenshot(path=str(OUT / "smart-guide-multi-zone-preview.png"), full_page=True)

        modal.get_by_role("button", name=re.compile("确认并导入全部")).first.click()
        page.get_by_text(re.compile("导入完成")).wait_for(state="visible", timeout=30000)
        page.wait_for_timeout(1200)
        detail["import_toast"] = page.get_by_text(re.compile("导入完成")).first.inner_text()

        after = zone_stats(token, fx["enterprise"])
        detail["after_import"] = after
        pump_zones = [z for z in after if z["zone"] == PUMPS]
        checks["all_pump_zones_visible"] = len(pump_zones) == 3
        checks["all_pump_zones_filled"] = len(pump_zones) == 3 and all(
            len(z["objects"]) >= 1 for z in pump_zones
        )
        checks["pump_obj_has_children"] = len(pump_zones) == 3 and all(
            o["unit_count"] >= 1 and o["event_count"] >= 1 and o["measure_count"] >= 2
            for z in pump_zones for o in z["objects"]
        )
        tank_zones = [z for z in after if z["zone"] == TANK_ZONE]
        checks["tank_zone_new_object_created"] = (
            len(tank_zones) == 1 and any(o["name"] == "1号储罐" for o in tank_zones[0]["objects"])
        )
        checks["no_console_errors"] = len(errors) == 0
        ctx.close()
        browser.close()

    result = {"checks": checks, "detail": detail, "errors": errors[:20],
              "passed": all(checks.values())}
    (OUT / "smart-guide-multi-zone.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"checks": checks, "errors": errors[:5]}, ensure_ascii=False, indent=2))
    print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
