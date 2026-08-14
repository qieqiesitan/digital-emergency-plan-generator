"""隐患排查治理任务 3 测试：排查计划 CRUD / 任务生成 / 清单项提交 / 一键转隐患。

测试风格与 tests/test_enterprise_org.py 一致：无 db fixture，服务/端点用
FastAPI TestClient + dependency_overrides + SQL 文本分发 mock；async 服务函数
用 @pytest.mark.asyncio。

覆盖：
- 计划创建：字段校验（category/frequency/weekdays）/ zone_ids 企业归属 /
  责任人启用成员校验 / 模板（系统或本企业）校验 / 写权限（企业主或管理员成员）
- 计划 CRUD 主路径：列表（enabled 过滤 SQL）/ 详情 / 404 / 更新 / 软删
- 任务生成：daily/weekly/custom/monthly 频次、防重、items 来自风险点+措施+模板
- 清单项提交：合法/非法 result、非责任人 403、全部核对 done / 部分 processing
- to-record：预填字段 / code 生成 / source 回填 / 仅 abnormal 可转
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.hazard_management import (
    HazardChecklistTemplate,
    HazardInspectionItem,
    HazardInspectionPlan,
    HazardInspectionTask,
    HazardRecord,
)
from app.models.risk_management import RiskEvent, RiskMeasure, RiskObject
from app.models.user import User
from app.routers import hazard_management
from app.services.hazard_service import generate_tasks_for_plan, next_hazard_code


# ── mock 工具 ──

def _scalar(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _scalars(values):
    res = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = list(values)
    res.scalars.return_value = scalars_mock
    return res


def _first(value):
    res = MagicMock()
    res.first.return_value = value
    return res


def _count(value):
    res = MagicMock()
    res.scalar.return_value = value
    return res


def _ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司", hazard_closure_mode="standard")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _plan(**kw):
    p = HazardInspectionPlan(
        id=kw.pop("id", "p1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        name=kw.pop("name", "生产车间日排查"),
        category=kw.pop("category", "daily"),
        frequency=kw.pop("frequency", "daily"),
        weekdays=kw.pop("weekdays", None),
        zone_ids=kw.pop("zone_ids", ["z1", "z2"]),
        template_id=kw.pop("template_id", None),
        responsible_user_id=kw.pop("responsible_user_id", "u1"),
        ai_suggestion=kw.pop("ai_suggestion", None),
        enabled=kw.pop("enabled", True),
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def _task(**kw):
    t = HazardInspectionTask(
        id=kw.pop("id", "t1"),
        plan_id=kw.pop("plan_id", "p1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        title=kw.pop("title", "生产车间日排查 · 08-15"),
        status=kw.pop("status", "pending"),
        responsible_user_id=kw.pop("responsible_user_id", "u1"),
        due_at=kw.pop("due_at", datetime(2026, 8, 15, 18, 0)),
        completed_at=kw.pop("completed_at", None),
        overdue_notified_at=kw.pop("overdue_notified_at", None),
    )
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def _item(**kw):
    i = HazardInspectionItem(
        id=kw.pop("id", "i1"),
        task_id=kw.pop("task_id", "t1"),
        object_id=kw.pop("object_id", "o1"),
        measure_id=kw.pop("measure_id", None),
        content=kw.pop("content", "检查配电箱"),
        expected_note=kw.pop("expected_note", None),
        result=kw.pop("result", "pending"),
        remark=kw.pop("remark", None),
        photo_urls=kw.pop("photo_urls", []),
    )
    for k, v in kw.items():
        setattr(i, k, v)
    return i


def _hazard_db(ent, *, member=None, admin_member=None, zones=None, plans=None, plan=None,
               tasks=None, task=None, items=None, item=None, dedupe_hit=None,
               template=None, objects=None, events=None, measures=None,
               remaining_pending=0, record_count=0):
    """按 SQL 文本特征分发（参照 tests/test_enterprise_org.py 的 _org_db）。"""
    db = AsyncMock()
    db.added = []

    def fake_add(obj):
        if isinstance(obj, HazardInspectionPlan) and not getattr(obj, "id", None):
            obj.id = "p1"
        elif isinstance(obj, HazardInspectionTask) and not getattr(obj, "id", None):
            obj.id = "t1"
        elif isinstance(obj, HazardInspectionItem) and not getattr(obj, "id", None):
            obj.id = f"ni{len([x for x in db.added if isinstance(x, HazardInspectionItem)]) + 1}"
        elif isinstance(obj, HazardRecord) and not getattr(obj, "id", None):
            obj.id = "r1"
        db.added.append(obj)

    db.add = MagicMock(side_effect=fake_add)

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(ent)
        if "FROM enterprise_members" in text:
            if "enterprise_members.role" in text:
                return _first(admin_member if admin_member and getattr(admin_member, "enabled", True) else None)
            return _first(member if member and getattr(member, "enabled", True) else None)
        if "FROM risk_zones" in text:
            return _scalars(zones or [])
        if "FROM risk_objects" in text:
            return _scalars(objects or [])
        if "FROM risk_events" in text:
            return _scalars(events or [])
        if "FROM risk_measures" in text:
            return _scalars(measures or [])
        if "FROM hazard_checklist_templates" in text:
            return _scalar(template)
        if "FROM hazard_inspection_plans" in text:
            if "hazard_inspection_plans.id =" in text:
                return _scalar(plan)
            return _scalars(plans or [])
        if "FROM hazard_inspection_tasks" in text:
            if "hazard_inspection_tasks.plan_id =" in text:
                return _first(dedupe_hit)
            if "hazard_inspection_tasks.id =" in text:
                return _scalar(task)
            return _scalars(tasks or [])
        if "FROM hazard_inspection_items" in text:
            if "hazard_inspection_items.id IN" in text:
                return _scalars(items or [])
            if "hazard_inspection_items.id =" in text:
                return _scalar(item)
            if "count(hazard_inspection_items.id)" in text:
                return _count(remaining_pending)
            return _scalars(items or [])
        if "FROM hazard_records" in text:
            return _count(record_count)
        return _scalar(None)

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(hazard_management.router)

    def _override_user():
        return User(id="u1", email="a@b.c", name="A", role="user")

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _hazard_db(_ent())
    with TestClient(app) as test_client:
        yield test_client


_PLAN_BODY = {
    "name": "生产车间日排查",
    "category": "daily",
    "frequency": "daily",
    "zone_ids": ["z1", "z2"],
    "responsible_user_id": "u2",
}


# ── 计划创建：字段 / 归属 / 责任人 / 模板 / 权限校验 ──

def test_plan_create_success(client):
    ent = _ent()
    db = _hazard_db(ent, zones=["z1", "z2"], member=MagicMock())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=_PLAN_BODY)
    assert resp.status_code == 201
    assert resp.json()["code"] == 0
    data = resp.json()["data"]
    assert data["name"] == "生产车间日排查"
    assert data["enabled"] is True
    assert data["zone_ids"] == ["z1", "z2"]
    added = db.added[0]
    assert isinstance(added, HazardInspectionPlan)
    assert added.enterprise_id == "e1"
    assert added.responsible_user_id == "u2"
    db.commit.assert_awaited()


def test_plan_create_rejects_invalid_category(client):
    db = _hazard_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "category": "boss"}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    assert "category 非法" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_plan_create_rejects_invalid_frequency(client):
    db = _hazard_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "frequency": "hourly"}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    assert "frequency 非法" in resp.json()["detail"]


def test_plan_create_rejects_weekly_without_weekdays(client):
    db = _hazard_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "frequency": "weekly"}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    assert "weekdays 必填" in resp.json()["detail"]


def test_plan_create_accepts_weekly_with_weekdays(client):
    db = _hazard_db(_ent(), zones=["z1"], member=MagicMock())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "frequency": "weekly", "weekdays": [0, 2], "zone_ids": ["z1"]}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 201
    assert resp.json()["data"]["frequency"] == "weekly"
    assert resp.json()["data"]["weekdays"] == [0, 2]


def test_plan_create_rejects_empty_zone_ids(client):
    db = _hazard_db(_ent())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "zone_ids": []}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    assert "zone_ids 不能为空" in resp.json()["detail"]


def test_plan_create_rejects_zone_not_in_enterprise(client):
    db = _hazard_db(_ent(), zones=[])
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "zone_ids": ["z1"]}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "分区不属于该企业" in detail
    assert "z1" in detail
    db.commit.assert_not_awaited()


def test_plan_create_rejects_responsible_not_member(client):
    db = _hazard_db(_ent(), zones=["z1"], member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "zone_ids": ["z1"]}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    assert "责任人必须是该企业的启用成员" in resp.json()["detail"]


def test_plan_create_rejects_disabled_responsible_member(client):
    disabled = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u2", enabled=False)
    db = _hazard_db(_ent(), zones=["z1"], member=disabled)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "zone_ids": ["z1"]}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    assert "责任人必须是该企业的启用成员" in resp.json()["detail"]


def test_plan_create_rejects_missing_template(client):
    db = _hazard_db(_ent(), zones=["z1"], member=MagicMock(), template=None)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "zone_ids": ["z1"], "template_id": "tpl9"}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    assert "检查表模板不存在" in resp.json()["detail"]


def test_plan_create_rejects_foreign_template(client):
    template = HazardChecklistTemplate(id="tpl9", enterprise_id="e9", name="他企业模板", category="daily")
    db = _hazard_db(_ent(), zones=["z1"], member=MagicMock(), template=template)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "zone_ids": ["z1"], "template_id": "tpl9"}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 422
    assert "检查表模板不属于该企业" in resp.json()["detail"]


def test_plan_create_accepts_system_template(client):
    template = HazardChecklistTemplate(id="tpl1", enterprise_id=None, name="日常检查表", category="daily")
    db = _hazard_db(_ent(), zones=["z1"], member=MagicMock(), template=template)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "zone_ids": ["z1"], "template_id": "tpl1"}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 201
    assert resp.json()["data"]["template_id"] == "tpl1"


def test_plan_create_non_admin_writer_403(client):
    ent = _ent(user_id="u2")
    db = _hazard_db(ent, admin_member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=_PLAN_BODY)
    assert resp.status_code == 403
    db.commit.assert_not_awaited()


def test_plan_create_admin_member_allowed(client):
    ent = _ent(user_id="u2")
    db = _hazard_db(ent, zones=["z1"], member=MagicMock(), admin_member=MagicMock())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {**_PLAN_BODY, "zone_ids": ["z1"]}
    resp = client.post("/enterprises/e1/hazard-inspection/plans", json=body)
    assert resp.status_code == 201
    assert resp.json()["data"]["name"] == "生产车间日排查"


# ── 计划列表 / 详情 ──

def test_plan_list_returns_plans(client):
    db = _hazard_db(_ent(), plans=[_plan(), _plan(id="p2", name="综合检查")])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/plans")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert data[0]["name"] == "生产车间日排查"


def test_plan_list_applies_enabled_filter(client):
    db = _hazard_db(_ent(), plans=[_plan()])
    captured = []
    orig = db.execute.side_effect
    def spy(stmt, *params):
        captured.append(str(stmt))
        return orig(stmt, *params)
    db.execute.side_effect = spy
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/plans?enabled=true")
    assert resp.status_code == 200
    assert any("enabled IS true" in s for s in captured)


def test_plan_get_detail(client):
    db = _hazard_db(_ent(), plan=_plan())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/plans/p1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "p1"
    assert data["name"] == "生产车间日排查"


def test_plan_get_not_found_404(client):
    db = _hazard_db(_ent(), plan=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/plans/p1")
    assert resp.status_code == 404
    assert "排查计划不存在" in resp.json()["detail"]


def test_plan_read_non_member_404(client):
    ent = _ent(user_id="u2")
    db = _hazard_db(ent, member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/plans")
    assert resp.status_code == 404


# ── 计划更新 / 删除 ──

def test_plan_update_name(client):
    plan = _plan()
    db = _hazard_db(_ent(), plan=plan)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/plans/p1", json={"name": "新计划"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "新计划"
    assert plan.name == "新计划"
    db.commit.assert_awaited()


def test_plan_update_revalidates_zone_ownership(client):
    db = _hazard_db(_ent(), plan=_plan(), zones=[])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/plans/p1", json={"zone_ids": ["z9"]})
    assert resp.status_code == 422
    assert "分区不属于该企业" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_plan_update_weekly_requires_weekdays_effective(client):
    db = _hazard_db(_ent(), plan=_plan(frequency="daily"))
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/plans/p1", json={"frequency": "weekly"})
    assert resp.status_code == 422
    assert "weekdays 必填" in resp.json()["detail"]


def test_plan_update_frequency_with_weekdays_ok(client):
    plan = _plan()
    db = _hazard_db(_ent(), plan=plan)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/plans/p1", json={"frequency": "weekly", "weekdays": [0, 2]})
    assert resp.status_code == 200
    assert plan.frequency == "weekly"
    assert plan.weekdays == [0, 2]


def test_plan_update_responsible_revalidated(client):
    db = _hazard_db(_ent(), plan=_plan(), member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/plans/p1", json={"responsible_user_id": "u9"})
    assert resp.status_code == 422
    assert "责任人必须是该企业的启用成员" in resp.json()["detail"]


def test_plan_delete_soft_disables(client):
    plan = _plan()
    db = _hazard_db(_ent(), plan=plan)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.delete("/enterprises/e1/hazard-inspection/plans/p1")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert plan.enabled is False
    db.commit.assert_awaited()


# ── 任务列表 / 详情 ──

def test_tasks_list_returns_tasks(client):
    db = _hazard_db(_ent(), tasks=[_task(), _task(id="t2", title="综合检查任务")])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/tasks")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert data[0]["id"] == "t1"


def test_tasks_list_responsible_filter_rejects_non_member(client):
    db = _hazard_db(_ent(), member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/tasks", params={"responsible_user_id": "u9"})
    assert resp.status_code == 422
    assert "责任人必须是该企业的启用成员" in resp.json()["detail"]


def test_tasks_list_overdue_filter_applies_sql(client):
    db = _hazard_db(_ent(), tasks=[_task()])
    captured = []
    orig = db.execute.side_effect
    def spy(stmt, *params):
        captured.append(str(stmt))
        return orig(stmt, *params)
    db.execute.side_effect = spy
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/tasks", params={"overdue": "true"})
    assert resp.status_code == 200
    assert any("hazard_inspection_tasks.due_at <" in s for s in captured)
    assert any("hazard_inspection_tasks.status IN" in s for s in captured)


def test_task_detail_includes_items(client):
    db = _hazard_db(_ent(), task=_task(), items=[_item(), _item(id="i2", content="检查灭火器")])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/tasks/t1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == "t1"
    assert len(data["items"]) == 2
    assert data["items"][0]["content"] == "检查配电箱"


def test_task_detail_not_found_404(client):
    db = _hazard_db(_ent(), task=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/tasks/t1")
    assert resp.status_code == 404


# ── 清单项提交 ──

def test_task_submit_all_done(client):
    task = _task(responsible_user_id="u1")
    item = _item()
    db = _hazard_db(_ent(), task=task, items=[item], remaining_pending=0)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"items": [{"item_id": "i1", "result": "normal", "remark": "运行正常"}]}
    resp = client.put("/enterprises/e1/hazard-inspection/tasks/t1", json=body)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "done"
    assert item.result == "normal"
    assert item.remark == "运行正常"
    assert task.completed_at is not None
    db.commit.assert_awaited()


def test_task_submit_partial_processing(client):
    task = _task(responsible_user_id="u1")
    db = _hazard_db(_ent(), task=task, items=[_item()], remaining_pending=1)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"items": [{"item_id": "i1", "result": "normal"}]}
    resp = client.put("/enterprises/e1/hazard-inspection/tasks/t1", json=body)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "processing"
    assert task.completed_at is None


def test_task_submit_abnormal_keeps_done(client):
    task = _task(responsible_user_id="u1")
    item = _item()
    db = _hazard_db(_ent(), task=task, items=[item], remaining_pending=0)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"items": [{"item_id": "i1", "result": "abnormal", "photo_urls": ["/uploads/x.jpg"]}]}
    resp = client.put("/enterprises/e1/hazard-inspection/tasks/t1", json=body)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "done"
    assert item.result == "abnormal"
    assert item.photo_urls == ["/uploads/x.jpg"]


def test_task_submit_invalid_result_422(client):
    db = _hazard_db(_ent(), task=_task())
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"items": [{"item_id": "i1", "result": "weird"}]}
    resp = client.put("/enterprises/e1/hazard-inspection/tasks/t1", json=body)
    assert resp.status_code == 422
    assert "result 非法" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_task_submit_item_not_in_task_422(client):
    db = _hazard_db(_ent(), task=_task(), items=[])
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"items": [{"item_id": "i9", "result": "normal"}]}
    resp = client.put("/enterprises/e1/hazard-inspection/tasks/t1", json=body)
    assert resp.status_code == 422
    assert "清单项不属于该任务" in resp.json()["detail"]


def test_task_submit_empty_items_422(client):
    db = _hazard_db(_ent(), task=_task())
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.put("/enterprises/e1/hazard-inspection/tasks/t1", json={"items": []})
    assert resp.status_code == 422
    assert "items 不能为空" in resp.json()["detail"]


def test_task_submit_non_responsible_403(client):
    ent = _ent(user_id="u2")
    member = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1", enabled=True)
    task = _task(responsible_user_id="u9")
    db = _hazard_db(ent, member=member, admin_member=None, task=task)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"items": [{"item_id": "i1", "result": "normal"}]}
    resp = client.put("/enterprises/e1/hazard-inspection/tasks/t1", json=body)
    assert resp.status_code == 403
    db.commit.assert_not_awaited()


def test_task_submit_admin_member_allowed(client):
    ent = _ent(user_id="u2")
    member = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1", enabled=True)
    admin = EnterpriseMember(id="m2", enterprise_id="e1", user_id="u1", role="enterprise_admin", enabled=True)
    task = _task(responsible_user_id="u9")
    item = _item()
    db = _hazard_db(ent, member=member, admin_member=admin, task=task, items=[item], remaining_pending=0)
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"items": [{"item_id": "i1", "result": "normal"}]}
    resp = client.put("/enterprises/e1/hazard-inspection/tasks/t1", json=body)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "done"


# ── 一键转隐患 ──

def test_to_record_creates_record_with_source_backfill(client):
    task = _task(responsible_user_id="u1")
    item = _item(result="abnormal", object_id="o1", measure_id="m1", content="配电箱门破损",
                 remark="箱门变形", photo_urls=["/uploads/a.jpg"])
    db = _hazard_db(_ent(), task=task, item=item, record_count=0)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/tasks/t1/to-record",
                       json={"item_id": "i1", "description": "箱门破损需更换"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["code"] == "HD-001"
    assert data["source_type"] == "inspection"
    assert data["source_task_id"] == "t1"
    assert data["source_item_id"] == "i1"
    assert data["object_id"] == "o1"
    assert data["measure_id"] == "m1"
    assert data["description"] == "箱门破损需更换"
    assert data["created_by"] == "u1"
    record = db.added[0]
    assert isinstance(record, HazardRecord)
    assert record.photo_urls == ["/uploads/a.jpg"]
    db.commit.assert_awaited()


def test_to_record_defaults_title_and_description(client):
    task = _task(responsible_user_id="u1")
    item = _item(result="abnormal", content="配电箱门破损", remark="箱门变形")
    db = _hazard_db(_ent(), task=task, item=item, record_count=0)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/tasks/t1/to-record", json={"item_id": "i1"})
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["title"] == "配电箱门破损"
    assert "配电箱门破损" in data["description"]
    assert "箱门变形" in data["description"]


def test_to_record_title_from_body_preferred(client):
    task = _task(responsible_user_id="u1")
    item = _item(result="abnormal", content="配电箱门破损")
    db = _hazard_db(_ent(), task=task, item=item, record_count=0)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/tasks/t1/to-record",
                       json={"item_id": "i1", "title": "配电箱门缺失"})
    assert resp.status_code == 201
    assert resp.json()["data"]["title"] == "配电箱门缺失"


def test_to_record_requires_abnormal_item(client):
    task = _task(responsible_user_id="u1")
    item = _item(result="normal")
    db = _hazard_db(_ent(), task=task, item=item)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/tasks/t1/to-record", json={"item_id": "i1"})
    assert resp.status_code == 422
    assert "仅 result=abnormal" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_to_record_item_not_found_404(client):
    task = _task(responsible_user_id="u1")
    db = _hazard_db(_ent(), task=task, item=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/tasks/t1/to-record", json={"item_id": "i9"})
    assert resp.status_code == 404
    assert "排查项不存在" in resp.json()["detail"]


def test_to_record_code_increments_with_existing_count(client):
    task = _task(responsible_user_id="u1")
    item = _item(result="abnormal")
    db = _hazard_db(_ent(), task=task, item=item, record_count=4)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/tasks/t1/to-record", json={"item_id": "i1"})
    assert resp.status_code == 201
    assert resp.json()["data"]["code"] == "HD-005"


def test_to_record_non_responsible_403(client):
    ent = _ent(user_id="u2")
    member = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1", enabled=True)
    task = _task(responsible_user_id="u9")
    item = _item(result="abnormal")
    db = _hazard_db(ent, member=member, admin_member=None, task=task, item=item)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/tasks/t1/to-record", json={"item_id": "i1"})
    assert resp.status_code == 403


# ── 任务生成（服务层） ──

@pytest.mark.asyncio
async def test_generate_daily_builds_items():
    plan = _plan(name="生产车间日排查", frequency="daily", zone_ids=["z1"], template_id="tpl1",
                 responsible_user_id="u2")
    obj = RiskObject(id="o1", enterprise_id="e1", zone_id="z1", name="配电室", category="电气",
                     description="变配电设施", is_risk_point=True)
    event = RiskEvent(id="ev1", object_id="o1")
    measure = RiskMeasure(id="m1", event_id="ev1", measure_category="工程控制",
                          description="安装漏电保护", check_items=["动作灵敏", "外观完好"])
    template = HazardChecklistTemplate(id="tpl1", enterprise_id=None, name="日常检查表", category="daily",
                                       items=[{"content": "通道畅通", "expected_note": "无堵塞"},
                                              {"content": "消防器材完好", "expected_note": "压力正常"}])
    db = _hazard_db(_ent(), objects=[obj], events=[event], measures=[measure], template=template)
    task = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 15))
    assert task is not None
    assert task.title == "生产车间日排查 · 08-15"
    assert task.due_at == datetime(2026, 8, 15, 18, 0)
    assert task.status == "pending"
    assert task.responsible_user_id == "u2"
    contents = [i.content for i in task.items]
    assert "风险点 配电室（电气）现场核查" in contents
    assert "工程控制：安装漏电保护" in contents
    assert "通道畅通" in contents
    assert "消防器材完好" in contents
    measure_item = next(i for i in task.items if i.measure_id == "m1")
    assert measure_item.object_id == "o1"
    assert measure_item.expected_note == "动作灵敏；外观完好"
    assert len([x for x in db.added if isinstance(x, HazardInspectionItem)]) == 4


@pytest.mark.asyncio
async def test_generate_weekly_matches_weekday_only():
    plan = _plan(frequency="weekly", weekdays=[0], zone_ids=["z1"], template_id=None)
    db = _hazard_db(_ent(), objects=[])
    assert date(2026, 8, 17).weekday() == 0  # 周一
    monday = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 17))
    assert monday is not None
    assert monday.title == "生产车间日排查 · 08-17"
    wednesday = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 19))
    assert wednesday is None


@pytest.mark.asyncio
async def test_generate_custom_matches_weekday_only():
    plan = _plan(frequency="custom", weekdays=[5], zone_ids=["z1"], template_id=None)
    db = _hazard_db(_ent(), objects=[])
    assert date(2026, 8, 15).weekday() == 5  # 周六
    saturday = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 15))
    assert saturday is not None
    sunday = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 16))
    assert sunday is None


@pytest.mark.asyncio
async def test_generate_monthly_on_first_day():
    plan = _plan(frequency="monthly", zone_ids=["z1"], template_id=None)
    db = _hazard_db(_ent(), objects=[])
    first = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 1))
    assert first is not None
    assert first.title == "生产车间日排查 · 08-01"
    mid = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 15))
    assert mid is None


@pytest.mark.asyncio
async def test_generate_dedupe_skips_existing_task():
    plan = _plan(frequency="daily", zone_ids=["z1"], template_id=None)
    db = _hazard_db(_ent(), dedupe_hit=MagicMock())
    task = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 15))
    assert task is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_generate_without_template_only_dynamic_items():
    plan = _plan(frequency="daily", zone_ids=["z1"], template_id=None)
    obj = RiskObject(id="o1", enterprise_id="e1", zone_id="z1", name="配电室", category="电气", is_risk_point=True)
    event = RiskEvent(id="ev1", object_id="o1")
    measure = RiskMeasure(id="m1", event_id="ev1", measure_category="工程控制", description="安装漏电保护")
    db = _hazard_db(_ent(), objects=[obj], events=[event], measures=[measure], template=None)
    task = await generate_tasks_for_plan(db, plan, on_date=date(2026, 8, 15))
    assert task is not None
    assert len(task.items) == 2  # 1 风险点 + 1 管控措施，无模板项
    assert all(i.measure_id is None or i.measure_id == "m1" for i in task.items)


@pytest.mark.asyncio
async def test_next_hazard_code_zero_based():
    db = _hazard_db(_ent(), record_count=0)
    assert await next_hazard_code(db, "e1") == "HD-001"


@pytest.mark.asyncio
async def test_next_hazard_code_increments():
    db = _hazard_db(_ent(), record_count=4)
    assert await next_hazard_code(db, "e1") == "HD-005"
