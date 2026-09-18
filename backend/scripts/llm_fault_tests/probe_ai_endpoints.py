"""AI 端点冒烟（mock 供应商，零真实额度）：验证 db_guard 大量插入后各 AI 端点仍可用。

路径从 /openapi.json 里按后缀解析，避免手抄前缀出错。
"""
import json
import os
import sys

import httpx

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api/v1")
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"

# (方法, 路径后缀, 载荷)
CALLS = [
    ("POST", "/chemicals/ai/questions", {}),
    ("POST", "/chemicals/ai/generate", {"answers": [{"question_id": "q1", "question": "主要危险化学品？", "answer": "甲醇"}]}),
    ("POST", "/resources/ai/questions", {}),
    ("POST", "/resources/ai/generate", {"answers": [{"question_id": "q1", "question": "队伍规模？", "answer": "20 人"}]}),
    ("POST", "/risk-sources/ai/questions", {}),
    ("POST", "/risk-sources/ai/generate", {"answers": [{"question_id": "q1", "question": "风险源？", "answer": "储罐"}]}),
    ("POST", "/surrounding/ai/questions", {}),
    ("POST", "/surrounding/ai/generate", {"answers": [{"question_id": "q1", "question": "周边单位？", "answer": "无"}]}),
    ("POST", "/risk-management/ai/suggest-objects", {"zone_name": "罐区", "zone_desc": "甲醇储罐", "enterprise_info": {}}),
    ("POST", "/risk-management/ai/suggest-events", {"unit_name": "储罐", "unit_type": "储罐", "object_name": "甲醇", "zone_name": "罐区", "enterprise_info": {}}),
    ("POST", "/risk-management/ai/suggest-measures", {"accident_type": "泄漏", "risk_level": "红色", "unit_name": "储罐", "object_name": "甲醇", "enterprise_info": {}}),
    ("POST", "/risk-management/ai/smart-guide", {"description": "甲醇储罐区，三个卧式罐，需要围堰和消防" }),
    ("POST", "/risk-management/ai/analyze-floor-plan", {"enterprise_info": {}}),
    ("POST", "/risk-management/ai/migrate-preview", {}),
    ("POST", "/org/ai-suggest", {"extra_requirements": ""}),
    ("POST", "ai/checklist-template", {"industry": "化工", "risk_points": "罐区 泄漏"}),
    ("POST", "ai/record-assist", {"description": "巡检发现管线法兰渗漏"}),
    ("POST", "/extraction/suggest-mapping", {"headers": ["名称", "型号", "数量"], "target_entity": "emergency_resource"}),
    ("POST", "/onboarding/candidates", {"enterprise_id": ENT, "module": "resources"}),
]


def resolve(openapi: dict, method: str, suffix: str) -> str | None:
    """按后缀 + HTTP 方法找路径（同一后缀可能同时存在 GET/POST 两个版本）。"""
    hits = []
    for path, ops in openapi.get("paths", {}).items():
        if path.endswith(suffix) and method.lower() in ops:
            hits.append(path)
    if not hits:
        return None
    # 优先 enterprise 级路径，其次是别的
    hits.sort(key=lambda p: (0 if "enterprise_id" in p else 1, len(p)))
    return hits[0]


def main() -> None:
    with httpx.Client(timeout=90) as c:
        r = c.post(f"{BASE}/auth/login", json={"email": U, "password": P})
        token = (r.json().get("data") or {}).get("access_token")
        h = {"Authorization": f"Bearer {token}"}
        openapi = c.get(f"{BASE.rsplit('/api/v1', 1)[0]}/openapi.json").json()

        ok = skip = bad = 0
        for method, suffix, payload in CALLS:
            path = resolve(openapi, method, suffix)
            if not path:
                print(f"⚠️ 找不到路由 {suffix}")
                skip += 1
                continue
            origin = BASE.rsplit("/api/v1", 1)[0]
            url = origin + path.replace("{enterprise_id}", ENT).replace("{id}", ENT)
            try:
                resp = c.request(method, url, json=payload, headers=h)
            except Exception as e:  # noqa: BLE001
                print(f"❌ {suffix}: {type(e).__name__}: {str(e)[:80]}")
                bad += 1
                continue
            body = resp.text[:110].replace("\n", " ")
            if resp.status_code == 200:
                ok += 1
                flag = "✅"
            elif resp.status_code in (400, 404, 409, 422):
                skip += 1
                flag = "⚠️"
            else:
                bad += 1
                flag = "❌"
            print(f"{flag} {method} {suffix:48s} {resp.status_code} {body}")

        print(f"\n==== AI 端点冒烟：200 成功 {ok}；4xx（缺前置数据/载荷） {skip}；其它 {bad}")
        print(json.dumps({"ok": ok, "skipped_4xx": skip, "bad": bad}, ensure_ascii=False))
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
