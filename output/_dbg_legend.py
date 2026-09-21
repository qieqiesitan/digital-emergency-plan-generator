"""调试：对比开发服务器(15173)与静态站(8082)的章节树图例文案。"""
import os

from playwright.sync_api import sync_playwright

U, P = "qa_e2e_test@test.com", "test123456"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"


def probe(base):
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(base + "/login", wait_until="load", timeout=45000)
        page.wait_for_timeout(1000)
        page.fill('input[type="email"], input[id*="email"]', U)
        page.fill('input[type="password"]', P)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)
        page.goto(base + f"/plans/{PLAN}/edit", wait_until="load", timeout=45000)
        page.wait_for_timeout(4500)
        body = page.inner_text("body")
        legend = ""
        for line in body.splitlines():
            if line.startswith("✓ 已完成"):
                legend = line
        print(f"[{base}] 图例: {legend or '(未找到)'}")
        print(f"[{base}] 含新文案: {'依赖数据已更新' in legend}")
        page.close()
        b.close()


for base in (os.environ.get("DEV_BASE", "http://localhost:15173"), "http://localhost:8082"):
    try:
        probe(base)
    except Exception as exc:  # noqa: BLE001
        print(f"[{base}] 失败: {exc}")
