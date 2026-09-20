"""诊断探针：作业情景对非动火票是否真的无效（只读）。

背景（2026-09-20 用户反馈）：开票向导第 0 步的「作业情景」是固定 7 项且全是动火语境，
切换票种时不变。本探针用接口层数据回答两件事：
  1. 每个票种的措施建议分布（unknown / applicable / not_applicable）
  2. 对受限空间票显式传「不在罐区」情景后，建议是否发生变化

用法（仓库根目录）：
    python output/playwright/e2e-20260920/scripts/_work_ticket_scenario_scope_probe.py
证据输出：同目录 work-ticket-scenario-scope.json
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
EVIDENCE = Path(__file__).resolve().parent / "work-ticket-scenario-scope.json"


def call(path: str, token: str):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def main() -> int:
    login = urllib.request.Request(
        API + "/auth/login",
        data=json.dumps({"email": USER[0], "password": USER[1]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(login, timeout=30) as resp:
        token = json.loads(resp.read())["data"]["access_token"]

    templates = [
        t
        for t in call("/work-ticket/templates", token)["data"]
        if t["code"] in ("DHZY", "YXKJ", "GCZY", "QZDZ", "LSYD", "PTZY", "DLZY", "MBCD")
    ]

    def prefill(template_id: str, scenario: dict | None = None) -> dict:
        params = {
            "enterprise_id": ENTERPRISE,
            "template_id": template_id,
            "level": (next((t["level"] for t in templates if t["id"] == template_id), None) or ""),
        }
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        if scenario is not None:
            query += "&scenario=" + urllib.parse.quote(json.dumps(scenario))
        return call(f"/work-ticket/prefill?{query}", token)["data"]

    distribution: dict[str, dict[str, int]] = {}
    seen_templates: set[str] = set()
    for tpl in templates:
        key = f"{tpl['code']}/{tpl['level'] or '-'}"
        if key in seen_templates:
            continue
        seen_templates.add(key)
        payload = prefill(tpl["id"])
        counts = {"unknown": 0, "applicable": 0, "not_applicable": 0}
        for item in payload.get("measures_suggestions", []):
            counts[item["suggest"]] = counts.get(item["suggest"], 0) + 1
        counts["measures"] = len(tpl["measures"])
        distribution[key] = counts

    # 关键对照：受限空间票显式声明「不在罐区」，建议是否变化
    space = next(t for t in templates if t["code"] == "YXKJ")
    plain = prefill(space["id"])
    with_scenario = prefill(space["id"], {"in_tank_area": False, "internal_work": True})

    def dist(payload: dict) -> dict[str, int]:
        out = {"unknown": 0, "applicable": 0, "not_applicable": 0}
        for item in payload.get("measures_suggestions", []):
            out[item["suggest"]] = out.get(item["suggest"], 0) + 1
        return out

    checks = {
        "yxkj_scenario_changes_nothing": dist(plain) == dist(with_scenario),
    }
    evidence = {
        "suggestion_distribution_by_type": distribution,
        "yxkj_plain": dist(plain),
        "yxkj_with_scenario": dist(with_scenario),
        "checks": checks,
    }
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
