"""数据中台「确认入库」链路校验（零 AI）：writer 注册 → 写正式表 → 幂等拒绝重复确认 → 失败留痕。

为什么值得单独验：`main.py` 启动代码里明确写着"不注册 writer 则 confirm_items 会报
「目标实体尚未注册写入器」，确认链路整体不可用"——即这是一条**靠启动期注册才成立**的接线。
解析（scan/parse）依赖真实 AI，这里跳过解析，直接造 pending 条目走确认环节。
探针自清理：删除写入的正式实体与 source/job/item 行，并还原 QA 角色。
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
UNIT_OK = f"数据中台探针单元-{STAMP}"
UNIT_BAD = f"数据中台坏行单元-{STAMP}"

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
        check("管理员可读数据源列表", call("GET", "/ingest/sources", token)[0] == 200)

        state["source"] = sql(
            "insert into ingest_sources (id, source_type, name, config) values "
            f"(gen_random_uuid(),'manual','探针数据源-{STAMP}','{{}}'::jsonb) returning id;")
        state["job"] = sql(
            "insert into ingest_jobs (id, source_id, trigger, status) values "
            f"(gen_random_uuid(),'{state['source']}','manual','running') returning id;")
        good_payload = json.dumps({"enterprise_id": ENT, "name": UNIT_OK, "unit_type": "storage"},
                                  ensure_ascii=False)
        bad_payload = json.dumps({"enterprise_id": ENT, "name": UNIT_BAD, "unit_type": "非法类型"},
                                 ensure_ascii=False)
        state["item_ok"] = sql(
            "insert into ingest_items (id, job_id, idempotency_key, raw_payload, target_entity) "
            f"values (gen_random_uuid(),'{state['job']}','probe-ok-{STAMP}',"
            f" $json${good_payload}$json$, 'major_hazard_unit') returning id;")
        state["item_bad"] = sql(
            "insert into ingest_items (id, job_id, idempotency_key, raw_payload, target_entity) "
            f"values (gen_random_uuid(),'{state['job']}','probe-bad-{STAMP}',"
            f" $json${bad_payload}$json$, 'major_hazard_unit') returning id;")
        check("造 2 条待审条目（1 正常 + 1 坏载荷）",
              bool(state["item_ok"]) and bool(state["item_bad"]))

        status, res = call("POST", "/ingest/items/confirm", token,
                           {"item_ids": [state["item_ok"]]}, expect=200, label="确认正常条目")
        data = res.get("data") or {}
        check("确认计数为 1", data.get("confirmed") == 1, data)
        check("**正式表已写入**（writer 注册生效）", sql(
            f"select count(*) from major_hazard_units where name='{UNIT_OK}' and "
            f"enterprise_id='{ENT}';") == "1")
        check("条目状态置为 imported 且回填 target_id", sql(
            f"select status||'|'||coalesce(target_id::text,'') from ingest_items "
            f"where id='{state['item_ok']}';").startswith("imported|"))

        status, again = call("POST", "/ingest/items/confirm", token,
                             {"item_ids": [state["item_ok"]]})
        check("重复确认被拒（防重复入库/重复计量）", status == 422, f"status={status} {again}")
        check("重复确认未产生第二行", sql(
            f"select count(*) from major_hazard_units where name='{UNIT_OK}';") == "1")

        status, bad = call("POST", "/ingest/items/confirm", token,
                           {"item_ids": [state["item_bad"]]})
        bdata = bad.get("data") or {}
        check("坏载荷被显式拒绝（不静默跳过）",
              status == 200 and bdata.get("confirmed") == 0 and len(bdata.get("failed") or []) == 1,
              bdata)
        check("坏条目落 failed 并写 error 原因", sql(
            f"select status||'|'||coalesce(left(error,40),'') from ingest_items "
            f"where id='{state['item_bad']}';").startswith("failed|"))
        check("坏载荷未写入正式表", sql(
            f"select count(*) from major_hazard_units where name='{UNIT_BAD}';") == "0")
    finally:
        for key, table in (("item_ok", "ingest_items"), ("item_bad", "ingest_items")):
            if state.get(key):
                sql(f"delete from {table} where id='{state[key]}';")
        if state.get("job"):
            sql(f"delete from ingest_jobs where id='{state['job']}';")
        if state.get("source"):
            sql(f"delete from ingest_sources where id='{state['source']}';")
        sql(f"delete from major_hazard_units where name in ('{UNIT_OK}','{UNIT_BAD}');")
        sql(f"update users set role='user' where id='{OWNER_ID}';")
        print("cleanup done: 探针数据源/任务/条目/正式单元已清理，QA 角色已还原")
    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-ingest-confirm.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
