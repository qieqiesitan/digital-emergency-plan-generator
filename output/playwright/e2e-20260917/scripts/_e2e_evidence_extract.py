"""抓取两条结论的精确文本证据（A19 单位重复、M1 假邮箱、M3 标题重复）。"""
import json
import re

from playwright.sync_api import sync_playwright

BASE = "http://shuzihuayuan:8080"
ENT = "e62bb772-a29f-4e48-89a4-9182f13ca86f"
U, P = "qa_e2e_test@test.com", "test123456"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
out = {}

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    p = ctx.new_page()
    p.goto(BASE + "/login"); p.fill('input[id*="email"]', U); p.fill('input[type="password"]', P)
    p.click('button[type="submit"]'); p.wait_for_timeout(3000)
    p.goto(BASE + f"/enterprises/{ENT}/hazard/dashboard", wait_until="load"); p.wait_for_timeout(3000)
    txt = p.locator("body").inner_text()
    out["A19_matches"] = [txt[max(0, m.start() - 40):m.end() + 40].replace("\n", " | ")
                          for m in re.finditer(r"条\s*条|个\s*个|条/0?个", txt)][:5]

    mctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                         device_scale_factor=3, locale="zh-CN", user_agent=UA)
    m = mctx.new_page()
    m.goto(BASE + "/m/login"); m.wait_for_timeout(1500)
    m.fill('input[type="email"]', U); m.fill('input[type="password"]', P)
    m.locator('button:has-text("登录")').last.click(); m.wait_for_timeout(4000)
    m.goto(BASE + "/m/settings", wait_until="load"); m.wait_for_timeout(2500)
    st = m.locator("body").inner_text()
    out["M1_settings_text"] = re.sub(r"\s+", " | ", st)[:400]
    out["M1_fake_email_context"] = [st[max(0, mm.start() - 60):mm.end() + 40].replace("\n", " | ")
                                    for mm in re.finditer("user@example\\.com", st)][:3]
    m.goto(BASE + "/m/dashboard", wait_until="load"); m.wait_for_timeout(2500)
    dt = m.locator("body").inner_text()
    out["M3_dashboard_head"] = re.sub(r"\s+", " | ", dt)[:300]
    out["M3_workbench_count"] = len(re.findall("工作台", dt))
    b.close()

print(json.dumps(out, ensure_ascii=False, indent=1))
