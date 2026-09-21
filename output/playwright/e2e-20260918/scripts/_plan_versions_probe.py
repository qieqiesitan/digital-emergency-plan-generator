"""预案版本快照 / 对比 / 回滚闭环（零 AI：手写章节内容即可）。

步骤：建预案 → 写 V1 → 存版本 → 写 V2 → 存版本 → 列表/对比 → 回滚到 V1 → 断言章节内容真的回到 V1。
探针跑完删除预案（级联清掉章节与版本记录）。
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API = "http://localhost:8000/api/v1"
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
V1 = "<p>版本探针-V1 内容</p>"
V2 = "<p>版本探针-V2 内容</p>"

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


def main():
    plan_id = None
    try:
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]
        status, created = call("POST", "/plans", token,
                               {"enterprise_id": ENT, "plan_type": "comprehensive",
                                "title": "版本探针-预案"}, expect=201, label="建探针预案")
        plan_id = (created.get("data") or {}).get("id")

        call("PUT", f"/plans/{plan_id}/sections/sec_1", token, {"content": V1}, expect=200,
             label="写入 V1")
        status, ver1 = call("POST", f"/plans/{plan_id}/versions", token,
                            {"description": "V1 快照"}, expect=200, label="存 V1 版本")
        v1 = ver1.get("data") or {}

        call("PUT", f"/plans/{plan_id}/sections/sec_1", token, {"content": V2}, expect=200,
             label="写入 V2")
        status, ver2 = call("POST", f"/plans/{plan_id}/versions", token,
                            {"description": "V2 快照"}, expect=200, label="存 V2 版本")
        v2 = ver2.get("data") or {}

        status, versions = call("GET", f"/plans/{plan_id}/versions", token)
        nums = [v.get("version_number") for v in (versions.get("data") or [])]
        check("版本列表含两个快照且倒序", status == 200 and len(nums) >= 2 and nums == sorted(nums, reverse=True),
              nums)

        status, diff = call("GET",
                            f"/plans/{plan_id}/versions/compare?a={v1.get('version_number')}"
                            f"&b={v2.get('version_number')}", token)
        diffs = (diff.get("data") or {}).get("diffs") if isinstance(diff, dict) else None
        changed = next((d for d in (diffs or []) if d.get("section_key") == "sec_1"), None)
        check("版本对比识别出 sec_1 变化",
              status == 200 and bool(changed), f"status={status} diffs={diffs}")

        status, _ = call("POST", f"/plans/{plan_id}/versions/{v1.get('id')}/rollback", token,
                         expect=200, label="回滚到 V1")
        status, sec = call("GET", f"/plans/{plan_id}/sections/sec_1", token)
        content = (sec.get("data") or {}).get("content") if isinstance(sec, dict) else None
        check("回滚后章节内容回到 V1", content == V1, str(content)[:60])

        status, versions2 = call("GET", f"/plans/{plan_id}/versions", token)
        nums2 = [v.get("version_number") for v in (versions2.get("data") or [])]
        # 回滚语义（`_mark_rollback`）：把 current_version 拨回目标版本、快照历史不动
        status, plan_after = call("GET", f"/plans/{plan_id}", token)
        current_version = (plan_after.get("data") or {}).get("current_version")
        check("回滚后预案当前版本指向目标快照",
              current_version == v1.get("version_number"),
              f"current_version={current_version} 目标={v1.get('version_number')}")
        check("快照历史未被删改", nums2 == nums, f"{nums} → {nums2}")
    finally:
        if plan_id:
            call("DELETE", f"/plans/{plan_id}", token)
            left = sql(f"select count(*) from plan_versions where plan_project_id='{plan_id}';")
            print(f"cleanup done: 探针预案已删除（残留版本 {left}）")

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-plan-versions.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
