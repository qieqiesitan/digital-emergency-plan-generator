"""AI 自动填充结果的字段类型体检（真接口，只读）。

背景（2026-09-23 用户实测）：新建企业提交时报 `industry：Input should be a valid string`。
前端 industry 是普通文本输入框，用户手打不会产生非字符串 —— 嫌疑集中在
「AI 自动填充」把非字符串值写进表单，提交时原样发给后端。

本探针把 AI 填充返回的每个字段与后端 schema 的期望类型对比，列出不符合的字段。

用法（仓库根目录）：
    python output/playwright/e2e-20260923/scripts/_enterprise_autofill_types_probe.py
证据输出：同目录 enterprise-autofill-types.json
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "http://localhost:8000/api/v1"
USER = ("qa_e2e_test@test.com", "test123456")
EVIDENCE = Path(__file__).resolve().parent / "enterprise-autofill-types.json"

# 后端 EnterpriseBase 的期望类型（字符串字段一旦不是 str 就会 422）
STRING_FIELDS = {
    "name", "address", "industry", "business_scope", "credit_code",
    "legal_representative", "economic_type", "established_date", "phone", "fax",
    "postal_code", "safety_officer", "safety_officer_phone", "safety_standardization",
    "fire_approval", "fire_approval_date", "last_plan_filing_date",
    "last_plan_filing_authority", "main_products", "annual_capacity",
    "hazardous_chemicals", "special_equipment", "building_overview", "floor_plan_url",
}
NUMBER_FIELDS = {
    "employee_count", "registered_capital", "land_area", "building_area",
    "safety_staff_count", "gis_lat", "gis_lng",
}

COMPANIES = ["西安宝岳空间科技", "西安宝岳空间科技有限公司", "延长壳牌石油有限公司（西安明光路加油站）"]


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
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def bad_fields(payload: dict) -> list[dict]:
    """找出类型与 schema 不符的字段。"""
    problems: list[dict] = []
    for key, value in payload.items():
        if key in STRING_FIELDS:
            if value is not None and not isinstance(value, str):
                problems.append({"field": key, "expected": "str", "actual": type(value).__name__, "value": str(value)[:80]})
        elif key in NUMBER_FIELDS:
            if value is not None and not isinstance(value, (int, float)):
                problems.append({"field": key, "expected": "int/float", "actual": type(value).__name__, "value": str(value)[:80]})
    return problems


def main() -> int:
    token = call("POST", "/auth/login", {"email": USER[0], "password": USER[1]})[1]["data"][
        "access_token"
    ]
    report: dict = {"companies": [], "all_clean": True}
    for name in COMPANIES:
        status, body = call("POST", "/enterprises/autofill", {"name": name}, token)
        data = body.get("data") or {}
        # 前端使用的是 data.fields（嵌套），不是 data 顶层——这里必须查对层级
        payload = data.get("fields") or {}
        problems = bad_fields(payload) if status == 200 else []
        entry = {
            "company": name,
            "status": status,
            "field_count": len(payload),
            "industry_value": payload.get("industry"),
            "industry_type": type(payload.get("industry")).__name__,
            "keys": sorted(payload.keys()),
            "problems": problems,
        }
        report["companies"].append(entry)
        if problems:
            report["all_clean"] = False

    EVIDENCE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for entry in report["companies"]:
        print(f"{entry['company']}: status={entry['status']} industry={entry['industry_type']}:{entry['industry_value']}")
        for problem in entry["problems"]:
            print("   类型不符:", problem)
    print("全部字段类型正常:", report["all_clean"])
    return 0 if report["all_clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
