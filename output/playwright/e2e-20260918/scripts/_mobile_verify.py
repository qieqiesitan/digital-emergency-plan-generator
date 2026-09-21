"""移动端 M1-M6 精确复验：滚动到底后的遮挡/溢出/文案（一次性脚本）。"""
import json
import re

from playwright.sync_api import sync_playwright

BASE = "http://172.26.0.3:5173"
U, P = "qa_e2e_test@test.com", "test123456"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

MEASURE = """() => {
  const main = document.querySelector('main');
  const tab = Array.from(document.querySelectorAll('*')).find(el => {
    const r = el.getBoundingClientRect();
    return getComputedStyle(el).position === 'fixed' && r.bottom >= innerHeight - 2 && r.height > 40;
  });
  const out = {tabbarHeight: tab ? Math.round(tab.getBoundingClientRect().height) : null};
  if (!main || !tab) return out;
  main.scrollTop = main.scrollHeight;
  const tabTop = tab.getBoundingClientRect().top;
  const mainBottom = main.getBoundingClientRect().bottom;
  const lastChild = main.lastElementChild;
  const lastBottom = lastChild ? lastChild.getBoundingClientRect().bottom : null;
  out.mainScrollable = main.scrollHeight > main.clientHeight + 5;
  out.mainPaddingBottom = getComputedStyle(main).paddingBottom;
  out.tabTop = Math.round(tabTop);
  out.mainBottom = Math.round(mainBottom);
  out.lastChildBottom = lastBottom ? Math.round(lastBottom) : null;
  out.occluded = lastBottom !== null && lastBottom > tabTop + 1;
  out.horizontalOverflow = document.documentElement.scrollWidth > innerWidth + 1;
  out.text = document.body.innerText.slice(0, 300);
  return out;
}"""

out = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3,
                        is_mobile=True, has_touch=True, locale="zh-CN", user_agent=UA)
    page = ctx.new_page()
    page.goto(BASE + "/m/login", wait_until="load", timeout=40000)
    page.wait_for_timeout(1500)
    page.fill('input[type="email"]', U)
    page.fill('input[type="password"]', P)
    page.locator('button:has-text("登录")').last.click()
    page.wait_for_timeout(4000)
    for name, path in (("dashboard", "/m/dashboard"), ("enterprises", "/m/enterprises"),
                       ("plans", "/m/plans"), ("settings", "/m/settings")):
        page.goto(BASE + path, wait_until="load", timeout=40000)
        page.wait_for_timeout(2500)
        info = page.evaluate(MEASURE)
        info["fake_email"] = "user@example.com" in info.get("text", "")
        info["workbench_count"] = len(re.findall("工作台", info.get("text", "")))
        info["has_registered_word"] = "registered" in info.get("text", "")
        out[name] = info
        page.screenshot(path=f"/app/exports/mobile-{name}.png", full_page=False)
    b.close()

print(json.dumps(out, ensure_ascii=False, indent=1))
