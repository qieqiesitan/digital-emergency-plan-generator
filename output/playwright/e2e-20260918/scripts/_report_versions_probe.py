"""报告版本闭环（风险评估 / 资源调查共用工厂）：改正文 → 存快照 → 再改 → 回滚 → 正文回到快照。
零 AI：报告行直接建库、正文走 PUT /content。跑完删除报告与版本行。
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
KIND = os.environ.get("E2E_KIND", "risk-assessment")   # risk-assessment | resource-investigation
TABLE = {"risk-assessment": ("risk_assessment_reports", "risk_assessment_versions"),
         "resource-investigation": ("resource_investigation_reports",
                                    "resource_investigation_versions")}[KIND]
V1 = "## 第一章\n\n正文甲版"
V2 = "## 第一章\n\n正文乙版"

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


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        report_table, version_table = TABLE
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]
        state["report"] = sql(
            f"insert into {report_table} (id, enterprise_id, title, content, summary, status,"
            f" generated_by) values (gen_random_uuid(),'{ENT}','版本探针报告', $doc${V1}$doc$,"
            " '{}'::jsonb, 'completed','ai') returning id;")
        check(f"建探针报告（{KIND}）", bool(state["report"]), state["report"])

        call("PUT", f"/enterprises/{ENT}/{KIND}/content", token, {"content": V1}, expect=200,
             label="保存正文 V1")
        status, ver1 = call("POST", f"/enterprises/{ENT}/{KIND}/versions", token,
                            {"description": "V1 快照"}, expect=200, label="存 V1 快照")
        v1 = (ver1.get("data") or {}) if isinstance(ver1, dict) else {}

        call("PUT", f"/enterprises/{ENT}/{KIND}/content", token, {"content": V2}, expect=200,
             label="保存正文 V2")
        status, ver2 = call("POST", f"/enterprises/{ENT}/{KIND}/versions", token,
                            {"description": "V2 快照"}, expect=200, label="存 V2 快照")
        v2 = (ver2.get("data") or {}) if isinstance(ver2, dict) else {}

        status, versions = call("GET", f"/enterprises/{ENT}/{KIND}/versions", token)
        nums = [v.get("version_number") for v in (versions.get("data") or [])]
        check("版本列表两条且倒序", status == 200 and nums == sorted(nums, reverse=True)
              and len(nums) >= 2, nums)
        check("快照版本号递增", v2.get("version_number", 0) > v1.get("version_number", 0),
              f"{v1.get('version_number')} → {v2.get('version_number')}")

        # 回滚前：预览接口读到的是 V2
        status, pv = call("GET", f"/enterprises/{ENT}/{KIND}/preview", token)
        html_before = (pv.get("data") or {}).get("html") if isinstance(pv, dict) else ""
        check("回滚前正文为 V2", "正文乙版" in (html_before or ""), f"status={status}")

        status, rolled = call("POST", f"/enterprises/{ENT}/{KIND}/versions/{v1.get('id')}/rollback",
                              token, expect=200, label="回滚到 V1")
        check("回滚响应带 current_version", (rolled or {}).get("current_version")
              == v1.get("version_number"),
              f"{rolled}")

        status, pv2 = call("GET", f"/enterprises/{ENT}/{KIND}/preview", token)
        html_after = (pv2.get("data") or {}).get("html") if isinstance(pv2, dict) else ""
        check("回滚后正文真的回到 V1", "正文甲版" in (html_after or "")
              and "正文乙版" not in (html_after or ""), f"status={status}")
        check("库内 current_version 已同步", sql(
            f"select current_version from {report_table} where id='{state['report']}';")
              == str(v1.get("version_number")))
    finally:
        if state.get("report"):
            report_table, version_table = TABLE
            sql(f"delete from {version_table} where report_id='{state['report']}';")
            sql(f"delete from {report_table} where id='{state['report']}';")
            left = sql(f"select count(*) from {version_table} where report_id='{state['report']}';")
            print(f"cleanup done: 探针报告已删除（残留版本 {left}）")
    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, f"summary-report-versions-{KIND}.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "kind": KIND, "results": results},
                  fh, ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
