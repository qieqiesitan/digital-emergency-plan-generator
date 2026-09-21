"""周期扫描接线校验：运维端点 + 作业票过期自动扫描。
修复前：`expire_overdue_tickets` 没有任何调用方，批准后超期的票永远停在「已批准」。
本探针造一张"已批准但有效期已过"的票，调用 POST /api/v1/admin/maintenance/run-scans，
断言它被自动置为 expired、留下审计记录，且**重复调用不会重复处理**；
同时校验该端点仅管理员可用。跑完删除探针票据并还原 QA 角色。
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
TPL = "99f530de-2586-5f03-9751-b9db1bbb3777"  # DHZY 动火
STAMP = str(int(time.time()))[-6:]

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
        with urllib.request.urlopen(req, timeout=180) as resp:
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


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        sql(f"update users set role='super_admin' where id='{OWNER_ID}';")
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]
        _, tpl_payload = call("GET", "/work-ticket/templates", token)
        tpl = next(t for t in tpl_payload["data"] if t["id"] == TPL)
        values = {f["field_key"]: "扫描探针值" for f in tpl["fields"] if f.get("is_required")}
        values["confirmed_measures"] = [m["sort_order"] for m in tpl["measures"]]
        status, opened = call("POST", "/work-ticket/tickets", token,
                              {"enterprise_id": ENT, "enterprise_code": f"SCN{STAMP[:3]}",
                               "ticket_type": "DHZY", "template_id": TPL, "level": None,
                               "values": values}, expect=200, label="开探针票")
        state["ticket"] = (opened.get("data") or {}).get("id")
        sql(f"update work_ticket_instances set status='approved', "
            f"valid_to = now() - interval '2 hours' where id='{state['ticket']}';")
        check("构造超期已批准票", sql(
            f"select status from work_ticket_instances where id='{state['ticket']}';") == "approved")
        status, scans = call("POST", "/admin/maintenance/run-scans", token, expect=200,
                             label="手动触发周期扫描")
        data = scans.get("data") if isinstance(scans, dict) else {}
        check("返回本轮计数（隐患 + 作业票）",
              isinstance(data.get("hazard_scans"), (dict, type(None)))
              and isinstance(data.get("expired_tickets"), int), data)
        check("本轮至少过期 1 张票", (data.get("expired_tickets") or 0) >= 1,
              data.get("expired_tickets"))
        check("超期票被自动置为 expired", sql(
            f"select status from work_ticket_instances where id='{state['ticket']}';") == "expired")
        check("过期动作留下审计记录", sql(
            f"select count(*) from work_ticket_audit_logs where instance_id='{state['ticket']}' "
            f"and action='expire';") == "1")
        status, scans2 = call("POST", "/admin/maintenance/run-scans", token, expect=200,
                             label="重复触发（幂等）")
        check("第二次不再重复处理该票", (scans2.get("data") or {}).get("expired_tickets") == 0,
              (scans2.get("data") or {}).get("expired_tickets"))
        check("审计记录未重复", sql(
            f"select count(*) from work_ticket_audit_logs where instance_id='{state['ticket']}' "
            f"and action='expire';") == "1")
        sql(f"update users set role='user' where id='{OWNER_ID}';")
        _, pr2 = call("POST", "/auth/login", body={"email": U, "password": P})
        token_user = pr2["data"]["access_token"]
        call("POST", "/admin/maintenance/run-scans", token_user, expect=403,
             label="普通用户触发 → 403")
    finally:
        if state.get("ticket"):
            sql(f"delete from work_ticket_audit_logs where instance_id='{state['ticket']}';")
            sql(f"delete from work_ticket_node_records where instance_id='{state['ticket']}';")
            sql(f"delete from work_ticket_gas_tests where instance_id='{state['ticket']}';")
            sql(f"delete from work_ticket_instances where id='{state['ticket']}';")
        sql(f"update users set role='user' where id='{OWNER_ID}';")
        print("cleanup done: 探针票据已清理，QA 角色已还原")
    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-maintenance-scan.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
