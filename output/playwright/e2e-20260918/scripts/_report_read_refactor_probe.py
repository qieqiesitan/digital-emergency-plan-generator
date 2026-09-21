"""③(a) 报告读取样板收敛验证（真实后端 + 真实数据库）。

被重构的 8 个端点（原来各自手抄"取企业 → 查报告 → 404"）：
  /resource-investigation{,,/summary,/preview,/export}  → 文案统一「未找到报告」
  /risk-assessment{,,/summary,/preview,/export}         → 「企业不存在」/「未找到已完成的风险评估报告」

覆盖分支：正常 200（并核对内容确实是插入的那条）/ 企业不存在 / 企业存在但无报告 / 报告属于他人企业（租户隔离）。
合成数据（报告行、临时企业行、导出的 docx）全部在结束时删除。
"""

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid

API = "http://localhost:8000/api/v1"
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"   # QA 企业
TMP_ENT_NAME = "探针企业-无报告"

CHAPTERS = [("第一章 概述", "本报告用于验证报告读取样板收敛后的行为等价。"),
            ("第二章 结论", "结论：读取路径未发生行为变化。")]
CONTENT = "\n\n".join(f"## {t}\n\n{b} PROBE_RI_BODY" for t, b in CHAPTERS)
SUMMARY = '{"marker":"PROBE_SUM","chapters":[]}'

results = []


def sql(statement: str) -> str:
    # psql 输出是 UTF-8（含中文企业名）；Windows 默认按 GBK 解码会炸
    out = subprocess.run(DB + [statement], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


def call(method, path, token=None, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            disp = resp.headers.get("Content-Disposition", "")
            return resp.status, (payload if raw else json.loads(payload)), ctype, disp
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type", ""), ""


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    print(("PASS " if ok else "FAIL ") + name + (f"  | {detail}" if detail else ""))


def detail_of(body):
    try:
        return json.loads(body).get("detail", "")
    except Exception:
        return str(body)[:120]


def delete_by_ids(table: str, ids) -> None:
    """按 id 删除（无有效 id 就跳过，避免拼出 'None' 这种非法 UUID）。"""
    valid = [f"'{i}'" for i in ids if i]
    if not valid:
        return
    sql(f"delete from {table} where id in ({','.join(valid)});")


def main():
    os.makedirs(OUT, exist_ok=True)
    ri_id = ra_id = other_ent = tmp_ent = None
    other_ri = other_ra = None
    server_files = []   # 容器内 /app/exports 下的导出物（精确路径）
    host_files = []     # 探针自己留档的下载副本
    try:
        _, pr, _, _ = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]
        uid = sql(f"select id from users where email='{U}';")
        ent_name = sql(f"select name from enterprises where id='{ENT}';")
        print("QA 用户:", uid, "| 企业:", ENT, ent_name)
        # 导出端点会把这两种文件名落到 /app/exports：只精确删这两个（不动历史导出）
        server_files += [f"/app/exports/{ent_name}_应急资源调查报告.docx",
                         f"/app/exports/{ent_name}_风险评估报告.docx"]

        # ---- 合成数据 ----
        ri_id = sql(
            "insert into resource_investigation_reports "
            "(id, enterprise_id, title, content, summary, status, generated_by) values "
            f"(gen_random_uuid(),'{ENT}','探针资源调查报告', $doc${CONTENT}$doc$, "
            f"'{SUMMARY}'::jsonb,'completed','ai') returning id;")
        ra_id = sql(
            "insert into risk_assessment_reports "
            "(id, enterprise_id, title, content, summary, status, generated_by) values "
            f"(gen_random_uuid(),'{ENT}','探针风险评估报告', $doc${CONTENT}$doc$, "
            f"'{SUMMARY}'::jsonb,'completed','ai') returning id;")
        tmp_ent = sql(
            "insert into enterprises (id, user_id, name, org_structure) values "
            f"(gen_random_uuid(),'{uid}','{TMP_ENT_NAME}','[]'::jsonb) returning id;")
        other_ent = sql(
            f"select id from enterprises where user_id <> '{uid}' order by created_at limit 1;")
        other_ri = sql(
            "insert into resource_investigation_reports "
            "(id, enterprise_id, title, content, summary, status, generated_by) values "
            f"(gen_random_uuid(),'{other_ent}','他人资源调查报告','x','{{}}'::jsonb,'completed','ai') "
            "returning id;")
        other_ra = sql(
            "insert into risk_assessment_reports "
            "(id, enterprise_id, title, content, summary, status, generated_by) values "
            f"(gen_random_uuid(),'{other_ent}','他人风险评估报告','x','{{}}'::jsonb,'completed','ai') "
            "returning id;")
        print("合成:", {"ri": ri_id, "ra": ra_id, "tmp_ent": tmp_ent, "other_ent": other_ent})

        # ---- 1~4：资源调查报告 4 端点 ----
        st, body, _, _ = call("GET", f"/enterprises/{ENT}/resource-investigation", token)
        check("RI get 200 且返回刚插入的报告", st == 200 and body.get("data", {}).get("id") == ri_id,
              f"status={st}")
        st, body, _, _ = call("GET", f"/enterprises/{ENT}/resource-investigation/summary", token)
        check("RI summary 200 且 summary 原样返回",
              st == 200 and body.get("data", {}).get("marker") == "PROBE_SUM", f"status={st}")
        st, body, _, _ = call("GET", f"/enterprises/{ENT}/resource-investigation/preview", token)
        check("RI preview 200 且正文渲染进 html",
              st == 200 and "PROBE_RI_BODY" in (body.get("data", {}).get("html") or ""),
              f"status={st}")
        st, blob, ctype, disp = call("GET", f"/enterprises/{ENT}/resource-investigation/export",
                                     token, raw=True)
        fname = urllib.parse.unquote(disp)   # Content-Disposition 里文件名是 percent-encoded
        ok = st == 200 and blob[:2] == b"PK" and "应急资源调查报告" in fname and ent_name in fname
        check("RI export 200 且 docx 文件名用了企业名", ok, f"status={st} size={len(blob)}")
        if st == 200:
            fp = os.path.join(OUT, "probe-read-refactor-resource.docx")
            open(fp, "wb").write(blob)
            host_files.append(fp)

        # ---- 5~8：风险评估报告 4 端点 ----
        st, body, _, _ = call("GET", f"/enterprises/{ENT}/risk-assessment", token)
        check("RA get 200 且返回刚插入的报告", st == 200 and body.get("data", {}).get("id") == ra_id,
              f"status={st}")
        st, body, _, _ = call("GET", f"/enterprises/{ENT}/risk-assessment/summary", token)
        check("RA summary 200 且 summary 原样返回",
              st == 200 and body.get("data", {}).get("marker") == "PROBE_SUM", f"status={st}")
        st, body, _, _ = call("GET", f"/enterprises/{ENT}/risk-assessment/preview", token)
        check("RA preview 200 且正文渲染进 html",
              st == 200 and "PROBE_RI_BODY" in (body.get("data", {}).get("html") or ""),
              f"status={st}")
        st, blob, ctype, disp = call("GET", f"/enterprises/{ENT}/risk-assessment/export",
                                     token, raw=True)
        fname = urllib.parse.unquote(disp)
        ok = st == 200 and blob[:2] == b"PK" and "风险评估报告" in fname and ent_name in fname
        check("RA export 200 且 docx 文件名用了企业名", ok, f"status={st} size={len(blob)}")
        if st == 200:
            fp = os.path.join(OUT, "probe-read-refactor-risk.docx")
            open(fp, "wb").write(blob)
            host_files.append(fp)

        # ---- 分支：企业不存在（随机 UUID） ----
        ghost = str(uuid.uuid4())
        for label, ep, want in (("RI", "resource-investigation", "未找到报告"),
                                ("RA", "risk-assessment", "企业不存在")):
            st, body, _, _ = call("GET", f"/enterprises/{ghost}/{ep}", token)
            d = detail_of(body)
            check(f"{label} 未知企业 → 404「{want}」", st == 404 and d == want, f"status={st} detail={d}")

        # ---- 分支：企业存在但报告缺失（临时企业） ----
        for label, ep, want in (("RI", "resource-investigation", "未找到报告"),
                                ("RA", "risk-assessment", "未找到已完成的风险评估报告")):
            st, body, _, _ = call("GET", f"/enterprises/{tmp_ent}/{ep}", token)
            d = detail_of(body)
            check(f"{label} 无报告企业 → 404「{want}」", st == 404 and d == want, f"status={st} detail={d}")

        # ---- 分支：报告属于他人企业（租户隔离） ----
        for label, ep, want in (("RI", "resource-investigation", "未找到报告"),
                                ("RA", "risk-assessment", "企业不存在")):
            st, body, _, _ = call("GET", f"/enterprises/{other_ent}/{ep}", token)
            d = detail_of(body)
            check(f"{label} 他人企业(有报告) → 404 不泄漏", st == 404 and d == want,
                  f"status={st} detail={d}")

    finally:
        delete_by_ids("resource_investigation_reports", [ri_id, other_ri])
        delete_by_ids("risk_assessment_reports", [ra_id, other_ra])
        if tmp_ent:
            sql(f"delete from enterprises where id='{tmp_ent}';")
        # 只删本次探针生成的两个精确路径（历史导出文件是用户数据，不能碰）
        if server_files:
            subprocess.run(["docker", "exec", "emergency-plan-backend", "rm", "-f", "--"] + server_files,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        leftover_files = [p for p in server_files
                          if subprocess.run(["docker", "exec", "emergency-plan-backend", "test", "-e", p],
                                            capture_output=True, text=True,
                                            encoding="utf-8", errors="replace").returncode == 0]
        leftover = "n/a"
        if ri_id or other_ri:
            ids = ",".join(f"'{i}'" for i in (ri_id, other_ri) if i)
            leftover = sql(f"select count(*) from resource_investigation_reports where id in ({ids});")
        print("清理后残留行:", leftover, "| 残留导出文件:", leftover_files, "| 下载副本:", host_files)
        with open(os.path.join(OUT, "summary-report-read-refactor.json"), "w", encoding="utf-8") as fh:
            json.dump({"results": results,
                       "passed": sum(1 for r in results if r["ok"]),
                       "total": len(results)}, fh, ensure_ascii=False, indent=2)
    fails = [r["name"] for r in results if not r["ok"]]
    print(f"\n=== {len(results) - len(fails)}/{len(results)} PASS ===")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
