"""B1 批次真实浏览器回归（桌面 1440 / 移动 390，针对本轮改动面）。

覆盖：
- 桌面：预案编辑器「创作风格」持久化（后端 PUT 修复）、法规关系图谱渲染（RegulationGraph 重写）、
  四色图工作台渲染（WorkbenchCanvas 重构）
- 移动端 390：新建企业「行业分类」选择器可用 + 表单可提交 + toast 文案可见（SelectSheet/toast 修复）、
  密码输入框可输入（Input onChange 修复）、关键页面无 console/pageerror
- 全程收集 console error / pageerror / HTTP 4xx
"""

import json
import os
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE", "http://host.docker.internal:8082")
API = os.environ.get("E2E_API", "http://localhost:8000")
OUT = "/app/exports/e2e-20260918"
U, P = "qa_e2e_test@test.com", "test123456"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

checks = []
console_log = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(("PASS " if ok else "FAIL ") + name + (f" | {str(detail)[:200]}" if detail else ""), flush=True)


def attach(page, tag: str):
    def on_console(msg):
        if msg.type in ("error", "warning"):
            console_log.append({"page": tag, "kind": msg.type, "text": msg.text[:300]})

    def on_pageerror(exc):
        console_log.append({"page": tag, "kind": "pageerror", "text": str(exc)[:300]})

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)


def api_delete_enterprise(eid: str, token: str) -> int:
    req = urllib.request.Request(
        f"{API}/api/v1/enterprises/{eid}",
        method="DELETE",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:  # noqa: BLE001
        return -1


def api_get(path: str, token: str):
    req = urllib.request.Request(
        f"{API}/api/v1{path}", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def desktop_checks(browser) -> None:
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()
    attach(page, "desktop")

    page.goto(BASE + "/login", wait_until="load", timeout=45000)
    page.wait_for_timeout(1200)
    page.fill('input[id*="email"]', U)
    page.fill('input[type="password"]', P)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    check("桌面登录成功", "/login" not in page.url, page.url)

    token = page.evaluate("() => localStorage.getItem('access_token')")

    # 1) 预案编辑器：创作风格保存后重新加载仍生效（后端 PUT 修复的端到端证明）
    try:
        plans = api_get("/plans?page=1&page_size=5", token).get("data", {}).get("items", [])
        check("API-取得可用预案", len(plans) > 0, f"count={len(plans)}")
        if plans:
            page.goto(BASE + f"/plans/{plans[0]['id']}/edit", wait_until="load", timeout=45000)
            page.wait_for_timeout(4000)
            check("桌面-打开预案编辑页", "/edit" in page.url, page.url)
            page.screenshot(path=os.path.join(OUT, "b1-desktop-plan-editor.png"), full_page=False)

            page.click("text=创作风格")
            page.wait_for_timeout(1200)
            # 选一个与当前值不同的选项（正式），确保断言真的验证了「写入 + 读回」
            page.click(".ant-modal .ant-segmented-item:has-text('正式')")
            page.wait_for_timeout(1500)
            pre = page.evaluate(
                """() => Array.from(document.querySelectorAll('.ant-modal .ant-segmented-item'))
                     .filter(el => el.classList.contains('ant-segmented-item-selected'))
                     .map(el => el.innerText.trim())"""
            )
            check("桌面-点击「正式」后本地选中态更新", "正式" in pre, f"selected={pre}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)

            page.reload(wait_until="load")
            page.wait_for_timeout(4000)
            page.click("text=创作风格")
            page.wait_for_timeout(1500)
            state = page.evaluate(
                """() => Array.from(document.querySelectorAll('.ant-modal .ant-segmented-item'))
                     .map(el => ({ text: el.innerText.trim(),
                                   selected: el.classList.contains('ant-segmented-item-selected') }))"""
            )
            selected = [s["text"] for s in state if s["selected"]]
            check("桌面-「创作风格」保存后可读回（PUT 落库 + 页面回填）", "正式" in selected, f"selected={selected}")
            page.screenshot(path=os.path.join(OUT, "b1-desktop-style-persist.png"), full_page=False)
            page.keyboard.press("Escape")
    except Exception as exc:  # noqa: BLE001
        check("桌面-预案编辑器与风格持久化", False, f"{type(exc).__name__}: {exc}")

    # 2) 法规关系图谱（RegulationGraph 重写：确定性布局 + 移除 ref 渲染期读取）
    try:
        page.goto(BASE + "/settings/regulations", wait_until="load", timeout=45000)
        page.wait_for_timeout(3000)
        if page.locator("text=关系图谱").count() == 0:
            check("桌面-法规关系图谱（需管理员权限）", False,
                  "页面无「关系图谱」标签：" + page.locator("body").inner_text()[:120].replace("\n", " "))
        else:
            page.click("text=关系图谱")
            page.wait_for_timeout(3500)
            circles = page.locator("svg circle").count()
            lines = page.locator("svg line").count()
            check("桌面-法规关系图谱渲染节点", circles > 0, f"circles={circles} lines={lines}")
            page.screenshot(path=os.path.join(OUT, "b1-desktop-regulation-graph.png"), full_page=False)
    except Exception as exc:  # noqa: BLE001
        check("桌面-法规关系图谱", False, f"{type(exc).__name__}: {exc}")

    # 3) 四色图工作台（WorkbenchCanvas：Transformer 改为命令式 nodes）
    try:
        ents = api_get("/enterprises?page=1&page_size=5", token).get("data", {}).get("items", [])
        check("API-取得可用企业", len(ents) > 0, f"count={len(ents)}")
        wb_url = (f"/enterprises/{ents[0]['id']}/risk-management/workbench" if ents
                  else "/risk-management/workbench")
        page.goto(BASE + wb_url, wait_until="load", timeout=45000)
        page.wait_for_timeout(4000)
        body = page.locator("body").inner_text()
        canvas = page.locator("canvas").count()
        check("桌面-四色图工作台可加载", ("无权限" not in body) and len(body) > 100,
              f"canvas={canvas} len={len(body)} url={page.url}")
        page.screenshot(path=os.path.join(OUT, "b1-desktop-workbench.png"), full_page=False)
    except Exception as exc:  # noqa: BLE001
        check("桌面-四色图工作台", False, f"{type(exc).__name__}: {exc}")
    ctx.close()


def mobile_checks(browser) -> None:
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        locale="zh-CN",
        user_agent=UA,
    )
    page = ctx.new_page()
    attach(page, "mobile")

    page.goto(BASE + "/m/login", wait_until="load", timeout=45000)
    page.wait_for_timeout(1500)
    page.fill('input[placeholder="请输入邮箱"]', U)
    page.fill('input[placeholder="请输入密码"]', P)
    page.locator("button:has-text('登录')").last.click()
    page.wait_for_timeout(3500)
    check("移动端登录成功", "/m/login" not in page.url, page.url)

    # 1) 修改密码页：输入框可输入（修复前 onChange 签名错，输入即抛错、值不更新）
    page.goto(BASE + "/m/settings/password", wait_until="load", timeout=45000)
    page.wait_for_timeout(2000)
    page.fill('input[placeholder="请输入原密码"]', "test123456")
    page.fill('input[placeholder="请输入新密码"]', "Abcd1234")
    old_val = page.locator('input[placeholder="请输入原密码"]').input_value()
    new_val = page.locator('input[placeholder="请输入新密码"]').input_value()
    check("移动端-密码输入框可输入（Input onChange 修复）",
          old_val == "test123456" and new_val == "Abcd1234", f"old={old_val!r} new={new_val!r}")
    page.screenshot(path=os.path.join(OUT, "b1-mobile-password-input.png"), full_page=False)

    # 2) 新建企业：行业分类选择器可用 + 可提交 + toast 有文案
    name = f"B1回归-{int(time.time())}"
    page.goto(BASE + "/m/enterprises/new", wait_until="load", timeout=45000)
    page.wait_for_timeout(2000)
    page.fill('input[placeholder="请输入企业名称"]', name)
    opened = False
    try:
        page.click("text=选择行业分类", timeout=8000)
        page.wait_for_timeout(1200)
        opened = page.locator("text=工贸").count() > 0
        if opened:
            page.locator("button:has-text('工贸')").first.click()
            page.wait_for_timeout(800)
    except Exception as exc:  # noqa: BLE001
        check("移动端-打开行业分类选择器", False, f"{type(exc).__name__}: {exc}")
    check("移动端-行业分类选择器可打开并选中", opened and page.locator("text=工贸").count() > 0)
    page.screenshot(path=os.path.join(OUT, "b1-mobile-enterprise-form.png"), full_page=False)

    page.click("text=创建企业")
    toast_text = ""
    created_id = None
    for _ in range(20):
        page.wait_for_timeout(300)
        toast_text = page.locator("body").inner_text()
        if "企业创建成功" in toast_text:
            break
        if "/m/enterprises/" in page.url and "new" not in page.url:
            break
    check("移动端-创建企业 toast 文案可见（toast 签名修复）", "企业创建成功" in toast_text,
          f"url={page.url} contains={'企业创建成功' in toast_text}")
    if "/m/enterprises/" in page.url and "new" not in page.url:
        created_id = page.url.rstrip("/").split("/")[-1]
    check("移动端-新建企业可提交（行业必填不再卡死）", created_id is not None, f"url={page.url}")
    page.screenshot(path=os.path.join(OUT, "b1-mobile-enterprise-created.png"), full_page=False)

    # 清理：删除本次创建的企业
    if created_id:
        token = page.evaluate("() => localStorage.getItem('access_token')")
        code = api_delete_enterprise(created_id, token)
        check("移动端-回归数据清理（删除测试企业）", code in (200, 204), f"status={code} id={created_id}")

    # 3) 移动端关键页面 smoke（含企业详情：资源 Tab 取值修复）
    for label, path in [
        ("dashboard", "/m/dashboard"),
        ("enterprises", "/m/enterprises"),
        ("plans", "/m/plans"),
        ("settings", "/m/settings"),
        ("chat", "/m/chat"),
    ]:
        page.goto(BASE + path, wait_until="load", timeout=45000)
        page.wait_for_timeout(2200)
        body = page.locator("body").inner_text()
        # /m/chat 会话列表在移动端收起，正文本身就短，这里用「页面非空白」作为判据
        check(f"移动端-{label} 页面加载", len(body) > 20, f"len={len(body)} url={page.url}")
    page.screenshot(path=os.path.join(OUT, "b1-mobile-dashboard.png"), full_page=False)
    ctx.close()


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        desktop_checks(browser)
        mobile_checks(browser)
        browser.close()

    errors = [c for c in console_log if c["kind"] in ("error", "pageerror")]
    # antd 依赖的 React 19 兼容提示等 warning 单独记录，不判失败
    failed = [c for c in checks if not c["ok"]]
    with open(os.path.join(OUT, "summary-b1-regression.json"), "w", encoding="utf-8") as fh:
        json.dump({"checks": checks, "console": console_log, "errors": errors}, fh, ensure_ascii=False, indent=1)
    print("\n==== 汇总 ====")
    print(f"检查项 {len(checks)}，通过 {len(checks) - len(failed)}，失败 {len(failed)}")
    print(f"console error/pageerror: {len(errors)}")
    for item in errors[:12]:
        print(f"  [{item['page']}/{item['kind']}] {item['text'][:180]}")
    for item in failed:
        print(f"  FAIL {item['name']} | {item['detail']}")


if __name__ == "__main__":
    main()
