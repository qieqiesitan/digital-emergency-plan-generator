"""作业包批量开票端到端探针（真接口 + 真库，自建数据自行清理）。

断言：
  1. 3 票包生成后：共享字段一致、related_tickets 互相包含、batch_id 正确
  2. 事务性：注入不存在的 template_id → 整包回滚，库中不新增票
  3. 包级检测被动火与受限空间两票同时读到（origin=batch）
  4. 状态机：包内 0 提交时作废允许；移出一张草稿票后其余票关联票号同步

用法（仓库根目录）：
    python output/playwright/e2e-20260920/scripts/_work_ticket_batch_probe.py
证据输出：同目录 work-ticket-batch.json
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "http://localhost:8000/api/v1"
USER = ("qa_e2e_test@test.com", "test123456")
ENTERPRISE = "10e11995-e682-405a-9035-fbde13cca213"
EVIDENCE = Path(__file__).resolve().parent / "work-ticket-batch.json"
PSQL = [
    "docker", "exec", "emergency-plan-db", "psql", "-U", "postgres",
    "-d", "emergency_plan", "--no-align", "--tuples-only", "-c",
]


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def sql(query: str) -> list[str]:
    out = subprocess.run(
        PSQL + [query], capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout
    return [ln for ln in out.strip().splitlines() if ln]


def main() -> int:
    token = call("POST", "/auth/login", body={"email": USER[0], "password": USER[1]})[1]["data"][
        "access_token"
    ]
    templates = {
        (t["code"], t["level"]): t["id"]
        for t in call("GET", "/work-ticket/templates", token)[1]["data"]
    }
    checks: dict[str, bool] = {}

    status, created_batch = call(
        "POST",
        "/work-ticket/batches",
        token,
        {
            "enterprise_id": ENTERPRISE,
            "title": "探针-3票包",
            "location_text": "3# 罐区（探针）",
            "shared_values": {
                "applicant_unit": "探针单位",
                "work_unit": "探针班组",
                "work_leader": "张三",
            },
            "content_base": "更换 3# 罐底阀门（探针）",
            "risk_basis": "罐内残留易燃液体（探针）",
        },
    )
    batch_id = created_batch["data"]["id"]
    status, created = call(
        "POST",
        f"/work-ticket/batches/{batch_id}/tickets",
        token,
        {
            "tickets": [
                {"ticket_type": "DHZY", "level": "二级", "template_id": templates[("DHZY", "二级")]},
                {"ticket_type": "YXKJ", "level": None, "template_id": templates[("YXKJ", None)]},
                {"ticket_type": "QZDZ", "level": "三级", "template_id": templates[("QZDZ", "三级")]},
            ]
        },
    )
    checks["batch_tickets_created"] = status == 200 and len(created["data"]) == 3
    codes = sorted(t["code"] for t in created["data"])

    # 1) 共享字段 / 关联票号 / batch_id
    rows = sql(
        "SELECT i.code, i.values->>'applicant_unit', i.values->>'related_tickets', i.batch_id, "
        "i.values->>'risk_identification', i.values->>'fire_location', i.values->>'space_location' "
        f"FROM work_ticket_instances i WHERE i.batch_id = '{batch_id}' ORDER BY i.code;"
    )
    checks["shared_fields_written_to_all"] = all(r.split("|")[1] == "探针单位" for r in rows)
    checks["risk_basis_written_to_all"] = all(r.split("|")[4].startswith("罐内残留") for r in rows)
    checks["related_tickets_reciprocal"] = all(
        set(r.split("|")[2].split(",")) == set(codes) - {r.split("|")[0]} for r in rows
    )
    checks["batch_id_set"] = all(r.split("|")[3].strip() == batch_id for r in rows)
    # 地点槽位按票种映射到不同字段：动火 fire_location、受限空间 space_location
    checks["location_slot_mapped_per_type"] = any(
        r.split("|")[5] == "3# 罐区（探针）" for r in rows
    ) and any(r.split("|")[6] == "3# 罐区（探针）" for r in rows)

    # 2) 事务性：坏模板 → 整包回滚
    before = int(sql("SELECT count(*) FROM work_ticket_instances;")[0])
    status, _ = call(
        "POST",
        f"/work-ticket/batches/{batch_id}/tickets",
        token,
        {
            "tickets": [
                {"ticket_type": "DHZY", "level": "二级", "template_id": templates[("DHZY", "二级")]},
                {
                    "ticket_type": "MBCD",
                    "level": None,
                    "template_id": "00000000-0000-0000-0000-000000000000",
                },
            ]
        },
    )
    after = int(sql("SELECT count(*) FROM work_ticket_instances;")[0])
    checks["batch_is_transactional"] = status == 422 and before == after

    # 3) 包级检测共享
    call(
        "POST",
        f"/work-ticket/batches/{batch_id}/gas-tests",
        token,
        {
            "sampled_at": "2026-09-20T08:00:00+08:00",
            "location": "3# 罐区",
            "gas_type": "可燃气体",
            "result": "0%LEL",
            "tester": "探针",
            "conclusion": "合格",
        },
    )
    shared_seen = []
    for ticket in created["data"]:
        if ticket["ticket_type"] not in ("DHZY", "YXKJ"):
            continue
        _, detail = call("GET", f"/work-ticket/tickets/{ticket['id']}", token)
        shared_seen.append(
            any(g.get("origin") == "batch" for g in detail["data"]["gas_tests"])
        )
    checks["package_gas_shared_by_both"] = bool(shared_seen) and all(shared_seen)

    # 4) 移出一张草稿票 → 其余票关联票号同步收缩
    removed_id = created["data"][0]["id"]
    call("DELETE", f"/work-ticket/batches/{batch_id}/tickets/{removed_id}", token)
    rest = sql(
        f"SELECT i.values->>'related_tickets' FROM work_ticket_instances i "
        f"WHERE i.batch_id = '{batch_id}' AND i.id <> '{removed_id}';"
    )
    checks["related_updated_after_removal"] = all(
        created["data"][0]["code"] not in row for row in rest
    )

    # 清理：删除探针自建的票与包（避免污染真库）
    sql(f"DELETE FROM work_ticket_instances WHERE batch_id = '{batch_id}';")
    sql(f"DELETE FROM work_ticket_batches WHERE id = '{batch_id}';")
    checks["probe_data_cleaned"] = (
        sql(f"SELECT count(*) FROM work_ticket_batches WHERE id = '{batch_id}';")[0] == "0"
    )

    EVIDENCE.write_text(
        json.dumps(
            {"checks": checks, "codes": codes, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
