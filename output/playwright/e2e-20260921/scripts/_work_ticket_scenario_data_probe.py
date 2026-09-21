"""作业票情景数据化端到端探针（真接口，只读）。

验证四件事：
  1. `/templates` 每票种带出 `scenario_fields`，项数与 YAML 声明一致
  2. 传「明确不涉及」的情景后，各票种的 not_applicable 增多（判定真的生效）
  3. 不传情景时保持保守（不自作主张判「不涉及」）
  4. 断路票（唯一条件是自动的 night_work）也能给出判定，不再是全 unknown

用法（仓库根目录）：
    python output/playwright/e2e-20260921/scripts/_work_ticket_scenario_data_probe.py
证据输出：同目录 work-ticket-scenario-data.json
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
EVIDENCE = Path(__file__).resolve().parent / "work-ticket-scenario-data.json"

# 各票种「人工情景全不涉及」的输入（键与 YAML 的 scenario 列表一致）
SCENARIOS: dict[str, dict[str, bool]] = {
    "DHZY": {
        "internal_work": False, "connected_pipeline": False, "surroundings_ignition": False,
        "in_tank_area": False, "height_work": False, "has_flammable_lining": False,
        "surrounding_hazardous_ops": False,
    },
    "YXKJ": {
        "hazardous_residue": False, "connected_pipeline": False, "rotating_equipment": False,
        "flammable_atmosphere": False, "dust_inside": False, "corrosive_medium": False,
    },
    "MBCD": {
        "toxic_medium": False, "explosion_hazard_area": False, "corrosive_medium": False,
        "high_temp_medium": False, "low_temp_medium": False, "multi_point_same_pipe": False,
    },
    "GCZY": {
        "toxic_gas_area": False, "scaffold_used": False, "layered_work": False,
        "ladder_used": False, "light_shed": False, "load_bearing_plate": False,
        "night_or_poor_light": False, "outdoor": False,
    },
    "QZDZ": {
        "hazardous_equipment_nearby": False, "building_as_anchor": False,
        "near_power_line": False, "pipe_as_anchor": False, "underground_facilities": False,
        "overhead_facilities": False, "explosion_hazard_area": False, "outdoor": False,
    },
    "LSYD": {
        "explosion_hazard_area": False, "line_elevated": False, "cross_road": False,
        "line_along_surface": False, "underground_cable": False, "outdoor": False,
    },
    "PTZY": {
        "underground_cable": False, "underground_pipeline": False,
        "on_road": False, "hazardous_area": False,
    },
    "DLZY": {},  # 唯一条件 night_work 为自动推断，无人工项
}

EXPECTED_SCENARIO_COUNTS = {
    "DHZY": 7, "YXKJ": 6, "MBCD": 6, "GCZY": 8,
    "QZDZ": 8, "LSYD": 6, "PTZY": 4, "DLZY": 0,
}


def call(path: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def dist(payload: dict) -> dict[str, int]:
    out = {"unknown": 0, "applicable": 0, "not_applicable": 0}
    for item in payload.get("measures_suggestions", []):
        out[item["suggest"]] = out.get(item["suggest"], 0) + 1
    return out


def main() -> int:
    token = call("/auth/login", body={"email": USER[0], "password": USER[1]})["data"][
        "access_token"
    ]
    templates = call("/work-ticket/templates", token)["data"]
    checks: dict[str, bool] = {}
    detail: dict[str, dict] = {}

    picked: dict[str, dict] = {}
    for tpl in templates:
        picked.setdefault(tpl["code"], tpl)

    # 1) scenario_fields 与声明一致
    counts = {code: len(tpl.get("scenario_fields") or []) for code, tpl in picked.items()}
    detail["scenario_field_counts"] = counts
    checks["scenario_fields_match_declaration"] = counts == EXPECTED_SCENARIO_COUNTS

    for code, tpl in picked.items():
        params = {"enterprise_id": ENTERPRISE, "template_id": tpl["id"]}
        if tpl.get("level"):
            params["level"] = tpl["level"]
        query = urllib.parse.urlencode(params)
        plain = call(f"/work-ticket/prefill?{query}", token)["data"]
        scenario = SCENARIOS.get(code) or {}
        with_scenario = call(
            f"/work-ticket/prefill?{query}&scenario={urllib.parse.quote(json.dumps(scenario))}",
            token,
        )["data"]
        detail[code] = {"plain": dist(plain), "with_scenario": dist(with_scenario)}

    # 2) 有条件的票种：传情景后 not_applicable 增多
    manual_types = [code for code, scenario in SCENARIOS.items() if scenario]
    checks["scenario_enables_judgement"] = all(
        detail[c]["with_scenario"]["not_applicable"] > detail[c]["plain"]["not_applicable"]
        for c in manual_types
    )

    # 3) 不传人工情景时，判定只能来自自动推断项（数量不超过自动项相关措施数上限）
    #    DHZY 上限 6：height_work 1 条 + has_other_tickets 2 条 + 气焊/电焊 3 条
    #    （该企业无动火历史票，故气焊/电焊不推断，实测会少于上限；上限是防回归的宽值）
    AUTO_RELATED_UPPER = {
        "DHZY": 6, "YXKJ": 1, "MBCD": 1, "GCZY": 1,
        "QZDZ": 2, "LSYD": 1, "PTZY": 2, "DLZY": 1,
    }
    checks["conservative_without_scenario"] = all(
        detail[c]["plain"]["not_applicable"] <= AUTO_RELATED_UPPER[c] for c in manual_types
    )

    # 4) 断路票：唯一条件是自动的 night_work，也必须有判定（不再全 unknown）
    dlzy = detail.get("DLZY", {})
    checks["dlzy_has_judgement"] = bool(dlzy) and (
        dlzy["plain"]["unknown"] < 4 or dlzy["plain"]["not_applicable"] > 0
    )

    EVIDENCE.write_text(
        json.dumps(
            {"detail": detail, "checks": checks, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(detail, ensure_ascii=False, indent=2))
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
