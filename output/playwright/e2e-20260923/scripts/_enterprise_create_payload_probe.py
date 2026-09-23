"""新建企业的真实提交载荷体检（浏览器抓包）。

背景（2026-09-23 用户实测）：提交时报 `industry：Input should be a valid string`。
接口层复现不出（只传 name = 201、空串数字 = 已修、AI 填充返回空 fields），
所以直接抓浏览器真实发出的请求体，看每个字段的类型。

用法（仓库根目录）：
    python output/playwright/e2e-20260923/scripts/_enterprise_create_payload_probe.py
证据输出：同目录 enterprise-create-payload.json
探针会创建一家临时企业并删除。
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:8082")
API = os.environ.get("E2E_API", "http://localhost:8000/api/v1")
OUT = Path(__file__).resolve().parent
USER = ("qa_e2e_test@test.com", "test123456")

STRING_FIELDS = {
    "name", "address", "industry", "business_scope", "credit_code",
    "legal_representative", "economic_type", "established_date", "phone", "fax",
    "postal_code", "safety_officer", "safety_officer_phone", "safety_standardization",
    "fire_approval", "fire_approval_date", "last_plan_filing_date",
    "last_plan_filing_authority", "main_products", "annual_capacity",
    "hazardous_chemicals", "special_equipment", "building_overview", "floor_plan_url",
}
NUMBER_FIELDS = {
    "employee_count", "registered_capital", "land_area", "building_area",
    "safety_staff_count", "gis_lat", "gis_lng",
}


def click_button(page, text: str) -> None:
    page.get_by_role("button", name=re.compile(r"\s*".join(text))).first.click(timeout=15000)


def api(method: str, path: str, token: str | None = None, body: dict | None = None):
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
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"error": exc.code, "body": exc.read()[:200].decode("utf-8", "ignore")}


def main() -> int:
    captured: list[dict] = []
    responses: list[dict] = []
    errors: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
        page = ctx.new_page()
        page.on("pageerror", lambda exc: errors.append(f"pageerror:{exc}"))
        page.on(
            "console",
            lambda msg: errors.append(f"console:{msg.text[:120]}")
            if msg.type == "error"
            else None,
        )

        def on_request(req):
            if req.method == "POST" and req.url.endswith("/api/v1/enterprises"):
                try:
                    captured.append({"url": req.url, "payload": req.post_data_json})
                except Exception:
                    captured.append({"url": req.url, "raw": (req.post_data or "")[:500]})

        def on_response(resp):
            if resp.request.method == "POST" and resp.url.endswith("/api/v1/enterprises"):
                responses.append({"status": resp.status, "body": resp.text()[:400]})

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        page.wait_for_selector('input[placeholder="邮箱"]', timeout=30000)
        page.fill('input[placeholder="邮箱"]', USER[0])
        page.fill('input[placeholder="密码"]', USER[1])
        click_button(page, "登录")
        page.wait_for_timeout(4000)

        page.goto(f"{BASE}/enterprises/new", wait_until="load", timeout=40000)
        page.wait_for_timeout(3000)
        page.fill('input[placeholder="请输入企业全称"]', "探针-提交载荷-可删")
        # 完整字段表单在「全部字段」抽屉里；行业字段只在抽屉中存在
        drawer_button = page.get_by_role("button", name=re.compile(r"全部字段"))
        if drawer_button.count() > 0:
            drawer_button.first.click()
            page.wait_for_timeout(1200)
            industry_input = page.locator('input[id$="industry"]')
            if industry_input.count() > 0:
                industry_input.first.fill("软件和信息技术服务业")
                page.wait_for_timeout(400)
            # 关掉抽屉，否则遮罩会挡住「创建企业」按钮
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)

        click_button(page, "创建企业")
        page.wait_for_timeout(5000)
        page.screenshot(path=str(OUT / "enterprise-create-submit.png"), full_page=True)
        browser.close()

    problems: list[dict] = []
    payload = captured[-1]["payload"] if captured and "payload" in captured[-1] else {}
    for key, value in (payload or {}).items():
        if key in STRING_FIELDS and value is not None and not isinstance(value, str):
            problems.append({"field": key, "expected": "str", "actual": type(value).__name__, "value": str(value)[:80]})
        elif key in NUMBER_FIELDS and value is not None and not isinstance(value, (int, float)):
            problems.append({"field": key, "expected": "number", "actual": type(value).__name__, "value": str(value)[:80]})

    checks = {
        "request_captured": bool(captured),
        "create_succeeded": any(r["status"] == 201 for r in responses),
        "no_type_problems": len(problems) == 0,
        "no_console_error": len(errors) == 0,
    }

    # 清理探针创建的企业
    cleanup: dict = {}
    if checks["create_succeeded"]:
        token = api("POST", "/auth/login", body={"email": USER[0], "password": USER[1]})["data"][
            "access_token"
        ]
        listing = api("GET", "/enterprises?page=1&page_size=100", token)
        for item in (listing.get("data") or {}).get("items") or []:
            if item.get("name") == "探针-提交载荷-可删":
                cleanup = api("DELETE", f"/enterprises/{item['id']}", token)
                break
    (OUT / "enterprise-create-payload.json").write_text(
        json.dumps(
            {
                "checks": checks,
                "payload": payload,
                "industry_type": type((payload or {}).get("industry")).__name__,
                "problems": problems,
                "responses": responses,
                "errors": errors[:5],
                "cleanup": cleanup,
                "all_passed": all(checks.values()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print("industry:", type((payload or {}).get("industry")).__name__, (payload or {}).get("industry"))
    print("类型问题:", problems)
    if responses:
        print("响应状态:", [r["status"] for r in responses])
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
