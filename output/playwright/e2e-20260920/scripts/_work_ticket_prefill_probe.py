"""作业票智能预填端到端探针（真接口，只读不写库）。

验证链路：企业档案/历史票/成员台账 → 确定性预填；作业情景 → 措施建议引擎。

用法（仓库根目录）：
    python output/playwright/e2e-20260920/scripts/_work_ticket_prefill_probe.py
证据输出：同目录 work-ticket-prefill.json
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "http://localhost:8000/api/v1"
USER = ("qa_e2e_test@test.com", "test123456")
ENTERPRISE = "10e11995-e682-405a-9035-fbde13cca213"
EVIDENCE = Path(__file__).resolve().parent / "work-ticket-prefill.json"


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def main() -> int:
    token = call("POST", "/auth/login", body={"email": USER[0], "password": USER[1]})["data"][
        "access_token"
    ]
    templates = call("GET", "/work-ticket/templates", token)["data"]
    fire = next(t for t in templates if t["code"] == "DHZY" and t["level"] == "二级")

    # 1) 不带情景：只应带出可确定的值，措施建议保持 unknown（保守）
    base = urllib.parse.urlencode(
        {
            "enterprise_id": ENTERPRISE,
            "template_id": fire["id"],
            "level": "二级",
        }
    )
    plain = call("GET", f"/work-ticket/prefill?{base}", token)["data"]
    plain_suggestions = {s["sort_order"]: s for s in plain["measures_suggestions"]}

    # 2) 带情景：明确「不在罐区」时，第 4 条应给出「不涉及」建议
    scenario = json.dumps({"in_tank_area": False})
    with_scenario = call(
        "GET",
        f"/work-ticket/prefill?{base}&scenario={urllib.parse.quote(scenario)}",
        token,
    )["data"]
    scenario_suggestions = {s["sort_order"]: s for s in with_scenario["measures_suggestions"]}

    locations = call("GET", f"/work-ticket/locations?enterprise_id={ENTERPRISE}", token)["data"]
    last = call(
        "GET",
        f"/work-ticket/last-ticket?enterprise_id={ENTERPRISE}&template_id={fire['id']}",
        token,
    )["data"]

    checks = {
        "applicant_unit_from_enterprise": bool(plain["values"].get("applicant_unit")),
        "values_meta_records_source": (
            plain["values_meta"].get("applicant_unit", {}).get("source") == "enterprise"
        ),
        "level_linked_into_ticket": plain["values"].get("fire_level") == "二级",
        "apply_time_defaulted": bool(plain["values"].get("apply_time")),
        "work_period_defaulted": isinstance(plain["values"].get("work_period"), list),
        "special_fields_not_prefilled": "fire_method" not in plain["values"],
        "suggestion_per_measure": len(plain["measures_suggestions"]) == 16,
        "conservative_unknown_without_scenario": (
            plain_suggestions[4]["suggest"] == "unknown"
        ),
        "scenario_turns_into_not_applicable": (
            scenario_suggestions[4]["suggest"] == "not_applicable"
            and "罐区" in (scenario_suggestions[4]["reason"] or "")
        ),
        "locations_shape": all(k in locations for k in ("floors", "zones", "objects")),
        "last_ticket_nullable": last is None or "code" in last,
    }
    EVIDENCE.write_text(
        json.dumps(
            {
                "values": plain["values"],
                "values_meta": plain["values_meta"],
                "suggestion_counts": {
                    key: sum(1 for s in plain["measures_suggestions"] if s["suggest"] == key)
                    for key in ("unknown", "applicable", "not_applicable")
                },
                "checks": checks,
                "all_passed": all(checks.values()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
