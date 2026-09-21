"""账号/角色权限 + 数据字典闭环校验。

覆盖：
- 管理员用户 CRUD + **改密后能用新密码登录**（重置闭环真的生效）；
- 角色 CRUD（权限子集绑定）+ 非管理员访问 /admin/users → 403；
- 数据字典：设置级/企业级 CRUD，并验证**写入与更新后立即读到新值**（缓存失效是否生效）；
- 重复 code → 409。

探针自清理：临时用户/角色走 API 删除，设置级字典无删除端点故用 SQL 兜底。
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "http://localhost:8000/api/v1"
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
U, P = "qa_e2e_test@test.com", "test123456"
OWNER_ID = "506a380e-a2fe-4fd8-9430-f7f4c61f3d4b"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
STAMP = str(int(time.time()))[-6:]
TMP_EMAIL = f"qa_adminprobe_{STAMP}@test.com"
TMP_PWD = "probe123456"
NEW_PWD = "probe654321"
# 角色 code 只允许小写字母与下划线（RoleCreate 的 pattern），数字会被 422 —— 探针第一版踩过
ROLE_CODE = "probe_role_" + "".join(chr(ord("a") + int(d)) for d in STAMP)
DICT_TYPE = "probe_dict"

results = []
state: dict = {}


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""), flush=True)


def call(method, path, token=None, body=None, expect=None, label=""):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    try:
        payload = json.loads(raw)
    except Exception:
        payload = raw[:200].decode("utf-8", "replace")
    if expect is not None:
        ok = status == expect
        results.append({"name": label, "ok": ok, "detail": f"expect={expect} got={status}"})
        print(("PASS " if ok else "FAIL ") + f"{label}（期望 {expect}，实际 {status}）")
    return status, payload


def login(email, pwd):
    status, payload = call("POST", "/auth/login", body={"email": email, "password": pwd})
    return status, (payload.get("data", {}).get("access_token") if isinstance(payload, dict) else None)


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        sql(f"update users set role='super_admin' where id='{OWNER_ID}';")
        status, token = login(U, P)
        assert status == 200, status

        # ---- A) 管理员账号闭环 ----
        status, users = call("GET", "/admin/users", token)
        # 分页结构：data={"items": [...], "total": N, "page": p, "page_size": s}
        page_data = users.get("data") if isinstance(users, dict) else None
        items = (page_data or {}).get("items") if isinstance(page_data, dict) else None
        check("管理员可列出用户（分页结构）",
              status == 200 and isinstance(items, list) and (page_data or {}).get("total", 0) >= 1,
              f"status={status} total={(page_data or {}).get('total')} items={len(items or [])}")
        check("列表带搜索参数（search=qa）可用",
              call("GET", "/admin/users?search=qa", token)[0] == 200)

        status, created = call("POST", "/admin/users", token,
                               {"email": TMP_EMAIL, "name": "巡检用户", "password": TMP_PWD,
                                "role": "user"}, expect=201, label="建临时用户")
        state["user"] = (created.get("data") or {}).get("id") if isinstance(created, dict) else None

        status, detail = call("GET", f"/admin/users/{state['user']}", token)
        check("用户详情可读", status == 200, f"status={status}")

        status, _ = call("PUT", f"/admin/users/{state['user']}", token,
                         {"name": "巡检用户-改", "role": "user"}, expect=200, label="改用户资料")
        n = sql(f"select name from users where id='{state['user']}';")
        check("改名已落库", n == "巡检用户-改", n)

        status, _ = call("POST", f"/admin/users/{state['user']}/reset-password", token,
                         {"new_password": NEW_PWD}, expect=200, label="管理员重置密码")
        status_new, tok_new = login(TMP_EMAIL, NEW_PWD)
        check("重置后用新密码可登录", status_new == 200 and bool(tok_new), f"status={status_new}")
        status_old, _ = login(TMP_EMAIL, TMP_PWD)
        check("旧密码已失效", status_old != 200, f"status={status_old}")

        # 非管理员越权访问
        status, _ = call("GET", "/admin/users", tok_new)
        check("普通用户访问 /admin/users → 403", status == 403, f"status={status}")
        status, menus = call("GET", "/roles/my-menus", tok_new)
        check("普通用户可取自己的菜单", status == 200, f"status={status}")

        # ---- B) 角色闭环 ----
        status, perms = call("GET", "/roles/permissions/list", token)
        perm_ids = [p.get("id") for p in (perms.get("data") or [])][:2]
        check("权限清单可读", status == 200 and len(perm_ids) >= 1, f"count={len(perm_ids)}")
        status, roles = call("GET", "/roles", token)
        check("角色列表可读", status == 200 and isinstance(roles.get("data"), list),
              f"status={status}")

        status, role = call("POST", "/roles", token,
                            {"name": "巡检角色", "code": ROLE_CODE, "description": "巡检用",
                             "permission_ids": perm_ids}, expect=201, label="建临时角色")
        state["role"] = (role.get("data") or {}).get("id") if isinstance(role, dict) else None
        status, rd = call("GET", f"/roles/{state['role']}", token)
        check("角色详情可读", status == 200, f"status={status}")
        status, _ = call("PUT", f"/roles/{state['role']}", token,
                         {"description": "巡检用-改"}, expect=200, label="改角色描述")
        status, role_del = call("DELETE", f"/roles/{state['role']}", token, expect=200,
                                label="删临时角色")
        state["role"] = None

        # ---- C) 数据字典（含缓存失效验证）----
        call("POST", "/settings/data-dicts", token,
             {"dict_type": DICT_TYPE, "code": "settings_a", "label": "甲"}, expect=201,
             label="建设置级字典")
        status, listed = call("GET", f"/settings/data-dicts?dict_type={DICT_TYPE}", token)
        labels = [d.get("label") for d in (listed.get("data") or [])]
        check("设置级字典写入后立即可读（缓存未挡住）", "甲" in labels, labels)
        dict_id = next((d.get("id") for d in (listed.get("data") or [])
                        if d.get("code") == "settings_a"), None)
        status, _ = call("PUT", f"/settings/data-dicts/{dict_id}", token, {"label": "乙"},
                         expect=200, label="改设置级字典")
        status, listed2 = call("GET", f"/settings/data-dicts?dict_type={DICT_TYPE}", token)
        labels2 = [d.get("label") for d in (listed2.get("data") or [])]
        check("更新后立刻读到新值（缓存失效生效）", "乙" in labels2 and "甲" not in labels2, labels2)

        status, _ = call("POST", f"/enterprises/{ENT}/data-dicts", token,
                         {"dict_type": DICT_TYPE, "code": "ent_a", "label": "企业甲"}, expect=201,
                         label="建企业级字典")
        status, _ = call("POST", f"/enterprises/{ENT}/data-dicts", token,
                         {"dict_type": DICT_TYPE, "code": "ent_a", "label": "重复"}, expect=409,
                         label="重复 code → 409")
        status, elist = call("GET", f"/enterprises/{ENT}/data-dicts?dict_type={DICT_TYPE}", token)
        ent_item = next((d for d in (elist.get("data") or []) if d.get("code") == "ent_a"), None)
        check("企业级字典可读", bool(ent_item), f"status={status}")
        if ent_item:
            status, _ = call("PUT", f"/enterprises/{ENT}/data-dicts/{ent_item['id']}", token,
                             {"label": "企业丙"}, expect=200, label="改企业级字典")
            status, elist2 = call("GET", f"/enterprises/{ENT}/data-dicts?dict_type={DICT_TYPE}",
                                  token)
            labels3 = [d.get("label") for d in (elist2.get("data") or [])
                       if d.get("code") == "ent_a"]
            check("企业级更新后立刻读到新值", labels3 == ["企业丙"], labels3)
            status, _ = call("DELETE", f"/enterprises/{ENT}/data-dicts/{ent_item['id']}", token,
                             expect=200, label="删企业级字典")
            status, elist3 = call("GET", f"/enterprises/{ENT}/data-dicts?dict_type={DICT_TYPE}",
                                  token)
            check("删除后清单不再包含", all(d.get("code") != "ent_a"
                                        for d in (elist3.get("data") or [])), "ok")

        # ---- 收尾：删临时用户 ----
        call("DELETE", f"/admin/users/{state.get('user')}", token, expect=200, label="删临时用户")
        status, _ = call("GET", f"/admin/users/{state.get('user')}", token)
        check("删除后详情 404", status == 404, f"status={status}")
        state["user"] = None
    finally:
        sql(f"delete from data_dicts where dict_type='{DICT_TYPE}' and enterprise_id is null;")
        if state.get("role"):
            call("DELETE", f"/roles/{state['role']}", token if 'token' in dir() else None)
        sql(f"delete from users where email='{TMP_EMAIL}';")
        sql(f"update users set role='user' where id='{OWNER_ID}';")
        print("cleanup done: 临时用户/角色/字典已清理，QA 角色已还原")

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-admin-dict.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
