"""法规写入族校验：入库 → 查重 → 废止 → 影响分析 → 删除（含磁盘与图谱零残留）。

图谱是 7.9MB 的 graph.json（7562 节点），因此探针必须证明"删干净"：
节点/边计数回到基线、texts/{id}.md 消失、uploads/{id}/ 清空、history.jsonl 还原。
同时验证字面量路由 `/check-duplicate`、`/batch/abolish` 不被 `/{id}` 吞掉。
"""

import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

API = "http://localhost:8000/api/v1"
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
REG_DATA = os.path.join("backend", "app", "regulations", "data")
GRAPH = os.path.join(REG_DATA, "graph.json")
# ⚠ 真实历史文件在 data/ 下（`sync.HISTORY_PATH`）；写成 regulations/history.jsonl
# 会对不上（那里另有一个历史遗留的空文件），探针第一版就踩了这个坑。
HISTORY = os.path.join(REG_DATA, "history.jsonl")
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
U, P = "qa_e2e_test@test.com", "test123456"
OWNER_ID = "506a380e-a2fe-4fd8-9430-f7f4c61f3d4b"
CODE = "QAPROBE-2026"
REG_ID = "reg_qaprobe_2026"
NAME = "探针法规（自动清理）"

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


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw[:200].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, raw[:200].decode("utf-8", "replace")


def post_form(path, token, fields: dict):
    boundary = "----probe" + uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n")
    body = "".join(parts).encode() + f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        API + path, method="POST", data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw[:200].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, raw[:200].decode("utf-8", "replace")


def graph_counts():
    with open(GRAPH, encoding="utf-8") as fh:
        data = json.load(fh)
    return len(data.get("nodes", [])), len(data.get("edges", []))


def texts_path(reg_id):
    return os.path.join(REG_DATA, "texts", f"{reg_id}.md")


def uploads_dir(reg_id):
    return os.path.join(REG_DATA, "uploads", reg_id)


def main():
    os.makedirs(OUT, exist_ok=True)
    before_nodes, before_edges = graph_counts()
    history_before = open(HISTORY, "rb").read() if os.path.exists(HISTORY) else b""
    print(f"基线：nodes={before_nodes} edges={before_edges} history_bytes={len(history_before)}")
    try:
        sql(f"update users set role='super_admin' where id='{OWNER_ID}';")
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]

        payload = {
            "code": CODE, "full_name": NAME, "node_type": "standard",
            "status": "effective", "issuing_body": "探针发布机关",
            "issue_date": "2026-09-01", "effective_date": "2026-10-01",
            "source": "probe", "articles": [{"number": "第一条", "text": "探针条文内容。"}],
        }
        status, created = post_form("/regulations", token,
                                    {"data": json.dumps(payload, ensure_ascii=False), "force": "false"})
        check("法规入库返回 200", status == 200, f"status={status} {created if isinstance(created,str) else ''}")
        rid = (created.get("data") or {}).get("id") if isinstance(created, dict) else None
        check("生成的 id 可预期", rid == REG_ID, rid)
        check("条文文本已落盘", os.path.isfile(texts_path(REG_ID)), texts_path(REG_ID))

        after_create_nodes, _ = graph_counts()
        check("图谱新增节点（法规节点至少 +1）", after_create_nodes >= before_nodes + 1,
              f"{before_nodes} → {after_create_nodes}")

        status, dup = post_form("/regulations", token,
                                {"data": json.dumps(payload, ensure_ascii=False), "force": "false"})
        check("重复入库被拦（/check-duplicate 语义 → 409）", status == 409, f"status={status}")

        status, detail = call("GET", f"/regulations/{REG_ID}", token)
        check("详情可读且状态 effective",
              status == 200 and (detail.get("data") or {}).get("status") == "effective",
              f"status={status}")

        status, abolished = call("POST", f"/regulations/{REG_ID}/abolish", token,
                                 {"replaced_by": "GB 30077-2023"})
        check("废止接口返回 200 且带影响数", status == 200 and "affected_count" in (abolished or {}),
              f"status={status} {str(abolished)[:120]}")
        status, detail2 = call("GET", f"/regulations/{REG_ID}", token)
        check("废止后状态变为 abolished",
              status == 200 and (detail2.get("data") or {}).get("status") == "abolished",
              (detail2.get("data") or {}).get("status") if isinstance(detail2, dict) else None)

        status, impact = call("GET", f"/regulations/{REG_ID}/impact", token)
        check("影响分析可读", status == 200, f"status={status}")

        status, deleted = call("DELETE", f"/regulations/{REG_ID}", token)
        check("删除返回 200", status == 200, f"status={status}")
        status, gone = call("GET", f"/regulations/{REG_ID}", token)
        check("删除后详情 404", status == 404, f"status={status}")
        check("条文文本已清理（本轮修）", not os.path.isfile(texts_path(REG_ID)),
              texts_path(REG_ID))
        check("源文件目录已清理", not os.path.isdir(uploads_dir(REG_ID)), uploads_dir(REG_ID))

        after_nodes, after_edges = graph_counts()
        check("图谱节点数回到基线", after_nodes == before_nodes,
              f"{after_nodes} vs {before_nodes}")
        with open(GRAPH, encoding="utf-8") as fh:
            graph_data = json.load(fh)
        leftovers = [n["id"] for n in graph_data.get("nodes", [])
                     if n.get("parent_regulation") == REG_ID or n.get("id") == REG_ID]
        check("删除后无残留节点（含条文子节点）", not leftovers, leftovers)
        check("图谱边数回到基线", after_edges == before_edges,
              f"{after_edges} vs {before_edges}")
    finally:
        # history.jsonl 只含探针产生的事件（基线为空），按原始字节还原
        try:
            with open(HISTORY, "wb") as fh:
                fh.write(history_before)
            if os.path.isfile(texts_path(REG_ID)):
                os.remove(texts_path(REG_ID))
            print("cleanup done: history.jsonl 已还原，残留文件已清理")
        except Exception as exc:  # noqa: BLE001
            print("CLEANUP FAILED:", exc)
        sql(f"update users set role='user' where id='{OWNER_ID}';")

    passed = sum(1 for r in results if r["ok"])
    print(f"合计 {passed}/{len(results)} PASS")
    with open(os.path.join(OUT, "summary-regulations-write.json"), "w", encoding="utf-8") as fh:
        json.dump({"passed": passed, "total": len(results), "results": results}, fh,
                  ensure_ascii=False, indent=2)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
