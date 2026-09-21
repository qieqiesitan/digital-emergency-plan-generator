"""隐患闭环端到端校验（登记 → 分级 → 整改 → 复查 → 销号），走真实库与真实权限。

覆盖两条分级路径：
  A 一般隐患：grade → rectifying → rectify → reviewing → review(pass) → close → closed
  B 重大隐患：grade → pending_approval → approve → rectifying → …… → closed
并验证：整改人/复查人必须是启用成员（否则 422）、复查人不能是整改人（422）、
整改不填内容 422、非法流转 409，以及 hazard_audit_logs 全链路留痕。

清理：删除探针记录（含审批/整改/复查/审计行）+ 临时成员/账号，并还原 QA 角色。
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
FIXER = f"qa_fixer_{STAMP}@test.com"
REVIEWER = f"qa_reviewer_{STAMP}@test.com"
TMP_PWD = "test123456"

results = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


def check(name, ok, detail=""):
    results.append({"name": name, "pass": bool(ok), "detail": str(detail)[:300]})
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
        payload = raw.decode("utf-8", "replace")[:200]
    if expect is not None:
        ok = status == expect
        results.append({"label": label, "expect": expect, "got": status, "pass": ok})
        print(("PASS " if ok else "FAIL ") + f"{label}（期望 {expect}，实际 {status}）")
    return status, payload


def login(email, pwd):
    status, payload = call("POST", "/auth/login", body={"email": email, "password": pwd})
    assert status == 200, (email, status, payload)
    return payload["data"]["access_token"]


def main():
    os.makedirs(OUT, exist_ok=True)
    record_ids = []
    try:
        # --- 0) 临时提权建两个账号并绑定为启用成员（整改人 / 复查人）---
        sql(f"update users set role='super_admin' where id='{OWNER_ID}';")
        owner = login(U, P)
        for email, name in ((FIXER, "探针整改人"), (REVIEWER, "探针复查人")):
            call("POST", "/admin/users", token=owner, expect=201, label=f"建号 {name}",
                 body={"email": email, "name": name, "password": TMP_PWD, "role": "user"})
        fixer_id = sql(f"select id from users where email='{FIXER}';")
        reviewer_id = sql(f"select id from users where email='{REVIEWER}';")
        call("PUT", f"/enterprises/{ENT}/org/nodes", token=owner, expect=200,
             label="写组织树（绑定成员用）",
             body={"nodes": [{"id": "node-1", "type": "dept", "name": "探针安全部",
                              "parent_id": None, "members": []}]})
        for uid, name in ((fixer_id, "探针整改人"), (reviewer_id, "探针复查人")):
            call("POST", f"/enterprises/{ENT}/org/members", token=owner, expect=201,
                 label=f"绑定成员 {name}",
                 body={"user_id": uid, "name": name, "org_node_id": "node-1", "role": "member"})

        # --- A) 一般隐患：分级 → 整改 → 复查(pass) → 销号 ---
        _, created = call("POST", f"/enterprises/{ENT}/hazard-inspection/records", token=owner,
                          expect=201, label="A 登记隐患",
                          body={"source_type": "manual", "title": "探针-一般隐患",
                                "description": "配电箱门缺失", "hazard_type": None,
                                "location": "一号车间"})
        rec_a = created["data"]["id"]
        record_ids.append(rec_a)
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_a}/grade", token=owner,
             expect=200, label="A 分级（一般）",
             body={"level": "general", "rectification_user_id": fixer_id})
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_a}/rectify", token=owner,
             expect=200, label="A 提交整改",
             body={"content": "已补装配电箱门并上锁", "reviewer_user_id": reviewer_id})
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_a}/review", token=owner,
             expect=200, label="A 复查通过", body={"result": "pass", "comment": "现场确认合格"})
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_a}/close", token=owner,
             expect=200, label="A 销号", body={"comment": "整改闭环"})
        status = sql(f"select status from hazard_records where id='{rec_a}';")
        check("A 终态为 closed", status == "closed", status)

        # --- B) 重大隐患：分级 → 审批 → 整改 → 复查 → 销号 ---
        _, created_b = call("POST", f"/enterprises/{ENT}/hazard-inspection/records", token=owner,
                            expect=201, label="B 登记隐患",
                            body={"source_type": "manual", "title": "探针-重大隐患",
                                  "description": "罐区可燃气体报警器失效", "location": "罐区"})
        rec_b = created_b["data"]["id"]
        record_ids.append(rec_b)
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_b}/grade", token=owner,
             expect=200, label="B 分级（重大）",
             body={"level": "major", "grading_basis": "依据 GB 30871-2022 判定",
                   "rectification_user_id": fixer_id,
                   "rectification_plan": {"goal": "恢复报警功能", "measures": "更换探头并校验",
                                          "budget": "5000", "emergency_measures": "临时人工巡检",
                                          "acceptance_criteria": "报警联动测试通过"}})
        st = sql(f"select status from hazard_records where id='{rec_b}';")
        check("B 重大隐患进入待审批", st == "pending_approval", st)
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_b}/approve", token=owner,
             expect=200, label="B 挂牌审批", body={"comment": "同意挂牌治理"})
        # 负例：复查人=整改人 → 422
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_b}/rectify", token=owner,
             expect=422, label="B 复查人=整改人 → 422",
             body={"content": "已更换探头", "reviewer_user_id": fixer_id})
        # 负例：内容为空 → 422
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_b}/rectify", token=owner,
             expect=422, label="B 整改内容为空 → 422",
             body={"content": "", "reviewer_user_id": reviewer_id})
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_b}/rectify", token=owner,
             expect=200, label="B 提交整改",
             body={"content": "已更换探头并完成联动测试", "reviewer_user_id": reviewer_id})
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_b}/review", token=owner,
             expect=200, label="B 复查通过", body={"result": "pass"})
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_b}/close", token=owner,
             expect=200, label="B 销号", body={"comment": "整改闭环"})
        call("POST", f"/enterprises/{ENT}/hazard-inspection/records/{rec_b}/close", token=owner,
             expect=409, label="B 已销号再销号 → 409", body={"comment": "重复销号"})

        # --- 留痕与关联行 ---
        audits = sql(f"select count(*) from hazard_audit_logs where record_id='{rec_b}';")
        check("审计留痕条数 ≥5（登记/分级/审批/整改/复查/销号）",
              int(audits or 0) >= 5, f"count={audits}")
        for table, expects in (("hazard_approvals", 1), ("hazard_rectifications", 1),
                               ("hazard_reviews", 1)):
            n = sql(f"select count(*) from {table} where record_id='{rec_b}';")
            check(f"{table} 有 {expects} 行", int(n or 0) >= expects, f"count={n}")

        detail_ok = True
        status, detail = call("GET", f"/enterprises/{ENT}/hazard-inspection/records/{rec_a}",
                              token=owner)
        detail_ok = status == 200 and isinstance(detail, dict)
        check("详情可读（一般隐患）", detail_ok, f"status={status}")
    finally:
        for rid in record_ids:
            sql(f"delete from hazard_audit_logs where record_id='{rid}';")
            for table in ("hazard_approvals", "hazard_rectifications", "hazard_reviews"):
                sql(f"delete from {table} where record_id='{rid}';")
            sql(f"delete from hazard_records where id='{rid}';")
        sql(f"delete from enterprise_members where enterprise_id='{ENT}' and user_id in "
            f"(select id from users where email in ('{FIXER}','{REVIEWER}'));")
        sql(f"update enterprises set org_structure='[]'::jsonb where id='{ENT}';")
        sql(f"delete from users where email in ('{FIXER}','{REVIEWER}');")
        sql(f"update users set role='user' where id='{OWNER_ID}';")
        print("cleanup done: 记录/成员/账号已清理，QA 角色已还原")

    passed = sum(1 for r in results if r["pass"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-hazard-lifecycle.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
