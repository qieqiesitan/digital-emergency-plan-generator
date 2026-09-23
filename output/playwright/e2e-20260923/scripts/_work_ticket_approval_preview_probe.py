"""开票前审批链预检实测（真接口）。

背景（2026-09-23 用户实测）：用户在「西安宝岳空间科技有限公司」提交了一张特级动火票，
票卡在"审批中"且不在任何人待办里——因为特级动火要求「主管领导」，
而该企业组织架构里没有同名节点，审批人匹配落空。

本探针用「新建的空白企业」把这个场景复制出来，验证新端点
`GET /work-ticket/approval-preview` 能在提交前就报出「本节点无人可审批」。

用法（仓库根目录）：
    python output/playwright/e2e-20260923/scripts/_work_ticket_approval_preview_probe.py
证据输出：同目录 work-ticket-approval-preview.json
探针会创建并删除一个临时企业。
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "http://localhost:8000/api/v1"
USER = ("qa_e2e_test@test.com", "test123456")
EVIDENCE = Path(__file__).resolve().parent / "work-ticket-approval-preview.json"
# 有组织架构与成员的既有企业（对照组）
CONFIGURED_ENTERPRISE = "10e11995-e682-405a-9035-fbde13cca213"


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def preview(token: str, enterprise_id: str, template_id: str) -> list[dict]:
    query = urllib.parse.urlencode(
        {"enterprise_id": enterprise_id, "template_id": template_id}
    )
    return call("GET", f"/work-ticket/approval-preview?{query}", token=token)[1]["data"]


def main() -> int:
    token = call("POST", "/auth/login", {"email": USER[0], "password": USER[1]})[1]["data"][
        "access_token"
    ]
    templates = call("GET", "/work-ticket/templates", token=token)[1]["data"]
    fire = next(t for t in templates if t["code"] == "DHZY" and t["level"] == "特级")

    checks: dict[str, bool] = {}
    detail: dict = {}
    blank_enterprise_id = ""

    # 1) 空白企业（无组织架构、无成员）——复现用户的实际处境
    status, created = call(
        "POST",
        "/enterprises",
        {"name": "探针-审批链预检-可删"},
        token,
    )
    checks["blank_enterprise_created"] = status == 201
    if status == 201:
        blank_enterprise_id = created["data"]["id"]
        blank_preview = preview(token, blank_enterprise_id, fire["id"])
        detail["blank_enterprise_preview"] = blank_preview
        checks["preview_lists_nodes"] = len(blank_preview) > 0
        checks["blank_enterprise_has_no_eligible_approver"] = all(
            row["eligible_count"] == 0 for row in blank_preview
        )
        detail["blank_required_role"] = blank_preview[0]["role_code"] if blank_preview else None

    # 2) 对照组：有组织架构与成员的既有企业
    configured = preview(token, CONFIGURED_ENTERPRISE, fire["id"])
    detail["configured_enterprise_preview"] = configured
    checks["configured_enterprise_preview_ok"] = len(configured) > 0

    # 清理临时企业
    if blank_enterprise_id:
        call("DELETE", f"/enterprises/{blank_enterprise_id}", token=token)
        remaining = call(
            "GET", f"/enterprises?page=1&page_size=100", token=token
        )[1]
        items = (remaining.get("data") or {}).get("items") or []
        detail["cleaned"] = all(item["id"] != blank_enterprise_id for item in items)
        checks["temp_enterprise_cleaned"] = detail["cleaned"]

    EVIDENCE.write_text(
        json.dumps(
            {"checks": checks, "detail": detail, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    print("空白企业要求的岗位:", detail.get("blank_required_role"))
    print("空白企业各节点匹配人数:", [r["eligible_count"] for r in detail.get("blank_enterprise_preview", [])])
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
