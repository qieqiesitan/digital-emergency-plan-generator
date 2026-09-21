"""「报告无数据时重复报错」复现/回归探针。

场景：企业尚未生成风险评估报告 / 应急资源调查报告，打开对应模块页。
量化三件事：
  1. 报告读取接口被请求了几次、返回码是什么（重复请求 = 控制台多份 404）
  2. 屏幕上弹了几个错误 toast（重复报错）
  3. 控制台 error 条数

用法（仓库根目录）：
    python output/playwright/e2e-20260921/scripts/_empty_report_error_probe.py
环境变量：
    E2E_BASE  前端地址，默认 dev 服务器 http://localhost:15173（StrictMode 双挂载）
    E2E_API   后端地址，默认 http://localhost:8000/api/v1
证据输出：同目录 empty-report-errors.json + 两张截图

夹具：只新建一个空企业（无任何报告），与其他探针一致不清理。
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
BASE = os.environ.get("E2E_BASE", "http://localhost:15173")
OUT = Path(__file__).resolve().parent
U, P = "qa_e2e_test@test.com", "test123456"

# 报告「读取正文」接口：空报告时后端返回 404，属于预期空态
LOAD_PATHS = {
    "risk": re.compile(r"/enterprises/[^/]+/risk-assessment$"),
    "resource": re.compile(r"/enterprises/[^/]+/resource-investigation$"),
}


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


def visit(page, kind: str, url: str, hits: dict, console_errors: list[str], detail: dict):
    """打开模块页，统计报告读取接口的请求次数与错误 toast 数量。"""
    record: dict = {"url": url, "load_requests": [], "toasts": 0, "toast_texts": []}
    page.on(
        "response",
        lambda r: record["load_requests"].append(
            {"status": r.status, "url": r.url}
        )
        if r.request.method == "GET" and LOAD_PATHS[kind].search(r.url)
        else None,
    )

    page.goto(url, wait_until="load", timeout=40000)
    # antd message 默认 3s 自动消失，必须实时采集，否则会漏掉已消失的 toast
    page.evaluate(
        """() => {
            window.__toasts = [];
            const scan = () => document.querySelectorAll('.ant-message-notice').forEach((n) => {
                const text = (n.innerText || '').trim();
                if (text && !window.__toasts.includes(text)) window.__toasts.push(text);
            });
            scan();
            new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
        }"""
    )
    # 留足时间：StrictMode 双挂载 + 首个请求回包 + toast 出现与消失
    page.wait_for_timeout(8000)

    record["toasts"] = len(page.evaluate("() => window.__toasts"))
    record["toast_texts"] = page.evaluate("() => window.__toasts")
    record["live_notices"] = page.locator(".ant-message-notice").count()
    record["load_request_count"] = len(record["load_requests"])
    record["load_statuses"] = [r["status"] for r in record["load_requests"]]
    record["console_errors"] = list(console_errors)
    record["page_hint_shown"] = page.get_by_text("尚未生成", exact=False).count()
    detail[kind] = record
    page.screenshot(path=str(OUT / f"empty-report-{kind}.png"), full_page=True)


def main() -> int:
    result: dict = {}
    detail: dict = {}
    console_errors: list[str] = []
    hits: dict = {}

    token = call_data("POST", "/auth/login", None, {"email": U, "password": P})["access_token"]
    stamp = int(time.time() * 1000)
    ent = call_data("POST", "/enterprises", token, {"name": f"E2E_EmptyReport_{stamp}"})["id"]
    detail["enterprise"] = ent

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: console_errors.append(f"{m.type}:{m.text[:150]}")
            if m.type == "error"
            else None,
        )
        page.on("pageerror", lambda exc: console_errors.append(f"pageerror:{exc}"))

        page.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        page.fill('input[placeholder="邮箱"]', U)
        page.fill('input[placeholder="密码"]', P)
        click_button(page, "登录")
        page.wait_for_timeout(4000)

        console_errors.clear()  # 登录过程的噪声与本次无关
        visit(page, "risk", f"{BASE}/enterprises/{ent}/modules/assessment", hits, console_errors, detail)
        risk_errors = list(console_errors)
        console_errors.clear()
        visit(page, "resource", f"{BASE}/enterprises/{ent}/modules/investigation", hits, console_errors, detail)

        browser.close()

    risk = detail["risk"]
    resource = detail["resource"]
    result["risk_load_request_count"] = risk["load_request_count"]
    result["risk_toast_count"] = risk["toasts"]
    result["risk_console_error_count"] = len(risk_errors)
    result["resource_load_request_count"] = resource["load_request_count"]
    result["resource_toast_count"] = resource["toasts"]
    result["resource_console_error_count"] = len(console_errors)

    (OUT / "empty-report-errors.json").write_text(
        json.dumps(
            {"summary": result, "detail": detail},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"summary": result, "detail": detail}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
