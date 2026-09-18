"""AI 清单补全落库端点：POST /hazard-inspection/tasks/{id}/items（2026-09-18 补）。

背景：`/ai/checklist` 只返回建议项，落库端点在本次补齐前并不存在——也就是说
"勾选后与既有清单项合并去重"这条链路的最后一跳是断的（前端 service 也从未被调用）。
本文件钉住落库语义：按 content 去重、状态回退、权限与归属。
"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.enterprise import Enterprise
from app.models.hazard_management import HazardInspectionItem, HazardInspectionTask
from app.models.user import User
from app.routers import hazard_management


def _scalar(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _scalars(values):
    res = MagicMock()
    inner = MagicMock()
    inner.all.return_value = list(values)
    res.scalars.return_value = inner
    return res


def _first(value):
    res = MagicMock()
    res.first.return_value = value
    return res


def _task(**kw):
    params = dict(id="t1", enterprise_id="e1", plan_id="p1", title="罐区日检",
                  status="pending", responsible_user_id="u1")
    params.update(kw)
    return HazardInspectionTask(**params)


def _item(item_id, content, result="pending"):
    it = HazardInspectionItem(task_id="t1", content=content, result=result)
    it.id = item_id
    return it


def _db(*, ent, task, items, member_hit=False, admin_member=False):
    db = AsyncMock()
    db.added = []
    db.add = MagicMock(side_effect=lambda obj: db.added.append(obj))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    def fake_execute(stmt, *params):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _scalar(ent)
        if "FROM enterprise_members" in text:
            # 管理员查询带 role 过滤，普通成员查询不带
            is_admin_query = "enterprise_members.role" in text
            hit = admin_member if is_admin_query else member_hit
            return _first(MagicMock() if hit else None)
        if "FROM hazard_inspection_tasks" in text:
            return _scalar(task)
        if "FROM hazard_inspection_items" in text:
            return _scalars(items)
        return _scalar(None)

    db.execute.side_effect = fake_execute
    return db


def _client(db, user_id="u1"):
    app = FastAPI()
    app.include_router(hazard_management.router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=user_id, email="a@b.c", name="A", role="user"
    )
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


URL = "/enterprises/e1/hazard-inspection/tasks/t1/items"


def test_append_dedupes_and_reopens_done_task():
    """已存在同内容 → 跳过；新内容入库；done 任务因新增 pending 项回退为 processing。"""
    task = _task(status="done")
    existing = [_item("i1", "灭火器压力表指针在绿区", result="normal")]
    db = _db(ent=Enterprise(id="e1", user_id="u1", name="甲公司"), task=task, items=existing)

    resp = _client(db).post(
        URL,
        json={
            "items": [
                {"content": "灭火器压力表指针在绿区"},  # 与既有项重复
                {"content": "罐区可燃气体浓度 ≤ 25% LEL", "expected_note": "≤25% LEL"},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert [i["content"] for i in data["appended"]] == ["罐区可燃气体浓度 ≤ 25% LEL"]
    assert data["skipped"] == ["灭火器压力表指针在绿区"]
    assert data["task"]["status"] == "processing"
    assert task.completed_at is None
    assert len(db.added) == 1


def test_append_all_duplicates_keeps_task_done():
    task = _task(status="done")
    existing = [_item("i1", "灭火器压力表指针在绿区", result="normal")]
    db = _db(ent=Enterprise(id="e1", user_id="u1", name="甲公司"), task=task, items=existing)

    resp = _client(db).post(URL, json={"items": [{"content": "灭火器压力表指针在绿区"}]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["appended"] == []
    assert resp.json()["data"]["skipped"] == ["灭火器压力表指针在绿区"]
    assert task.status == "done"  # 没有新增项就不该改动状态
    db.commit.assert_not_awaited()


def test_append_requires_task_actor():
    """是企业启用成员但不是责任人、也不是企业管理员 → 403（读归属已过，写权限不过）。"""
    task = _task(responsible_user_id="u9")
    db = _db(
        ent=Enterprise(id="e1", user_id="u0", name="甲公司"),
        task=task,
        items=[],
        member_hit=True,
    )
    resp = _client(db, user_id="u1").post(URL, json={"items": [{"content": "x"}]})
    assert resp.status_code == 403


def test_append_non_member_gets_404():
    """非成员连企业都读不到 → 404（沿用项目"不用 403 探测存在性"的约定）。"""
    db = _db(ent=Enterprise(id="e1", user_id="u0", name="甲公司"), task=_task(), items=[])
    resp = _client(db, user_id="u1").post(URL, json={"items": [{"content": "x"}]})
    assert resp.status_code == 404


def test_append_allows_enterprise_admin_member():
    task = _task(responsible_user_id="u9")
    db = _db(
        ent=Enterprise(id="e1", user_id="u0", name="甲公司"),
        task=task,
        items=[],
        member_hit=True,
        admin_member=True,
    )
    resp = _client(db, user_id="u1").post(URL, json={"items": [{"content": "新增检查项"}]})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]["appended"]) == 1


def test_append_rejects_blank_content_and_other_enterprise_task():
    db = _db(ent=Enterprise(id="e1", user_id="u1", name="甲公司"), task=_task(), items=[])
    client = _client(db)
    assert client.post(URL, json={"items": [{"content": "   "}]}).status_code == 422
    # 任务不存在（归属不符）→ 404
    db2 = _db(ent=Enterprise(id="e1", user_id="u1", name="甲公司"), task=None, items=[])
    assert _client(db2).post(URL, json={"items": [{"content": "x"}]}).status_code == 404
