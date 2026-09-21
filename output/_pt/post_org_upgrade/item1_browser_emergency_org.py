"""定向回归 ①：应急组织页浏览器级验证（预置 → 指派成员 → 保存 → 刷新持久化 → 级联删除）。"""
import os
import sys

import httpx
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_BASE", "http://host.docker.internal:8082")
API = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
ENT = "10e11995-e682-405a-9035-fbde13cca213"
MEMBER = "浏览器回归成员"

rows: list[tuple[str, bool, str]] = []


def rec(name: str, ok: bool, detail: str = "") -> None:
    rows.append((name, ok, detail))
    print(f"{'OK ' if ok else '!! '}{name:34s} {detail}", flush=True)


def confirm_modal(page, ok_text: str = "") -> bool:
    """点掉 antd 的 Modal.confirm：优先按 okText，否则点确认框里的主按钮。

    注意：antd 会把两字中文按钮渲染成「确 定」（中间插空格），按文本精确匹配会失败。
    """
    page.wait_for_timeout(500)
    if ok_text:
        btn = page.locator(f".ant-modal-confirm-btns button:has-text('{ok_text}')").last
        if btn.count() > 0:
            btn.click()
            return True
    btn = page.locator(".ant-modal-confirm-btns button.ant-btn-primary").last
    if btn.count() > 0:
        btn.click()
        return True
    return False


def main() -> int:
    with httpx.Client(timeout=60) as c:
        token = (c.post(f"{API}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                   "password": "test123456"}).json()
                 .get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}
        r = c.post(f"{API}/enterprises/{ENT}/org/members", headers=h,
                   json={"name": MEMBER, "role": "member"})
        mid = (r.json().get("data") or {}).get("id")
        print(f"前置：建成员 HTTP {r.status_code} id={mid}")

    errs: list[str] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1500, "height": 1000}, locale="zh-CN")
            page.on("console", lambda m: errs.append(f"{m.type}: {m.text[:160]}")
                    if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:160]}"))

            # 登录
            page.goto(f"{APP}/login", wait_until="load", timeout=60000)
            page.wait_for_timeout(1500)
            page.fill('input[id*="email"]', "qa_e2e_test@test.com")
            page.fill('input[type="password"]', "test123456")
            page.click('button[type="submit"]')
            page.wait_for_timeout(3500)

            # 打开应急组织页
            page.goto(f"{APP}/enterprises/{ENT}/emergency-org", wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            body = page.locator("body").inner_text()
            rec("① 页面渲染", "应急组织" in body and "添加顶层单元" in body,
                f"标题/按钮存在；{len(body)} 字")
            page.screenshot(path="/app/exports/_preview/emergency-org-1-empty.png", full_page=True)

            # ② 应用预置应急组织
            page.get_by_role("button", name="应用预置应急组织").click()
            page.wait_for_timeout(800)
            ok_clicked = confirm_modal(page)
            rec("②a 预置确认框可点", ok_clicked, "已点确认")
            page.wait_for_timeout(2600)
            body2 = page.locator("body").inner_text()
            rec("② 应用预置生成组织树", "应急指挥部" in body2 and "有未保存的修改" in body2,
                "树已生成且标记未保存")

            # ③ 选中「应急指挥部」并给必填角色指派成员
            page.get_by_text("应急指挥部", exact=True).first.click()
            page.wait_for_timeout(900)
            selects = page.locator(".ant-select-multiple")
            rec("③ 右侧出现角色多选", selects.count() >= 1, f"多选框 {selects.count()} 个")
            if selects.count() >= 1:
                selects.first.click()
                page.wait_for_timeout(600)
                opt = page.locator(f".ant-select-item-option:has-text('{MEMBER}')").first
                if opt.count() > 0:
                    opt.click()
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                    rec("③ 指派成员", True, f"已选 {MEMBER}")
                else:
                    rec("③ 指派成员", False, "下拉里没有该成员")

            # ④ 保存
            page.get_by_role("button", name="保存").click()
            page.wait_for_timeout(3000)
            body4 = page.locator("body").inner_text()
            rec("④ 保存成功", "有未保存的修改" not in body4, "未保存标记已消失")
            page.screenshot(path="/app/exports/_preview/emergency-org-2-saved.png", full_page=True)

            # ⑤ 刷新后持久化（成员指派仍在）
            page.reload(wait_until="load")
            page.wait_for_timeout(2600)
            page.get_by_text("应急指挥部", exact=True).first.click()
            page.wait_for_timeout(900)
            sel_text = page.locator(".ant-select-multiple").first.inner_text()
            rec("⑤ 刷新后指派仍存在", MEMBER in sel_text, f"多选内容={sel_text[:40]!r}")

            # ⑥ 级联删除根单元
            node = page.locator(".ant-tree-treenode:not([aria-hidden='true'])").first
            node.hover()
            page.wait_for_timeout(300)
            node.locator(".anticon-delete").first.click()
            page.wait_for_timeout(800)
            confirm_modal(page, ok_text="删除")
            page.wait_for_timeout(1200)
            page.get_by_role("button", name="保存").click()
            page.wait_for_timeout(2600)
            page.reload(wait_until="load")
            page.wait_for_timeout(2600)
            body6 = page.locator("body").inner_text()
            rec("⑥ 级联删除后组织为空", "暂无应急组织" in body6, "空态提示出现")

            browser.close()
    except Exception as exc:  # noqa: BLE001
        rec("浏览器流程异常", False, f"{type(exc).__name__}: {str(exc)[:140]}")
    finally:
        with httpx.Client(timeout=60) as c:
            token = (c.post(f"{API}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                       "password": "test123456"}).json()
                     .get("data") or {}).get("access_token")
            h = {"Authorization": f"Bearer {token}"}
            c.put(f"{API}/enterprises/{ENT}/emergency-org", headers=h, json={"units": []})
            if mid:
                c.delete(f"{API}/enterprises/{ENT}/org/members/{mid}", headers=h)
            print("清理：应急组织清空 + 成员删除")

    bad = [r for r in rows if not r[1]]
    print(f"\n==== ① 应急组织页浏览器验证：{len(rows)} 项，失败 {len(bad)}")
    for n, _, d in bad:
        print(f"   FAIL {n}: {d}")
    if errs:
        print(f"console/pageerror {len(errs)} 条：")
        for e in errs[:5]:
            print(f"   !! {e}")
    return 1 if bad or errs else 0


if __name__ == "__main__":
    sys.exit(main())
