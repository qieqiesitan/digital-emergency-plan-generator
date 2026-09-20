"""作业票模板接口实测：开票页拿到的措施条数必须是修复后的 16/15。

前端第 4 步直接渲染 `GET /work-ticket/templates` 返回的 measures，
因此这里从接口层验证"用户打开动火票看到的就是 16 条"。
只读，不建票、不写库。

用法（仓库根目录）：
    python output/playwright/e2e-20260920/scripts/_work_ticket_templates_api_probe.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

API = "http://localhost:8000/api/v1"
USER = ("qa_e2e_test@test.com", "test123456")
EVIDENCE = Path(__file__).resolve().parent / "work-ticket-templates-api.json"
EXPECTED = {"DHZY": 16, "YXKJ": 15}


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

    seen: dict[str, list[int]] = {}
    for tpl in templates:
        if tpl["code"] in EXPECTED:
            seen.setdefault(tpl["code"], []).append(len(tpl["measures"]))

    checks = {
        "dhzy_all_levels_16": seen.get("DHZY") == [16, 16, 16],
        "yxkj_15": seen.get("YXKJ") == [15],
        "dhzy_last_measure_is_placeholder": next(
            (
                tpl["measures"][-1]["measure_text"].startswith("其他安全措施")
                for tpl in templates
                if tpl["code"] == "DHZY"
            ),
            False,
        ),
        "no_foreign_measure_leaked": not any(
            "放坡" in m["measure_text"] or "警示灯" in m["measure_text"]
            for tpl in templates
            if tpl["code"] == "DHZY"
            for m in tpl["measures"]
        ),
    }
    EVIDENCE.write_text(
        json.dumps(
            {"measures_per_ticket": seen, "checks": checks, "all_passed": all(checks.values())},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
