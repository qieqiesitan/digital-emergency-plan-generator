"""端到端驱动「AI 智能引导」：真实 UI 点击 → mock 供应商 → 三块写入。

验证点：弹窗能打开、生成的建议能渲染、三块能分别写入、结果文案正确。
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("APP_BASE", "http://127.0.0.1:8099")
ENT = "10e11995-e682-405a-9035-fbde13cca213"
U, P = "qa_e2e_test@test.com", "test123456"
OUT = os.environ.get("PREVIEW_OUT", "/app/exports/_preview")
os.makedirs(OUT, exist_ok=True)


def main() -> int:
    errs: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
        page.on("console", lambda m: errs.append(f"{m.type}: {m.text[:200]}")
                if m.type == "error" and "WebSocket" not in m.text and "[vite]" not in m.text else None)
        page.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:200]}"))

        # 登录
        page.goto(f"{BASE}/login", wait_until="load", timeout=60000)
        page.wait_for_timeout(1500)
        page.fill('input[id*="email"]', U)
        page.fill('input[type="password"]', P)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3500)

        # 排查计划页 → 打开智能引导
        page.goto(f"{BASE}/enterprises/{ENT}/hazard/plans", wait_until="load", timeout=60000)
        page.wait_for_timeout(3000)
        page.get_by_role("button", name="AI 智能引导").click()
        page.wait_for_timeout(800)
        page.screenshot(path=os.path.join(OUT, "wizard-1-form.png"), full_page=True)

        # 生成建议
        page.get_by_label("所属行业").fill("化工 / 危险化学品经营")
        page.get_by_label("主要区域（逗号分隔）").fill("储罐区、装卸区")
        page.get_by_role("button", name="生成建议").click()
        page.wait_for_selector("text=① 组织架构", timeout=90000)
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(OUT, "wizard-2-suggestions.png"), full_page=True)
        body2 = page.locator("body").inner_text()

        # 全部确认写入
        page.get_by_role("button", name="全部确认写入").click()
        page.wait_for_selector("text=已创建", timeout=90000)
        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(OUT, "wizard-3-written.png"), full_page=True)
        body3 = page.locator("body").inner_text()
        browser.close()

    checks = [
        ("弹窗打开并出现三块建议", "① 组织架构" in body2 and "② 排查计划" in body2 and "③ 检查表模板" in body2),
        ("组织架构合并写入成功", "组织架构已合并" in body3),
        ("排查计划创建成功", "已创建" in body3 and "排查计划" in body3),
        ("检查表模板创建成功", "检查表模板" in body3 or "已创建检查表模板" in body3),
    ]
    for name, ok in checks:
        print(f"{'✅' if ok else '❌'} {name}")
    print(f"\n结果区文案片段：\n{body3[body3.find('① 组织架构'):][:600] if '① 组织架构' in body3 else body3[:400]}")
    if errs:
        print("\nconsole/pageerror：")
        for e in errs[:6]:
            print(f"   !! {e}")
    return 0 if all(ok for _, ok in checks) and not errs else 1


if __name__ == "__main__":
    sys.exit(main())
