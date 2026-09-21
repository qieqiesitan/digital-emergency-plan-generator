"""dev 模式下捕获 antd 弃用告警：确认 SimpleList 替换后不再出现 `[antd: List] deprecated`。

与 `_b1_broad_smoke.py` 的差别：冒烟只抓 console.error，而 antd 弃用是 console.warn，
所以这里单独抓 warning/error（生产构建会剥离告警，必须打 dev 服务器）。
"""
import os
import re

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://localhost:5173")
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"

# (标签, 路径, 载入后尝试点击的按钮文案)
TARGETS = [
    ("dashboard", "/dashboard", ["切换企业", "选择企业"]),
    ("risk-management", f"/enterprises/{ENT}/risk-management/overview", ["楼层管理", "迁移", "导入"]),
    ("risk-workbench", f"/enterprises/{ENT}/risk-management/workbench", ["导入", "四色", "迁移"]),
    ("major-hazard", f"/enterprises/{ENT}/major-hazard", ["依据", "详情"]),
    ("plan-editor", f"/plans/{PLAN}/edit", ["高级", "风格", "章节"]),
    ("notice-cards", f"/enterprises/{ENT}/risk-management/notice-cards", ["预览", "生成"]),
]


def main():
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        msgs = []
        page.on("console", lambda m: msgs.append((m.type, m.text[:300])) if m.type in ("warning", "error") else None)
        page.on("pageerror", lambda e: msgs.append(("pageerror", str(e)[:300])))

        # 阳性对照：对照页左侧渲染的是 antd 原生 List，必须能看到弃用告警，
        # 否则说明探针的 console 钩子失效（0 告警就不能作为证据）。
        ctrl = []
        try:
            page.goto(BASE + "/src/list-parity.html", wait_until="networkidle", timeout=60000)
            page.wait_for_selector("section[data-case='1']", timeout=30000)
            page.wait_for_timeout(1500)
            ctrl = [m for m in msgs if "List" in m[1] and "deprecated" in m[1]]
            print(f"{'OK ' if ctrl else '!! '}阳性对照（antd List 对照页）：抓到弃用告警 {len(ctrl)} 条")
        except Exception as exc:  # noqa: BLE001
            print(f"!! 阳性对照失败：{type(exc).__name__}: {exc}")
        msgs.clear()

        page.goto(BASE + "/login", wait_until="load", timeout=45000)
        page.wait_for_timeout(1500)
        page.fill('input[id*="email"]', U)
        page.fill('input[type="password"]', P)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)

        for name, path, clicks in TARGETS:
            msgs.clear()
            try:
                page.goto(BASE + path, wait_until="load", timeout=45000)
                page.wait_for_timeout(2500)
                for text in clicks:
                    try:
                        loc = page.locator(f"button:has-text('{text}'), a:has-text('{text}')").first
                        if loc.count() > 0 and loc.is_visible():
                            loc.click(timeout=3000)
                            page.wait_for_timeout(1500)
                    except Exception:  # noqa: BLE001
                        pass
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
            except Exception as exc:  # noqa: BLE001
                msgs.append(("probe", f"{type(exc).__name__}: {exc}"[:200]))
            row = [{"type": t, "text": x} for t, x in msgs]
            rows.append({"name": name, "path": path, "messages": row})
            list_dep = [m for m in row if "List" in m["text"] and "deprecated" in m["text"]]
            antd_dep = [m for m in row if "antd" in m["text"].lower() and "deprecat" in m["text"].lower()]
            warn = [m for m in row if m["type"] in ("warning", "error")]
            flag = "OK " if not list_dep else "!! "
            print(f"{flag}{name:16s} warnings/errors={len(warn)} antd弃用={len(antd_dep)} List弃用={len(list_dep)}",
                  flush=True)
            for m in row[:6]:
                print(f"      [{m['type']}] {re.sub(chr(10), ' ', m['text'])[:150]}")
        browser.close()

    all_msgs = [m for r in rows for m in r["messages"]]
    list_dep = [m for m in all_msgs if "List" in m["text"] and "deprecated" in m["text"]]
    antd_dep = [m for m in all_msgs if "antd" in m["text"].lower() and "deprecat" in m["text"].lower()]
    print(f"\n==== 汇总：{len(rows)} 页；warning/error {len(all_msgs)} 条；"
          f"antd 弃用 {len(antd_dep)} 条；List 弃用 {len(list_dep)} 条")
    for m in antd_dep[:5]:
        print(f"   ! {m['text'][:200]}")


if __name__ == "__main__":
    main()
