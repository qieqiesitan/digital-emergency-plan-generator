"""查报告单章 400 的原因 + 抽检批量生成质量。"""
import json

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"

with httpx.Client(timeout=120) as c:
    token = (c.post(f"{BASE}/auth/login", json={"email": "qa_e2e_test@test.com",
                                                "password": "test123456"}).json()
             .get("data") or {}).get("access_token")
    h = {"Authorization": f"Bearer {token}"}

    r = c.post(f"{BASE}/enterprises/{ENT}/risk-assessment/generate/section", headers=h,
               json={"chapter_key": "ch1_hazard_id"})
    print("报告单章：HTTP", r.status_code)
    print(r.text[:400])

    # 报告草稿现状
    r2 = c.get(f"{BASE}/enterprises/{ENT}/risk-assessment", headers=h)
    body = r2.json().get("data") or {}
    chapters = (body.get("summary") or {}).get("chapters") or {}
    print(f"\n报告草稿：HTTP {r2.status_code} 章节数={len(chapters)} "
          f"键={list(chapters)[:6]}")

    # 抽检批量生成结果
    r3 = c.get(f"{BASE}/plans/{PLAN}", headers=h)
    plan = r3.json().get("data") or {}
    secs = plan.get("sections") or []
    filled = [s for s in secs if (s.get("content") or "").strip()]
    print(f"\n预案章节：共 {len(secs)}，有正文 {len(filled)}")
    for s in plan.get("sections", [])[:3]:
        content = s.get("content") or ""
        print(f"   - {s.get('section_key')} {s.get('title')}: {len(content)} 字 "
              f"ai_generated={s.get('ai_generated')}")
        print(f"     开头：{content[:150].replace(chr(10),' ')}")
    total = sum(len(s.get("content") or "") for s in secs)
    print(f"   全部章节正文合计 {total} 字")
