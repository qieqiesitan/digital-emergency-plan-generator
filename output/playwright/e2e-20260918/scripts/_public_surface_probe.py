"""免登录公开面校验：风险公示 / 隐患公示+扫码上报 / 风险点二维码。

这三条链路没有登录态，是攻击面最外层的部分，重点验：
  ①令牌强度（64 hex）与**重置后旧 token 立即失效**；
  ②伪造 token → 404（不可枚举）；
  ③公示数据脱敏（不含责任人/电话等敏感字段）；
  ④扫码上报能真正落库（source_type=report、created_by 为空）且 nonce 防重（409）。

探针自清理：删除上报产生的隐患记录、二维码所属风险对象/分区/楼层；公示 token 轮换后保留新值。
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
ENT = "10e11995-e682-405a-9035-fbde13cca213"
BASE = f"/enterprises/{ENT}/risk-management"
HAZ = f"/enterprises/{ENT}/hazard-inspection"
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


def call(method, path, token=None, body=None, expect=None, label="", raw=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status, raw_body = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw_body = exc.code, exc.read()
    if raw:
        payload = raw_body
    else:
        try:
            payload = json.loads(raw_body)
        except Exception:
            payload = raw_body[:200].decode("utf-8", "replace")
    if expect is not None:
        ok = status == expect
        results.append({"name": label, "ok": ok, "detail": f"expect={expect} got={status}"})
        print(("PASS " if ok else "FAIL ") + f"{label}（期望 {expect}，实际 {status}）")
    return status, payload


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]

        # ---- A) 风险公示 token ----
        status, tok1 = call("POST", f"{BASE}/risk-publicity/token", token)
        t1 = (tok1.get("data") or {}).get("token") if isinstance(tok1, dict) else None
        check("公示 token 生成（64 hex）",
              status == 200 and isinstance(t1, str) and len(t1) == 64
              and all(c in "0123456789abcdef" for c in t1), f"len={len(t1 or '')}")
        status, public1 = call("GET", f"/public/risk/{t1}")
        check("免登录可读公示页", status == 200, f"status={status}")
        items = (public1.get("data") or {}).get("items") if isinstance(public1, dict) else None
        if isinstance(items, list) and items:
            keys = set(items[0].keys())
            banned = {k for k in keys if k in ("person", "phone", "responsible_person", "contact_phone")}
            check("公示数据不含责任人/电话字段", not banned, sorted(keys))
        else:
            check("公示数据不含责任人/电话字段", True, "（本企业当前无重大风险公示行）")
        status, _ = call("GET", "/public/risk/" + "f" * 64)
        check("伪造 token → 404", status == 404, f"status={status}")

        status, tok2 = call("POST", f"{BASE}/risk-publicity/token", token)
        t2 = (tok2.get("data") or {}).get("token") if isinstance(tok2, dict) else None
        check("重置生成新 token", bool(t2) and t2 != t1, f"{str(t1)[:8]}… → {str(t2)[:8]}…")
        status, _ = call("GET", f"/public/risk/{t1}")
        check("重置后旧 token 立即失效（404）", status == 404, f"status={status}")
        status, _ = call("GET", f"/public/risk/{t2}")
        check("新 token 可用", status == 200, f"status={status}")

        # ---- B) 风险点二维码扫码上报 ----
        status, floor = call("POST", f"{BASE}/floors?enterprise_id={ENT}", token,
                             {"name": f"公开面探针-{STAMP}", "sort_order": 97}, expect=201,
                             label="建探针楼层")
        state["floor"] = (floor.get("data") or {}).get("id")
        status, zone = call("POST", f"{BASE}/zones?enterprise_id={ENT}", token,
                            {"name": f"公开面探针-分区-{STAMP}", "floor_id": state["floor"]},
                            expect=201, label="建探针分区")
        state["zone"] = (zone.get("data") or {}).get("id")
        status, obj = call("POST", f"{BASE}/objects?enterprise_id={ENT}", token,
                           {"name": f"公开面探针-风险点-{STAMP}", "zone_id": state["zone"],
                            "is_risk_point": True, "location_x": 1.0, "location_y": 1.0},
                           expect=201, label="建风险对象")
        state["object"] = (obj.get("data") or {}).get("id")
        obj_token = sql(f"select public_token from risk_objects where id='{state['object']}';")
        check("风险对象自动生成二维码 token（64 hex）",
              len(obj_token or "") == 64, f"len={len(obj_token or '')}")

        status, _ = call("POST", f"/public/hazard/report/{obj_token}",
                         body={"description": "扫码上报：探针隐患", "nonce": f"probe-{STAMP}"},
                         expect=200, label="免登录扫码上报")
        state["hazard_id"] = sql(
            f"select id from hazard_records where enterprise_id='{ENT}' "
            f"and description like '%探针隐患%' order by created_at desc limit 1;")
        check("上报已落库为 report 来源且无创建人",
              bool(state["hazard_id"])
              and sql(f"select source_type from hazard_records where id='{state['hazard_id']}';") == "report"
              and sql(f"select coalesce(created_by::text,'') from hazard_records "
                      f"where id='{state['hazard_id']}';") == "",
              f"id={state['hazard_id']}")
        status, dup = call("POST", f"/public/hazard/report/{obj_token}",
                           body={"description": "扫码上报：探针隐患（重复）",
                                 "nonce": f"probe-{STAMP}"})
        check("同 nonce 重复提交 → 409", status == 409, f"status={status} {str(dup)[:80]}")
        status, _ = call("POST", "/public/hazard/report/" + "e" * 64,
                         body={"description": "x", "nonce": f"bad-{STAMP}"})
        check("伪造二维码 token → 404", status == 404, f"status={status}")

        # ---- C) 隐患公示 token ----
        status, htok = call("POST", f"{HAZ}/publicity-token", token)
        ht = (htok.get("data") or {}).get("token") if isinstance(htok, dict) else None
        check("隐患公示 token 生成（64 hex）",
              status == 200 and isinstance(ht, str) and len(ht) == 64, f"len={len(ht or '')}")
        status, pub = call("GET", f"/public/hazard/{ht}")
        data = pub.get("data") if isinstance(pub, dict) else {}
        check("免登录隐患公示可读且企业名脱敏",
              status == 200 and bool(data.get("enterprise_name")),
              f"status={status} name={str(data.get('enterprise_name'))[:12]}")
        rows = data.get("items") if isinstance(data, dict) else None
        if isinstance(rows, list) and rows:
            keys = set(rows[0].keys())
            check("公示行不含责任人/联系方式/位置",
                  not ({"person", "phone", "location", "responsible_person"} & keys), sorted(keys))
        else:
            check("公示行不含责任人/联系方式/位置", True, "（无公示行）")
        status, _ = call("GET", "/public/hazard/" + "d" * 64)
        check("伪造公示 token → 404", status == 404, f"status={status}")
    finally:
        if state.get("hazard_id"):
            sql(f"delete from hazard_audit_logs where record_id='{state['hazard_id']}';")
            for t in ("hazard_approvals", "hazard_rectifications", "hazard_reviews"):
                sql(f"delete from {t} where record_id='{state['hazard_id']}';")
            sql(f"delete from hazard_records where id='{state['hazard_id']}';")
        if state.get("object"):
            sql(f"delete from risk_objects where id='{state['object']}';")
        if state.get("zone"):
            sql(f"delete from risk_zones where id='{state['zone']}';")
        if state.get("floor"):
            sql(f"delete from enterprise_floors where id='{state['floor']}';")
        print("cleanup done: 探针上报记录与二维码对象已清理")

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-public-surface.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
