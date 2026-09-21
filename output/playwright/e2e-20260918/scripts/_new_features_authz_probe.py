"""新功能模块跨租户越权探针（新增大功能的增量安全复验）。

覆盖 2026-09-18 新增/扩展的四个模块：
  - 组织架构与成员（enterprise_org，11 个端点）
  - 重大危险源（major_hazard，22 个端点）
  - 作业票（work_ticket，8 个端点）
  - AI 能力平台 / 数据接入 / 解析（platform・ingest・extraction，管理员专属）

判定口径：
  - 跨租户读 → 期望 404（契约规定用 404 而非 403，避免探测资源存在性）
  - 跨租户写 → 期望 403（企业主专属）
  - 管理员模块被普通用户访问 → 期望 403
  - 匿名访问 → 期望 401
  - 本企业读 → 200（对照组，证明探针本身可用）

所有写用例均为**无副作用**：目标企业的 org_structure 当前就是 []，PUT {"nodes": []} 等价于原值。
"""

import json
import urllib.error
import urllib.request

API = "http://localhost:8000/api/v1"
U, P = "qa_e2e_test@test.com", "test123456"
OWN_ENT = "10e11995-e682-405a-9035-fbde13cca213"
OTHER_ENT = "2f754692-ba53-41fd-a94a-ef8d553880ad"


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # 连接层异常单独标注，避免被当成业务码
        return -1, str(exc).encode()


def login():
    status, raw = call("POST", "/auth/login", body={"email": U, "password": P})
    assert status == 200, (status, raw[:200])
    return json.loads(raw)["data"]["access_token"]


CASES = [
    # (分组, 方法, 路径, 期望码, 说明)
    ("对照", "GET", f"/enterprises/{OWN_ENT}/org/nodes", 200, "本企业组织架构可读"),
    ("对照", "GET", f"/major-hazard/units?enterprise_id={OWN_ENT}", 200, "本企业重大危险源可读"),
    ("对照", "GET", f"/work-ticket/tickets?enterprise_id={OWN_ENT}", 200, "本企业作业票可读"),
    ("对照", "GET", "/work-ticket/templates", 200, "登录用户可用票面模板"),
    ("跨租户读", "GET", f"/enterprises/{OTHER_ENT}/org/nodes", 404, "组织架构跨租户被拒"),
    ("跨租户读", "GET", f"/enterprises/{OTHER_ENT}/org/members", 404, "通讯录跨租户被拒"),
    ("跨租户读", "GET", f"/major-hazard/units?enterprise_id={OTHER_ENT}", 404, "重大危险源跨租户被拒"),
    ("跨租户读", "GET", f"/work-ticket/tickets?enterprise_id={OTHER_ENT}", 404, "作业票跨租户被拒"),
    ("跨租户写", "PUT", f"/enterprises/{OTHER_ENT}/org/nodes", 403, "组织架构跨租户写入被拒"),
    ("管理员模块", "GET", "/platform/capabilities", 403, "AI 能力注册表需管理员"),
    ("管理员模块", "GET", "/platform/overview", 403, "跨企业总览需管理员"),
    ("管理员模块", "GET", "/platform/ai-usage", 403, "AI 调用统计需管理员"),
    ("管理员模块", "GET", "/ingest/sources", 403, "数据接入需管理员"),
]

ANON_CASES = [
    ("匿名", "GET", f"/enterprises/{OTHER_ENT}/org/nodes", 401, "匿名读组织架构"),
    ("匿名", "GET", f"/work-ticket/tickets?enterprise_id={OTHER_ENT}", 401, "匿名读作业票"),
    ("匿名", "GET", "/platform/capabilities", 401, "匿名读 AI 能力注册表"),
]


def main():
    token = login()
    print("login 200")
    results = []
    for group, method, path, expect, note in CASES:
        body = {"nodes": []} if method == "PUT" else None
        status, raw = call(method, path, token=token, body=body)
        ok = status == expect
        results.append(
            {
                "group": group,
                "method": method,
                "path": path,
                "expect": expect,
                "status": status,
                "pass": ok,
                "note": note,
                "body_head": raw[:160].decode("utf-8", "replace"),
            }
        )
    for group, method, path, expect, note in ANON_CASES:
        status, raw = call(method, path)
        results.append(
            {
                "group": group,
                "method": method,
                "path": path,
                "expect": expect,
                "status": status,
                "pass": status == expect,
                "note": note,
                "body_head": raw[:160].decode("utf-8", "replace"),
            }
        )

    passed = sum(1 for r in results if r["pass"])
    for r in results:
        print(
            "{mark} {group:<10} {method:<4} {path:<62} expect={expect} got={status}".format(
                mark="PASS" if r["pass"] else "FAIL", **r
            )
        )
    print(f"合计 {passed}/{len(results)} PASS")

    with open(
        "backend/exports/e2e-20260918/summary-new-features-authz.json", "w", encoding="utf-8"
    ) as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh, ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
