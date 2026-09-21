"""真浏览器验证「版本对比」新 UI（零 AI）：

造 2 个有差异的版本 → 打开版本页 → 点"对比" → 断言弹窗出现新增/修改分组与新正文 → 清理。
"""
import os
import re
import sys

import httpx
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_BASE", "http://host.docker.internal:8082")
API = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
OUT = "/app/exports/_preview"
V1_BODY = "<h3>总则</h3><p>第一版正文（对比验证）。</p>"
V2_BODY = "<h3>总则</h3><p>第二版正文——这里改了内容，用于验证 diff。</p>"

rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:32s} {detail}", flush=True)


def main() -> int:
    created_versions: list[str] = []
    with httpx.Client(timeout=60) as c:
        token = (c.post(f"{API}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                   "password": "test123456"}).json()
                 .get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}

        before = c.get(f"{API}/plans/{PLAN}/versions", headers=h).json().get("data") or []
        print(f"前置：现有版本 {len(before)} 个")

        def make_version(note: str, body: str) -> str:
            c.put(f"{API}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": body})
            r = c.post(f"{API}/plans/{PLAN}/versions", headers=h, json={"description": note})
            vid = (r.json().get("data") or {}).get("id")
            if vid:
                created_versions.append(vid)
            return vid

        v_a = make_version("对比验证-旧", V1_BODY)
        v_b = make_version("对比验证-新", V2_BODY)
        print(f"造版本：A={v_a} B={v_b}")
        versions = c.get(f"{API}/plans/{PLAN}/versions", headers=h).json().get("data") or []
        nums = sorted({v["version_number"] for v in versions}, reverse=True)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:160]}"))

            page.goto(f"{APP}/login", wait_until="load", timeout=60000)
            page.wait_for_timeout(1500)
            page.fill('input[id*="email"]', "qa_e2e_test@test.com")
            page.fill('input[type="password"]', "test123456")
            page.click('button[type="submit"]')
            page.wait_for_timeout(3500)

            page.goto(f"{APP}/plans/{PLAN}/versions", wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            body = page.locator("body").inner_text()
            rec("版本页出现「对比」按钮", "对比" in body)

            # antd 会给两字中文按钮插入空格（实际渲染「对 比」），所以用正则匹配
            page.get_by_role("button", name=re.compile(r"对\s*比")).first.click()
            page.wait_for_timeout(2500)
            modal = page.locator("[role=dialog]").first.inner_text()
            rec("弹窗显示分组统计", "新增" in modal and "修改" in modal, modal[:80].replace("\n", " "))
            rec("弹窗显示新旧正文", "第一版正文" in modal and "第二版正文" in modal)
            rec("弹窗含改前/改后标记", "改前" in modal and "改后" in modal)

            page.screenshot(path=os.path.join(OUT, "version-compare-ui.png"), full_page=False)
            rec("无 console/pageerror", not errs, f"{len(errs)} 条")
            browser.close()
    finally:
        with httpx.Client(timeout=60) as c:
            token = (c.post(f"{API}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                       "password": "test123456"}).json()
                     .get("data") or {}).get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            # 还原：清空该章正文（版本行由 SQL 清理，保持最小权限面）
            c.put(f"{API}/plans/{PLAN}/sections/sec_1", headers=h, json={"content": ""})
            for vid in created_versions:
                print(f"待清理版本 id={vid}")

    bad = [r for r in rows if not r[1]]
    print(f"\n==== 版本对比 UI：{len(rows)} 项，失败 {len(bad)}")
    for n, _, d in bad:
        print(f"   FAIL {n}: {d}")
    with open("/app/exports/_preview/version-compare-ids.txt", "w") as fh:
        fh.write("\n".join(created_versions))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
