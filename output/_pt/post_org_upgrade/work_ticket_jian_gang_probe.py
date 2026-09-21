"""定向回归 ②b：作业票会签的**兼岗**分支——只有兼岗命中时才能收到待办。

构造：公司树分两支「生产部」「安全管理」（互不为祖先）；成员主岗挂生产部，兼岗挂安全管理；
动土票（PTZY）第 1 个节点是「涉及单位会签」，countersign_units 含「安全管理」。
预期：① 有兼岗 → 我的待办包含该票；② 去掉兼岗 → 不包含（证明命中来自兼岗）；
     ③ 恢复兼岗 → 再次包含（证明增删即时生效）。
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
APPROVER = f"qa_jg_{STAMP}@test.com"
TMP_PWD = "test123456"

results: list[dict] = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def call(method: str, path: str, token: str | None = None, body=None, expect=None, label=""):
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
    except Exception as exc:  # noqa: BLE001
        status, raw = -1, str(exc).encode()
    if expect is not None:
        ok = status == expect
        results.append({"label": label, "expect": expect, "got": status, "pass": ok})
        print(("PASS " if ok else "FAIL ") + f"{label} (expect {expect}, got {status})", flush=True)
    try:
        return status, json.loads(raw)
    except Exception:  # noqa: BLE001
        return status, raw[:200].decode("utf-8", "replace")


def login(email, password):
    _, payload = call("POST", "/auth/login", body={"email": email, "password": password})
    return payload["data"]["access_token"]


def mine(token, ticket_id: str) -> bool:
    _, payload = call("GET", f"/work-ticket/tickets?enterprise_id={ENT}&status=approving&assigned_to_me=true",
                      token=token)
    return ticket_id in [t["id"] for t in (payload.get("data") or [])]


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append({"label": label, "pass": ok, "detail": detail})
    print(("PASS " if ok else "FAIL ") + label + (f" —— {detail}" if detail else ""), flush=True)


def main() -> int:
    ticket = None
    member_id = None
    try:
        sql(f"update users set role='super_admin' where id='{OWNER_ID}';")
        owner = login(OWNER_EMAIL, OWNER_PWD)
        call("POST", "/admin/users", token=owner, expect=201, label="建兼岗测试账号",
             body={"email": APPROVER, "name": "兼岗测试审批人", "password": TMP_PWD, "role": "user"})
        approver = login(APPROVER, TMP_PWD)
        approver_id = sql(f"select id from users where email='{APPROVER}';")

        # 公司树两支：生产部 / 安全管理（互不为祖先）
        nodes = [
            {"id": "node-prod", "type": "dept", "name": "生产部", "parent_id": None, "members": []},
            {"id": "node-safe", "type": "dept", "name": "安全管理", "parent_id": None, "members": []},
        ]
        call("PUT", f"/enterprises/{ENT}/org/nodes", token=owner, body={"nodes": nodes},
             expect=200, label="写两支组织树")
        status, created = call("POST", f"/enterprises/{ENT}/org/members", token=owner, expect=201,
                               label="建成员（主岗生产部 + 兼岗安全管理）",
                               body={"user_id": approver_id, "name": "兼岗测试审批人",
                                     "org_node_id": "node-prod", "extra_node_ids": ["node-safe"],
                                     "role": "member"})
        member_id = created["data"]["id"]
        positions = created["data"].get("positions") or []
        check("成员任职=主岗+兼岗", len(positions) == 2, f"positions={positions}")

        # 开动土票（PTZY）→ 提交 → 当前节点 = 涉及单位会签
        _, tpl_payload = call("GET", "/work-ticket/templates", token=owner)
        tpl = next(t for t in tpl_payload["data"] if t["code"] == "PTZY")
        values = {f["field_key"]: "兼岗探针值" for f in tpl["fields"] if f.get("is_required")}
        measures = tpl.get("measures") or []
        if measures:
            values["confirmed_measures"] = [m["sort_order"] for m in measures]
        status, opened = call("POST", "/work-ticket/tickets", token=owner, expect=200,
                              label="开动土票", body={"enterprise_id": ENT, "enterprise_code": "JGCS",
                                                    "ticket_type": "PTZY", "template_id": tpl["id"],
                                                    "level": None, "values": values})
        ticket = opened["data"]["id"]
        call("POST", f"/work-ticket/tickets/{ticket}/gas-tests", token=owner,
             body={"sampled_at": datetime.now(timezone.utc).isoformat(), "conclusion": "合格"},
             label="录气体检测（动土票可选）")
        call("POST", f"/work-ticket/tickets/{ticket}/submit", token=owner, expect=200, label="提交进入会签")

        # ① 兼岗命中
        check("① 有兼岗 → 收到会签待办", mine(approver, ticket))

        # ② 去掉兼岗 → 不再命中（证明是兼岗带来的）
        call("PUT", f"/enterprises/{ENT}/org/members/{member_id}", token=owner, expect=200,
             label="移除兼岗（保留主岗）", body={"extra_node_ids": []})
        check("② 无兼岗 → 不再收到", not mine(approver, ticket))

        # ③ 恢复兼岗 → 再次命中
        call("PUT", f"/enterprises/{ENT}/org/members/{member_id}", token=owner, expect=200,
             label="恢复兼岗", body={"extra_node_ids": ["node-safe"]})
        check("③ 恢复兼岗 → 再次收到", mine(approver, ticket))
    finally:
        try:
            if ticket:
                sql(f"delete from work_ticket_instances where id='{ticket}';")
            if member_id:
                sql(f"delete from member_positions where member_id='{member_id}';")
            sql(f"delete from enterprise_members where enterprise_id='{ENT}' and name='兼岗测试审批人';")
            sql(f"update enterprises set org_structure='[]'::jsonb where id='{ENT}';")
            sql(f"delete from users where email='{APPROVER}';")
            sql(f"update users set role='user' where id='{OWNER_ID}';")
            print("清理：票/成员/任职/组织树/临时账号/角色 已还原", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"清理失败：{exc}", flush=True)

    bad = [r for r in results if not r["pass"]]
    print(f"\n==== ②b 兼岗会签：{len(results)} 项，失败 {len(bad)}")
    for r in bad:
        print(f"   FAIL {r['label']} {r.get('detail', '')}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
