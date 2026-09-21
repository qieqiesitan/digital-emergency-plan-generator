"""「报告无数据时重复报错」复现/回归探针。

两条路径都测：
  A 无数据（企业还没生成报告）：期望 **1 次**请求、HTTP 200、0 个错误 toast、0 条控制台报错，
    页面显示「尚未生成」空态。（修复前：每个 tab 2 次 404 + 1 个错误 toast + 4 条控制台报错）
  B 有数据（直接补一行已完成报告）：期望报告正文正常渲染、同样 0 报错（回归：空态改动别把有数据搞坏）

用法（仓库根目录）：
    python output/playwright/e2e-20260921/scripts/_empty_report_error_probe.py
环境变量：
    E2E_BASE  前端地址，默认 dev 服务器 http://localhost:15173（StrictMode 双挂载）
    E2E_API   后端地址，默认 http://localhost:8000/api/v1
证据输出：同目录 empty-report-errors.json + 4 张截图

夹具：新建两个企业（空的 / 带报告的），与其他探针一致不清理。带报告企业直接往库里插
已完成报告行（AI 生成会真的调模型，不适合当夹具）。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

API = os.environ.get("E2E_API", "http://localhost:8000/api/v1")
BASE = os.environ.get("E2E_BASE", "http://localhost:15173")
OUT = Path(__file__).resolve().parent
U, P = "qa_e2e_test@test.com", "test123456"
DB_CONTAINER, DB_NAME, DB_USER = "emergency-plan-db", "emergency_plan", "postgres"

# 报告「读取正文」接口：空报告时后端返回 404，属于预期空态
LOAD_PATHS = {
    "risk": re.compile(r"/enterprises/[^/]+/risk-assessment$"),
    "resource": re.compile(r"/enterprises/[^/]+/resource-investigation$"),
}

RISK_CHAPTER = ("ch1_hazard_id", "一、危险有害因素辨识分析")
RESOURCE_CHAPTER = ("ch1_purpose", "一、调查目的与依据")
REPORT_BODY = "这是验收用的报告正文。"


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


def seed_completed_report(enterprise: str, table: str, chapter: tuple[str, str]) -> None:
    """直接插一行已完成报告（避开 AI 生成依赖），供「有数据」路径使用。"""
    key, title = chapter
    summary = json.dumps(
        {"chapters": [{"key": key, "title": title, "content": REPORT_BODY}]},
        ensure_ascii=False,
    )
    sql = (
        # id 由应用层 uuid4 生成（模型里没有 DB 默认值），这里显式给一个
        f"INSERT INTO {table} (id, enterprise_id, title, content, summary, status, generated_by) "
        f"VALUES (gen_random_uuid(), '{enterprise}', '{title}', '{REPORT_BODY}', "
        f"'{summary}'::jsonb, 'completed', 'ai');"
    )
    subprocess.run(
        ["docker", "exec", "-i", DB_CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-v", "ON_ERROR_STOP=1"],
        input=sql.encode("utf-8"),
        check=True,
        capture_output=True,
    )


def visit(
    ctx,
    label: str,
    kind: str,
    url: str,
    detail: dict,
    expect_chapter: tuple[str, str] | None,
) -> dict:
    """开一个新页（登录态来自共享 context）打开模块页，统计请求次数 / toast / 控制台报错。"""
    console_errors: list[str] = []
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: console_errors.append(f"{m.type}:{m.text[:150]}") if m.type == "error" else None,
    )
    page.on("pageerror", lambda exc: console_errors.append(f"pageerror:{exc}"))
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
            const seen = new WeakSet();
            const scan = () => document.querySelectorAll('.ant-message-notice').forEach((n) => {
                if (seen.has(n)) return;   // 每个 toast 节点只记一次（MutationObserver 会多次回调）
                seen.add(n);
                const text = (n.innerText || '').trim();
                if (text) window.__toasts.push(text);
            });
            scan();
            new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
        }"""
    )
    # 留足时间：StrictMode 双挂载 + 首个请求回包 + toast 出现与消失
    page.wait_for_timeout(8000)

    record["toasts"] = len(page.evaluate("() => window.__toasts"))
    record["toast_texts"] = sorted(set(page.evaluate("() => window.__toasts")))
    record["live_notices"] = page.locator(".ant-message-notice").count()
    record["load_request_count"] = len(record["load_requests"])
    record["load_statuses"] = [r["status"] for r in record["load_requests"]]
    record["console_errors"] = list(console_errors)
    body = page.inner_text("body")
    record["empty_hint_shown"] = "尚未生成" in body
    record["report_rendered"] = REPORT_BODY in body
    record["chapter_title_shown"] = bool(expect_chapter) and expect_chapter[1] in body
    detail[label] = record
    page.screenshot(path=str(OUT / f"empty-report-{label}.png"), full_page=True)
    page.close()
    return record


def main() -> int:
    checks: dict[str, bool] = {}
    detail: dict = {}

    token = call_data("POST", "/auth/login", None, {"email": U, "password": P})["access_token"]
    stamp = int(time.time() * 1000)
    empty_ent = call_data("POST", "/enterprises", token, {"name": f"E2E_EmptyReport_{stamp}"})["id"]
    data_ent = call_data("POST", "/enterprises", token, {"name": f"E2E_HasReport_{stamp}"})["id"]
    seed_completed_report(data_ent, "risk_assessment_reports", RISK_CHAPTER)
    seed_completed_report(data_ent, "resource_investigation_reports", RESOURCE_CHAPTER)
    detail["fixtures"] = {"empty_enterprise": empty_ent, "has_report_enterprise": data_ent}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        login = ctx.new_page()
        login.goto(f"{BASE}/login", wait_until="load", timeout=40000)
        login.wait_for_timeout(2500)
        login.fill('input[placeholder="邮箱"]', U)
        login.fill('input[placeholder="密码"]', P)
        click_button(login, "登录")
        login.wait_for_timeout(4000)
        login.close()

        visits: list[tuple[str, str, str, tuple[str, str] | None]] = [
            ("empty-risk", "risk", f"{BASE}/enterprises/{empty_ent}/modules/assessment", None),
            ("empty-resource", "resource", f"{BASE}/enterprises/{empty_ent}/modules/investigation", None),
            ("data-risk", "risk", f"{BASE}/enterprises/{data_ent}/modules/assessment", RISK_CHAPTER),
            ("data-resource", "resource", f"{BASE}/enterprises/{data_ent}/modules/investigation", RESOURCE_CHAPTER),
        ]
        for label, kind, url, chapter in visits:
            record = visit(ctx, label, kind, url, detail, chapter)
            record["console_error_count"] = len(record["console_errors"])

            # 通用：只发 1 次请求（StrictMode 双挂载已被合并）、HTTP 200、无报错、无错误 toast
            checks[f"{label}_single_request"] = record["load_request_count"] == 1
            checks[f"{label}_http_200"] = record["load_statuses"] == [200]
            checks[f"{label}_no_error_toast"] = record["toasts"] == 0
            checks[f"{label}_no_console_error"] = record["console_error_count"] == 0
            if chapter is None:
                checks[f"{label}_shows_empty_state"] = record["empty_hint_shown"]
            else:
                checks[f"{label}_renders_report"] = record["report_rendered"]
                checks[f"{label}_shows_chapter_title"] = record["chapter_title_shown"]

        browser.close()

    (OUT / "empty-report-errors.json").write_text(
        json.dumps({"checks": checks, "detail": detail, "all_passed": all(checks.values())},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print("all_passed:", all(checks.values()))
    for label, _, _, _ in visits:
        rec = detail[label]
        print(f"[{label}] requests={rec['load_request_count']} statuses={rec['load_statuses']} "
              f"toasts={rec['toasts']}{rec['toast_texts']} console_errors={rec['console_errors']}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
