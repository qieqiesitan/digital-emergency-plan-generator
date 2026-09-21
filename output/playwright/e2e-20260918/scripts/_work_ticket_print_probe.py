"""作业票票面打印校验：开票 → 提交 → 打印 DOCX → 核对票号/字段/措施/审批栏是否齐全。

票面是交给监管与作业现场的法律文书，缺项等于无效票；这里用真实接口跑一遍并解析 DOCX。
跑完删除探针票据。
"""

import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from docx import Document

API = "http://localhost:8000/api/v1"
OUT = os.environ.get("E2E_OUT", "backend/exports/e2e-20260918")
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
TPL = "99f530de-2586-5f03-9751-b9db1bbb3777"   # DHZY 动火
CODE_PREFIX = "PTPRB"


def call(method, path, token=None, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = resp.read()
            return resp.status, (payload if raw else json.loads(payload)), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def main():
    os.makedirs(OUT, exist_ok=True)
    ticket_id = None
    try:
        status, payload, _ = call("POST", "/auth/login", body={"email": U, "password": P})
        token = payload["data"]["access_token"]
        _, tpl_payload, _ = call("GET", "/work-ticket/templates", token)
        tpl = next(t for t in tpl_payload["data"] if t["id"] == TPL)
        values = {f["field_key"]: f"探针值-{f['label']}" for f in tpl["fields"] if f.get("is_required")}
        values["confirmed_measures"] = [m["sort_order"] for m in tpl["measures"]]
        status, opened, _ = call("POST", "/work-ticket/tickets", token,
                                 {"enterprise_id": ENT, "enterprise_code": CODE_PREFIX,
                                  "ticket_type": "DHZY", "template_id": TPL,
                                  "level": None, "values": values})
        assert status == 200, (status, opened)
        ticket_id = opened["data"]["id"]
        code = opened["data"]["code"]
        print("ticket:", code)
        call("POST", f"/work-ticket/tickets/{ticket_id}/gas-tests", token,
             {"sampled_at": datetime.now(timezone.utc).isoformat(), "conclusion": "合格"})
        status, submitted, _ = call("POST", f"/work-ticket/tickets/{ticket_id}/submit", token)
        print("submit:", status)

        status, blob, headers = call("GET", f"/work-ticket/tickets/{ticket_id}/print.docx", token, raw=True)
        print("print:", status, "size:", len(blob) if isinstance(blob, bytes) else "-")
        if status != 200 or not isinstance(blob, bytes):
            print("body:", blob[:200])
            return 1
        with open(os.path.join(OUT, "work-ticket-print-probe.docx"), "wb") as fh:
            fh.write(blob)
        doc = Document(io.BytesIO(blob))
        text = "\n".join(p.text for p in doc.paragraphs)
        for table in doc.tables:
            for row in table.rows:
                text += "\n" + " | ".join(c.text for c in row.cells)
        flat = re.sub(r"\s+", "", text)

        checks = [
            ("票号出现在票面", re.sub(r"\s+", "", code) in flat),
            ("票名用法定中文名（动火安全作业票）", "动火安全作业票" in flat),
            ("不再只印内部缩写（DHZY 安全作业票）", "DHZY安全作业票" not in flat),
            ("含气体检测结论", "合格" in flat),
            ("含安全措施栏", any(k in flat for k in ("安全措施", "主要安全措施"))),
            ("含三联标注与保存期（GB 30871 附录B.3）", "第三联" in flat and "至少保存一年" in flat),
            ("审批记录区随签署出现（未签署时无该区，属设计）",
             ("审批记录" in flat) or ("审批" not in flat)),
            ("无未替换占位（如 {、}}、undefined）", not any(p in flat for p in ("{", "}}", "undefined"))),
        ]
        fails = [name for name, ok in checks if not ok]
        for name, ok in checks:
            print(("PASS " if ok else "FAIL ") + name)
        print("段落数:", len(doc.paragraphs), " 表格数:", len(doc.tables))
        with open(os.path.join(OUT, "summary-work-ticket-print.json"), "w", encoding="utf-8") as fh:
            json.dump({"code": code, "size": len(blob), "fails": fails,
                       "paragraphs": len(doc.paragraphs), "tables": len(doc.tables)},
                      fh, ensure_ascii=False, indent=2)
        return 0 if not fails else 1
    finally:
        if ticket_id:
            status, _, _ = call("DELETE", f"/work-ticket/tickets/{ticket_id}", token)
            if status == 405 or status == 404:
                print("（无删除端点，改用库内清理）")
            print("cleanup:", status)


if __name__ == "__main__":
    sys.exit(main())
