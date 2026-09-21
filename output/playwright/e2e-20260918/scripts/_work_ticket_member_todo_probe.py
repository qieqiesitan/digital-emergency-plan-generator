"""作业票「成员审批 + 我的待办」端到端探针。

验证 2026-09-18 补齐的能力（关闭前端审批工作台里记录的遗留项）：
  1. 非企业主的法定审批人（绑定为企业成员的登录用户）能进入作业票审批链路；
  2. `assigned_to_me=true` 只返回"当前节点轮到我签"的票；
  3. 成员即使不传 `assigned_to_me`，也只能看到与自己有关的票（不能越权浏览全企业）；
  4. 非成员 / 匿名仍然是 404 / 401；
  5. 签过之后的票仍可回看（历史签署记录），但不再出现在待办里。

副作用与清理：临时把 QA 账号提权为 super_admin 以调用管理员建号接口，创建两个临时用户
（审批成员 / 非成员），写入 QA 自己企业的组织树与成员绑定，开一张 DHZY 测试票；
finally 里全部回滚：删票、删成员、组织树恢复为 []、删临时用户、QA 角色还原为 user。
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "http://localhost:8000/api/v1"
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan", "-t", "-A", "-c"]
OWNER_EMAIL, OWNER_PWD = "qa_e2e_test@test.com", "test123456"
OWNER_ID = "506a380e-a2fe-4fd8-9430-f7f4c61f3d4b"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
STAMP = str(int(time.time()))[-6:]
APPROVER = f"qa_approver_{STAMP}@test.com"
NONMEMBER = f"qa_nonmember_{STAMP}@test.com"
TMP_PWD = "test123456"
TICKET_CODE = "MEMB"

results = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def call(method, path, token=None, body=None, expect=None, label=""):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except Exception as exc:  # 连接层异常
        status, raw = -1, str(exc).encode()
    if expect is not None:
        ok = status == expect
        results.append({"label": label, "path": path, "expect": expect, "got": status, "pass": ok})
        print(("PASS " if ok else "FAIL ") + f"{label} (expect {expect}, got {status})")
    try:
        return status, json.loads(raw)
    except Exception:
        return status, raw[:200].decode("utf-8", "replace")


def login(email, password):
    status, payload = call("POST", "/auth/login", body={"email": email, "password": password})
    assert status == 200, (email, status, payload)
    return payload["data"]["access_token"]


def main():
    created_ticket = None
    try:
        # --- 0) 临时提权（建号需要管理员），并登录 ---
        sql(f"update users set role='super_admin' where id='{OWNER_ID}';")
        owner = login(OWNER_EMAIL, OWNER_PWD)

        call("POST", "/admin/users", token=owner, expect=201, label="创建审批成员账号",
             body={"email": APPROVER, "name": "探针审批人", "password": TMP_PWD, "role": "user"})
        call("POST", "/admin/users", token=owner, expect=201, label="创建非成员账号",
             body={"email": NONMEMBER, "name": "探针旁观者", "password": TMP_PWD, "role": "user"})
        approver = login(APPROVER, TMP_PWD)
        nonmember = login(NONMEMBER, TMP_PWD)
        approver_id = sql(f"select id from users where email='{APPROVER}';")
        nonmember_id = sql(f"select id from users where email='{NONMEMBER}';")

        # --- 1) 绑定成成员之前：非成员看不到该企业 ---
        call("GET", f"/work-ticket/tickets?enterprise_id={ENT}", token=approver,
             expect=404, label="未绑定成员读票据列表 → 404")

        # --- 2) 组织树（三层同名链，覆盖节点 role_code 的三种命名）+ 绑定成员 ---
        nodes = [
            {"id": "node-1", "type": "dept", "name": "主管领导", "parent_id": None, "members": []},
            {"id": "node-2", "type": "dept", "name": "安全管理部门", "parent_id": "node-1", "members": []},
            {"id": "node-3", "type": "dept", "name": "所在基层单位", "parent_id": "node-2", "members": []},
        ]
        call("PUT", f"/enterprises/{ENT}/org/nodes", token=owner, body={"nodes": nodes},
             expect=200, label="写入探针组织树")
        call("POST", f"/enterprises/{ENT}/org/members", token=owner, expect=201,
             label="绑定审批成员到最深层节点",
             body={"user_id": approver_id, "name": "探针审批人", "org_node_id": "node-3",
                   "role": "member"})

        # --- 3) 企业主开票 → 气体检测 → 提交 ---
        _, tpl_payload = call("GET", "/work-ticket/templates", token=owner)
        tpl = next(t for t in tpl_payload["data"] if t["code"] == "DHZY")
        values = {f["field_key"]: "探针值" for f in tpl["fields"] if f.get("is_required")}
        values["confirmed_measures"] = [m["sort_order"] for m in tpl["measures"]]
        status, opened = call("POST", "/work-ticket/tickets", token=owner, expect=200,
                              label="企业主开票",
                              body={"enterprise_id": ENT, "enterprise_code": TICKET_CODE,
                                    "ticket_type": "DHZY", "template_id": tpl["id"],
                                    "level": None, "values": values})
        created_ticket = opened["data"]["id"]
        call("POST", f"/work-ticket/tickets/{created_ticket}/gas-tests", token=owner,
             expect=200, label="录入气体检测",
             body={"sampled_at": datetime.now(timezone.utc).isoformat(), "conclusion": "合格"})
        call("POST", f"/work-ticket/tickets/{created_ticket}/submit", token=owner,
             expect=200, label="提交进入审批")

        # --- 4) 待办口径 ---
        _, owner_all = call("GET", f"/work-ticket/tickets?enterprise_id={ENT}&status=approving",
                            token=owner)
        results.append({"label": "企业主可见全部审批中票据", "got": len(owner_all["data"]),
                        "expect": ">=1", "pass": len(owner_all["data"]) >= 1})
        print(("PASS " if len(owner_all["data"]) >= 1 else "FAIL ") + "企业主可见全部审批中票据")
        _, owner_mine = call("GET",
                             f"/work-ticket/tickets?enterprise_id={ENT}&status=approving&assigned_to_me=true",
                             token=owner)
        ok = len(owner_mine["data"]) == 0
        results.append({"label": "企业主(非成员)我的待办为空", "got": len(owner_mine["data"]),
                        "expect": 0, "pass": ok})
        print(("PASS " if ok else "FAIL ") + "企业主(非成员)我的待办为空")

        _, approver_all = call("GET", f"/work-ticket/tickets?enterprise_id={ENT}&status=approving",
                               token=approver, expect=200, label="成员读列表（隐式收窄）")
        ok = [t["id"] for t in approver_all["data"]] == [created_ticket]
        results.append({"label": "成员列表只含与自己有关的票", "pass": ok})
        print(("PASS " if ok else "FAIL ") + "成员列表只含与自己有关的票")
        _, approver_mine = call("GET",
                                f"/work-ticket/tickets?enterprise_id={ENT}&status=approving&assigned_to_me=true",
                                token=approver, expect=200, label="成员我的待办")
        ok = [t["id"] for t in approver_mine["data"]] == [created_ticket]
        results.append({"label": "我的待办命中当前节点可签人", "pass": ok})
        print(("PASS " if ok else "FAIL ") + "我的待办命中当前节点可签人")
        call("GET", f"/work-ticket/tickets/{created_ticket}", token=approver,
             expect=200, label="成员可读票据详情")

        # --- 5) 非成员与匿名 ---
        call("GET", f"/work-ticket/tickets?enterprise_id={ENT}", token=nonmember,
             expect=404, label="非成员读列表 → 404")
        call("GET", f"/work-ticket/tickets/{created_ticket}", token=nonmember,
             expect=404, label="非成员读详情 → 404")
        call("GET", f"/work-ticket/tickets/{created_ticket}", expect=401, label="匿名读详情 → 401")

        # --- 6) 成员签字 → 待办清空但历史仍可回看 ---
        call("POST", f"/work-ticket/tickets/{created_ticket}/node-action", token=approver,
             expect=200, label="成员执行审批", body={"action": "approve", "opinion": "探针同意"})
        _, after = call("GET",
                        f"/work-ticket/tickets?enterprise_id={ENT}&assigned_to_me=true",
                        token=approver)
        ok = len(after["data"]) == 0
        results.append({"label": "签完后待办清空", "got": len(after["data"]), "expect": 0, "pass": ok})
        print(("PASS " if ok else "FAIL ") + "签完后待办清空")
        call("GET", f"/work-ticket/tickets/{created_ticket}", token=approver,
             expect=200, label="签过的票仍可回看")

        # --- 7) 生命周期推进（企业主）：开始作业 → 完工 → 归档 ---
        for action, label, expected in (
            ("start", "开始作业", "working"),
            ("finish", "完工", "finished"),
            ("close", "归档", "closed"),
        ):
            status, body = call("POST", f"/work-ticket/tickets/{created_ticket}/transition",
                                token=owner, body={"action": action}, expect=200, label=label)
            got = (body or {}).get("data", {}).get("status") if isinstance(body, dict) else None
            ok = got == expected
            results.append({"label": f"{label}后状态={expected}", "got": got, "pass": ok})
            print(("PASS " if ok else "FAIL ") + f"{label}后状态={expected}（实际 {got}）")

        # 终态不可再作废（状态机守护）
        call("POST", f"/work-ticket/tickets/{created_ticket}/transition", token=owner,
             body={"action": "cancel"}, expect=409, label="已归档票再作废 → 409")
        # 全量流转留痕应包含开票/提交/审批/开始作业/完工/归档
        _, detail = call("GET", f"/work-ticket/tickets/{created_ticket}", token=owner)
        actions = [a.get("action") for a in (detail.get("data", {}).get("audit_logs") or [])]
        print("audit actions:", actions)
        need = {"open", "submit", "approve", "start", "finish", "close"}
        ok = need.issubset(set(actions))
        results.append({"label": "流转留痕覆盖全链路", "got": actions, "pass": ok})
        print(("PASS " if ok else "FAIL ") + f"流转留痕覆盖全链路：{sorted(set(actions))}")
    finally:
        try:
            sql(f"delete from work_ticket_instances where enterprise_id='{ENT}' and code like 'DHZY-{TICKET_CODE}-%';")
            sql(f"delete from enterprise_members where enterprise_id='{ENT}' and user_id in "
                f"(select id from users where email in ('{APPROVER}','{NONMEMBER}'));")
            sql(f"update enterprises set org_structure='[]'::jsonb where id='{ENT}';")
            sql(f"delete from users where email in ('{APPROVER}','{NONMEMBER}');")
            sql(f"update users set role='user' where id='{OWNER_ID}';")
            print("cleanup done: ticket/member/org/user 已清理，QA 角色已还原")
        except Exception as exc:  # 清理失败必须显式暴露
            print("CLEANUP FAILED:", exc)

    passed = sum(1 for r in results if r["pass"])
    print(f"合计 {passed}/{len(results)} PASS")
    out = {"passed": passed, "total": len(results), "results": results, "ticket_id": created_ticket}
    with open("backend/exports/e2e-20260918/summary-work-ticket-member-todo.json", "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
