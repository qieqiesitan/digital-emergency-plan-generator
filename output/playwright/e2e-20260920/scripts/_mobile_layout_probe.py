"""移动端布局重叠/重复标题实测（只读，一次性）。

用 DOM 几何而不是 full-page 截图判断：FAB 是否压住内容、TabBar 是否遮住列表末项、
「工作台」大标题是否重复。滚动到底后再测，避免视口位置造成的假象。
"""
import json
import os

from playwright.sync_api import sync_playwright

BASE = os.environ.get("MOBILE_BASE", "http://localhost:8082")
OUT = os.environ.get("PROBE_OUT", "output/playwright/e2e-20260920")
U, P = "qa_e2e_test@test.com", "test123456"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

MEASURE = """
() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
            bottom: Math.round(r.bottom), right: Math.round(r.right)};
  };
  const overlap = (a, b) => {
    if (!a || !b) return 0;
    const w = Math.min(a.right, b.right) - Math.max(a.x, b.x);
    const h = Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y);
    return w > 0 && h > 0 ? w * h : 0;
  };
  const texts = [...document.querySelectorAll('*')]
    .filter(e => e.children.length === 0 && (e.textContent || '').trim() === '工作台');
  const fab = document.querySelector('button[class*="rounded-full"]');
  const cards = [...document.querySelectorAll('div[class*="shadow-card"], div[class*="rounded-md"]')]
    .filter(e => e.getBoundingClientRect().height > 40);
  const tabbar = [...document.querySelectorAll('nav, div')]
    .find(e => /工作台/.test(e.textContent || '') && /设置/.test(e.textContent || '')
               && e.getBoundingClientRect().bottom >= window.innerHeight - 2
               && e.getBoundingClientRect().height < 120);
  const last = cards[cards.length - 1];
  return {
    heading_title_count: texts.length,
    heading_rects: texts.map(rect),
    fab: rect(fab),
    tabbar: rect(tabbar),
    last_card: rect(last),
    fab_overlap_last_card: overlap(rect(fab), rect(last)),
    tabbar_overlap_last_card: overlap(rect(tabbar), rect(last)),
    viewport: {w: window.innerWidth, h: window.innerHeight},
    doc_scroll_h: document.documentElement.scrollHeight,
  };
}
"""


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    out = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            locale="zh-CN",
            user_agent=UA,
        )
        page = ctx.new_page()
        page.goto(BASE + "/m/login", wait_until="load", timeout=30000)
        page.wait_for_timeout(1200)
        page.fill('input[type="email"]', U)
        page.fill('input[type="password"]', P)
        page.locator('button:has-text("登录")').last.click()
        page.wait_for_timeout(4000)

        for path, name in [("/m/dashboard", "dashboard"), ("/m/plans", "plans"), ("/m/enterprises", "enterprises")]:
            page.goto(BASE + path, wait_until="load", timeout=30000)
            page.wait_for_timeout(3000)
            page.evaluate("() => { const m = document.querySelector('main'); if (m) m.scrollTop = m.scrollHeight; else window.scrollTo(0, document.body.scrollHeight); }")
            page.wait_for_timeout(900)
            out[name] = page.evaluate(MEASURE)
            page.screenshot(path=os.path.join(OUT, f"layout-{name}.png"))

        browser.close()

    with open(os.path.join(OUT, "mobile-layout.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
