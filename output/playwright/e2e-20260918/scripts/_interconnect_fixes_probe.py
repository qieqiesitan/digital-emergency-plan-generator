"""D-1/D-2/D-3/D-4 修复的真实端到端验证（真后端 + 真库）。

一个探针覆盖四件事，全部走真实 API：
  D-4 平面图双向同步：企业档案改图 → 默认楼层跟随（含清空）
  D-1 统计口径：新建的风险事件必须让 risk_events_count / risk_sources_count / 仪表盘口径一致，
      且导出质检的 has_risk 认新五层（资源全 0 时要报 E3 告警）
  D-3 章节待更新：删除风险事件（不更新任何行时间戳）后，依赖它的章节必须出现 stale_domains
  D-2 危化品派生：台账新增后企业档案文本自动变成派生摘要
结束清理：所有探针数据删除并回读核验。
"""

import json
import os
import subprocess
import urllib.error
import urllib.request
from uuid import uuid4

API = "http://localhost:8000/api/v1"
DB = ["docker", "exec", "emergency-plan-db", "psql", "-U", "postgres", "-d", "emergency_plan",
      "-t", "-A", "-q", "-c"]
U, P = "qa_e2e_test@test.com", "test123456"
ENT = "10e11995-e682-405a-9035-fbde13cca213"
PLAN = "6792266d-cd5f-41fc-b591-648fcb64b435"
FLOOR_NAME = "探针默认总图"
PROBE_CATEGORY = "探针类应急物资"   # 必须用企业里不存在的类别，否则同类里有数量>0的资源不会触发 E3

results = []


def sql(statement: str) -> str:
    out = subprocess.run(DB + [statement], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=True)
    for line in out.stdout.splitlines():
        line = line.strip()
        if line and not line.startswith(("INSERT", "DELETE", "UPDATE")):
            return line
    return ""


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"raw": raw[:200].decode("utf-8", "replace")}


def check(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:220]})
    print(("PASS " if ok else "FAIL ") + name + (f"  | {detail}" if detail else ""))


def main():
    floor_id = zone_id = object_id = unit_id = event_id = None
    resource_id = chemical_id = None
    section_key = org_key = None
    created_org = False   # 仅当探针自己建了应急组织时才在清理阶段清空
    original_plan_url = None
    original_text = None
    try:
        _, pr = call("POST", "/auth/login", body={"email": U, "password": P})
        token = pr["data"]["access_token"]
        original_plan_url = sql(f"select coalesce(floor_plan_url,'') from enterprises where id='{ENT}';")
        original_text = sql(f"select coalesce(hazardous_chemicals,'') from enterprises where id='{ENT}';")

        # ---------- D-4 平面图双向同步（直接针对既有的默认楼层，不新建楼层） ----------
        st, r = call("GET", f"/enterprises/{ENT}/risk-management/floors", token)
        floors = r.get("data") or []
        default_floor = next((f for f in floors if f.get("is_default")), None)
        floor_id = default_floor.get("id") if default_floor else None
        check("D-4 前置：企业有默认楼层", bool(floor_id), f"floors={len(floors)}")
        original_floor_url = sql(
            f"select coalesce(floor_plan_url,'') from enterprise_floors where id='{floor_id}';")

        new_url = f"/uploads/enterprises/{ENT}/floors/probe/probe.png"
        st, r = call("PUT", f"/enterprises/{ENT}", token, {"floor_plan_url": new_url})
        check("D-4 企业档案改图", st == 200, f"status={st}")
        floor_url = sql(
            f"select coalesce(floor_plan_url,'') from enterprise_floors where id='{floor_id}';")
        check("D-4 默认楼层跟随企业档案改图", floor_url == new_url, f"floor={floor_url}")

        st, r = call("PUT", f"/enterprises/{ENT}", token, {"floor_plan_url": None})
        floor_url = sql(
            f"select coalesce(floor_plan_url,'') from enterprise_floors where id='{floor_id}';")
        check("D-4 清空企业平面图也同步到楼层", st == 200 and floor_url == "", f"floor='{floor_url}'")

        # ---------- D-1 + D-3 风险数据与统计口径 ----------
        st, r = call("POST", f"/enterprises/{ENT}/risk-management/zones",
                     token, {"floor_id": floor_id, "name": "探针分区"})
        zone_id = r.get("data", {}).get("id")
        check("D-1 前置：建风险分区", st in (200, 201) and zone_id, f"status={st}")
        st, r = call("POST", f"/enterprises/{ENT}/risk-management/objects",
                     token, {"zone_id": zone_id, "name": "探针对象"})
        object_id = r.get("data", {}).get("id")
        st, r = call("POST", f"/enterprises/{ENT}/risk-management/objects/{object_id}/units",
                     token, {"name": "探针单元"})
        unit_id = r.get("data", {}).get("id")
        st, r = call("POST", f"/enterprises/{ENT}/risk-management/units/{unit_id}/events",
                     token, {"accident_type": "火灾", "risk_level": "一般"})
        event_id = r.get("data", {}).get("id")
        check("D-1 前置：建风险事件", st in (200, 201) and event_id, f"status={st}")

        legacy = sql(f"select count(*) from risk_sources where enterprise_id='{ENT}';")
        st, r = call("GET", f"/enterprises/{ENT}", token)
        data = r.get("data", {})
        check("D-1 企业详情：risk_sources_count 走新五层",
              st == 200 and data.get("risk_events_count") == 1 and data.get("risk_sources_count") == 1,
              f"旧表={legacy} events={data.get('risk_events_count')} sources={data.get('risk_sources_count')}")
        st, r = call("GET", "/dashboard", token)
        stats = r.get("data", {}).get("stats", {})
        check("D-1 仪表盘：risk_source_count 与新口径一致",
              st == 200 and stats.get("risk_source_count") == stats.get("risk_event_count") >= 1,
              f"sources={stats.get('risk_source_count')} events={stats.get('risk_event_count')}")

        # D-1b：导出质检 has_risk 必须认新五层
        st, r = call("POST", f"/enterprises/{ENT}/resources",
                     token, {"category": PROBE_CATEGORY, "name": "探针灭火器", "quantity": 0})
        resource_id = r.get("data", {}).get("id")
        st, r = call("POST", f"/plans/{PLAN}/export/validate", token)
        warnings = [w.get("warning", "") for w in (r.get("data", {}).get("warnings") or [])]
        check("D-1 导出质检对「只有新五层风险数据」的企业仍触发 E3 告警",
              st == 200 and any(f"{PROBE_CATEGORY}应急资源数量均为 0" in w for w in warnings),
              f"status={st} warnings={warnings[:3]}")

        # D-3：章节依赖变更 → 待更新标记
        st, r = call("GET", f"/plans/{PLAN}/sections", token)
        sections = r.get("data") or []
        target = next((s for s in sections if "risk_sources" in (s.get("data_dependencies") or [])), None)
        section_key = target.get("section_key") if target else None
        check("D-3 前置：预案有依赖 risk_sources 的章节", bool(section_key), f"key={section_key}")
        st, r = call("PUT", f"/plans/{PLAN}/sections/{section_key}", token, {"content": "探针正文（依赖风险数据）"})
        check("D-3 写入章节正文", st == 200, f"status={st}")
        st, r = call("GET", f"/plans/{PLAN}/sections", token)
        cur = next((s for s in (r.get("data") or []) if s.get("section_key") == section_key), {})
        check("D-3 正文比风险数据新 → 不标记待更新", cur.get("stale_domains") == [],
              f"stale={cur.get('stale_domains')}")

        st, r = call("DELETE", f"/enterprises/{ENT}/risk-management/events/{event_id}", token)
        check("D-3 删除风险事件（API）", st == 200, f"status={st}")
        event_id = None   # 已删
        st, r = call("GET", f"/plans/{PLAN}/sections", token)
        cur = next((s for s in (r.get("data") or []) if s.get("section_key") == section_key), {})
        check("D-3 删除后章节标记待更新（打点生效）",
              cur.get("stale_domains") == ["risk_sources"], f"stale={cur.get('stale_domains')}")

        # ---------- D-3 信号精度：组织域不该被"企业记录更新"误触发 ----------
        org_target = next((s for s in (r.get("data") or [])
                           if "org_structure" in (s.get("data_dependencies") or [])), None)
        org_key = org_target.get("section_key") if org_target else None
        check("D-3 前置：预案有依赖 org_structure 的章节", bool(org_key), f"key={org_key}")
        if org_key:
            call("PUT", f"/plans/{PLAN}/sections/{org_key}", token, {"content": "探针组织章节正文"})
            st, r = call("GET", f"/plans/{PLAN}/sections", token)
            cur = next((s for s in (r.get("data") or []) if s.get("section_key") == org_key), {})
            check("D-3 组织章节刚写完 → 不标记", cur.get("stale_domains") == [],
                  f"stale={cur.get('stale_domains')}")
            # 改企业名（企业记录会被刷新）：组织域不应因此被标脏
            ent_name = sql(f"select name from enterprises where id='{ENT}';")
            call("PUT", f"/enterprises/{ENT}", token, {"fax": "029-probe"})
            st, r = call("GET", f"/plans/{PLAN}/sections", token)
            cur = next((s for s in (r.get("data") or []) if s.get("section_key") == org_key), {})
            check("D-3 仅编辑企业记录 → 组织章节不误报待更新",
                  cur.get("stale_domains") == [], f"name={ent_name} stale={cur.get('stale_domains')}")
            # 真正保存应急组织（整树覆盖）：应当标记
            st, r = call("GET", f"/enterprises/{ENT}/emergency-org", token)
            units = r.get("data") or []
            if not units:
                # 该企业尚未配置应急组织：探针临时建一份最小树（结束时清空还原）
                st, r = call("PUT", f"/enterprises/{ENT}/emergency-org", token,
                             {"units": [{"id": str(uuid4()), "name": "探针应急指挥部",
                                         "roles": [{"id": str(uuid4()), "name": "探针总指挥",
                                                    "is_required": True, "member_ids": []}]}]})
                created_org = st == 200
                check("D-3 前置：临时建应急组织", created_org, f"status={st} {str(r)[:80]}")
                st, r = call("GET", f"/enterprises/{ENT}/emergency-org", token)
                units = r.get("data") or []
            if units:
                call("PUT", f"/enterprises/{ENT}/emergency-org", token,
                     {"units": [{"id": u.get("id"), "name": u.get("name"), "duties": u.get("duties"),
                                 "sort_order": u.get("sort_order", 0),
                                 "roles": [{"id": ro.get("id"), "name": ro.get("name"),
                                            "duties": ro.get("duties"), "is_required": ro.get("is_required", False),
                                            "sort_order": ro.get("sort_order", 0),
                                            "member_ids": ro.get("member_ids") or []}
                                           for ro in (u.get("roles") or [])]}
                                for u in units]})
                st, r = call("GET", f"/plans/{PLAN}/sections", token)
                cur = next((s for s in (r.get("data") or []) if s.get("section_key") == org_key), {})
                check("D-3 保存应急组织后组织章节标记待更新",
                      cur.get("stale_domains") == ["org_structure"], f"stale={cur.get('stale_domains')}")
            else:
                check("D-3 保存应急组织后组织章节标记待更新", False, "该企业应急组织为空，跳过")

        # ---------- D-2 危化品派生 ----------
        st, r = call("POST", f"/enterprises/{ENT}/chemicals",
                     token, {"name": "探针乙醇", "cas_no": "64-17-5",
                             "storage_amount": 5, "storage_unit": "t"})
        chemical_id = r.get("data", {}).get("id")
        check("D-2 前置：新建台账条目", st in (200, 201) and chemical_id, f"status={st}")
        text = sql(f"select coalesce(hazardous_chemicals,'') from enterprises where id='{ENT}';")
        check("D-2 档案文本自动变成台账派生摘要",
              text.startswith("共 1 种") and "探针乙醇" in text and "CAS 64-17-5" in text,
              f"text={text[:60]}")

    finally:
        # ---------- 清理 ----------
        if chemical_id:
            call("DELETE", f"/enterprises/{ENT}/chemicals/{chemical_id}", token)
        if resource_id:
            call("DELETE", f"/enterprises/{ENT}/resources/{resource_id}", token)
        if section_key:
            call("PUT", f"/plans/{PLAN}/sections/{section_key}", token, {"content": ""})
        if org_key:
            call("PUT", f"/plans/{PLAN}/sections/{org_key}", token, {"content": ""})
        # 仅当探针自己建过应急组织时才清空还原（避免误删真实组织树）
        if created_org:
            call("PUT", f"/enterprises/{ENT}/emergency-org", token, {"units": []})
        if event_id:
            call("DELETE", f"/enterprises/{ENT}/risk-management/events/{event_id}", token)
        if zone_id:
            call("DELETE", f"/enterprises/{ENT}/risk-management/zones/{zone_id}", token)
        # 档案字段还原（探针改过平面图与危化品文本）：平面图还原会经同步写回默认楼层
        call("PUT", f"/enterprises/{ENT}", token,
             {"floor_plan_url": original_plan_url or None, "hazardous_chemicals": original_text})
        call("PUT", f"/enterprises/{ENT}", token, {"floor_plan_url": original_floor_url or None})
        leftover = sql(
            "select (select count(*) from enterprise_floors where name='" + FLOOR_NAME + "')"
            " || '/' || (select count(*) from hazardous_chemicals where name='探针乙醇')"
            " || '/' || (select count(*) from emergency_resources where name='探针灭火器')"
            " || '/' || (select count(*) from risk_zones where name='探针分区');")
        print("清理后残留（楼层/危化品/资源/分区）:", leftover)
        with open(os.path.join("backend/exports/e2e-20260918",
                               "summary-interconnect-fixes.json"), "w", encoding="utf-8") as fh:
            json.dump({"results": results,
                       "passed": sum(1 for r in results if r["ok"]),
                       "total": len(results), "leftover": leftover}, fh,
                      ensure_ascii=False, indent=2)
    fails = [r["name"] for r in results if not r["ok"]]
    print(f"\n=== {len(results) - len(fails)}/{len(results)} PASS ===")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
