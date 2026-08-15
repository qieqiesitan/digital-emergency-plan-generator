"""隐患排查治理任务 7 测试：整改 / 复查 / 销号端点（状态机接线）。

测试风格与 tests/test_hazard_grade_api.py / test_hazard_record_api.py 一致：
无 db fixture，端点用 FastAPI TestClient + dependency_overrides + SQL 文本分发
mock；async 服务函数用 @pytest.mark.asyncio。

覆盖：
- rectify 成功（写 HazardRectification + 状态 reviewing + 复查提醒通知 +
  review_deadline 按字典天数计算）、enterprise_admin 代整改例外、
  非整改人 422、复查人=整改人 422、content 空 422、复查人非启用成员 422、
  记录/企业不归属 404、状态非法 409、缺 review 天数不建通知
- review pass/fail 全路径（standard 一般停留 reviewing、strict+重大 →
  second_review、second_review pass 停留、fail → rectifying）、
  非指定复查人 422、enterprise_admin 代复查、result 非法 422、404/409
- close 成功（review_type=close + closed_at + audit log）、
  非 reviewing/second_review 409、strict+重大未 second_review 409、
  非 admin 403、404
- 全链路 API 级 registered→grade→rectify→review→close + 销号留痕断言
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.data_dict import DataDict
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.hazard_management import (
    HazardAuditLog,
    HazardNotification,
    HazardRecord,
    HazardRectification,
    HazardReview,
)
from app.models.user import User
from app.routers import hazard_management
from app.services.data_dict_service import invalidate_dict_cache


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


def _ent(**kw):
    e = Enterprise(id="e1", user_id="u1", name="甲公司", hazard_closure_mode="standard")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _record(**kw):
    r = HazardRecord(
        id=kw.pop("id", "r1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        code=kw.pop("code", "HD-001"),
        source_type=kw.pop("source_type", "report"),
        title=kw.pop("title", "配电箱门破损"),
        description=kw.pop("description", "配电箱门变形无法闭合"),
        status=kw.pop("status", "registered"),
    )
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _deadline_row(code, days):
    return DataDict(dict_type="deadline_rules", code=code, label=f"{code}期限",
                    value={"days": days}, scope="system", enabled=True, is_system=True)


def _review_db(ent, *, admin_member=None, member=None, record=None, dict_rows=None):
    """按 SQL 文本特征分发（参照 test_hazard_grade_api.py 的 _grade_db）。"""
    db = AsyncMock()
    db.added = []

    def fake_add(obj):
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
        if "FROM data_dicts" in text:
            return _scalars(dict_rows or [])
        if "FROM hazard_records" in text:
            return _scalar(record)
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
    app.dependency_overrides[get_db] = lambda: _review_db(_ent(), record=_record())
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clear_dict_cache():
    """每个测试结束后清空数据字典进程内缓存，避免污染同进程其他测试模块。"""
    yield
    invalidate_dict_cache()


def _reviewing_record(**kw):
    defaults = dict(status="reviewing", level="general", reviewer_user_id="u2",
                    rectification_user_id="u7")
    defaults.update(kw)
    return _record(**defaults)


# ── rectify：成功路径 ──

def test_rectify_success_writes_rectification_and_review_notice(client):
    invalidate_dict_cache("e1", "deadline_rules")
    rec = _record(status="rectifying", rectification_user_id="u1")
    db = _review_db(_ent(), member=MagicMock(), record=rec,
                    dict_rows=[_deadline_row("review", 15)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已更换箱门并加锁", "evidence": ["/uploads/a.jpg"],
                             "reviewer_user_id": "u2"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    data = resp.json()["data"]
    assert data["status"] == "reviewing"
    assert data["reviewer_user_id"] == "u2"
    assert data["review_deadline"] == (date.today() + timedelta(days=15)).isoformat()
    added = db.added
    rect = next(x for x in added if isinstance(x, HazardRectification))
    assert rect.record_id == "r1"
    assert rect.user_id == "u1"
    assert rect.content == "已更换箱门并加锁"
    assert rect.evidence == ["/uploads/a.jpg"]
    notice = next(x for x in added if isinstance(x, HazardNotification))
    assert notice.type == "review_due"
    assert notice.user_id == "u2"
    assert notice.record_id == "r1"
    assert notice.enterprise_id == "e1"
    assert "请于" in notice.message
    assert (date.today() + timedelta(days=15)).isoformat() in notice.message
    assert any(isinstance(x, HazardAuditLog) and x.action == "rectify" for x in added)
    db.commit.assert_awaited()


def test_rectify_admin_member_bypasses_rectifier(client):
    invalidate_dict_cache("e1", "deadline_rules")
    ent = _ent(user_id="u0")
    admin = EnterpriseMember(id="m2", enterprise_id="e1", user_id="u1",
                             role="enterprise_admin", enabled=True)
    rec = _record(status="rectifying", rectification_user_id="u7")
    db = _review_db(ent, admin_member=admin, member=MagicMock(), record=rec,
                    dict_rows=[_deadline_row("review", 15)])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "代整改提交", "reviewer_user_id": "u2"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "reviewing"
    assert rec.rectification_user_id == "u7"  # 代整改不覆盖 grade/approve 指定的责任人
    db.commit.assert_awaited()


# ── rectify：字段/身份/权限校验 ──

def test_rectify_non_assigned_rectifier_422(client):
    invalidate_dict_cache("e1", "deadline_rules")
    ent = _ent(user_id="u0")
    plain = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1",
                             role="member", enabled=True)
    rec = _record(status="rectifying", rectification_user_id="u7")
    db = _review_db(ent, admin_member=None, member=plain, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已整改", "reviewer_user_id": "u2"})
    assert resp.status_code == 422
    assert "整改" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_rectify_reviewer_equals_rectifier_422(client):
    rec = _record(status="rectifying", rectification_user_id="u1")
    db = _review_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已整改", "reviewer_user_id": "u1"})
    assert resp.status_code == 422
    assert "复查人不能为整改人" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_rectify_blank_content_422(client):
    rec = _record(status="rectifying", rectification_user_id="u1")
    db = _review_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "   ", "reviewer_user_id": "u2"})
    assert resp.status_code == 422
    assert "content 不能为空" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_rectify_reviewer_not_enabled_member_422(client):
    rec = _record(status="rectifying", rectification_user_id="u1")
    db = _review_db(_ent(), member=None, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已整改", "reviewer_user_id": "u9"})
    assert resp.status_code == 422
    assert "启用成员" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_rectify_wrong_state_409(client):
    invalidate_dict_cache("e1", "deadline_rules")
    rec = _record(status="registered")
    db = _review_db(_ent(), member=MagicMock(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已整改", "reviewer_user_id": "u2"})
    assert resp.status_code == 409
    assert "不允许执行动作" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_rectify_record_not_in_enterprise_404(client):
    db = _review_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r9/rectify",
                       json={"content": "已整改", "reviewer_user_id": "u2"})
    assert resp.status_code == 404
    assert "隐患记录不存在" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_rectify_non_member_404(client):
    ent = _ent(user_id="u0")
    rec = _record(status="rectifying", rectification_user_id="u7")
    db = _review_db(ent, member=None, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已整改", "reviewer_user_id": "u2"})
    assert resp.status_code == 404
    assert "企业不存在" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_rectify_missing_review_rule_skips_notification(client):
    invalidate_dict_cache("e1", "deadline_rules")
    rec = _record(status="rectifying", rectification_user_id="u1")
    db = _review_db(_ent(), member=MagicMock(), record=rec, dict_rows=[])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已整改", "reviewer_user_id": "u2"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "reviewing"
    assert data["review_deadline"] is None
    assert not any(isinstance(x, HazardNotification) for x in db.added)
    db.commit.assert_awaited()


def test_rectify_review_rule_json_string_days(client):
    invalidate_dict_cache("e1", "deadline_rules")
    rec = _record(status="rectifying", rectification_user_id="u1")
    row = DataDict(dict_type="deadline_rules", code="review", label="复查期限",
                   value='{"days": 10}', scope="system", enabled=True, is_system=True)
    db = _review_db(_ent(), member=MagicMock(), record=rec, dict_rows=[row])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已整改", "reviewer_user_id": "u2"})
    assert resp.status_code == 200
    assert resp.json()["data"]["review_deadline"] == (date.today() + timedelta(days=10)).isoformat()
    notice = next(x for x in db.added if isinstance(x, HazardNotification))
    assert "请于" in notice.message
    db.commit.assert_awaited()


# ── review：pass/fail 全路径 ──

def test_review_pass_standard_general_stays_reviewing(client):
    rec = _reviewing_record(reviewer_user_id="u1")
    db = _review_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "pass", "comment": "整改合格"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "reviewing"
    assert data["closed_at"] is None
    added = db.added
    review = next(x for x in added if isinstance(x, HazardReview))
    assert review.review_type == "first_review"
    assert review.result == "pass"
    assert review.comment == "整改合格"
    assert review.user_id == "u1"
    assert any(isinstance(x, HazardAuditLog) and x.action == "review" for x in added)
    db.commit.assert_awaited()


def test_review_pass_strict_major_goes_second_review(client):
    ent = _ent(hazard_closure_mode="strict")
    rec = _reviewing_record(level="major", reviewer_user_id="u1")
    db = _review_db(ent, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "pass", "comment": "首次复查通过"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "second_review"
    assert resp.json()["data"]["closed_at"] is None


def test_review_second_review_pass_stays(client):
    ent = _ent(hazard_closure_mode="strict")
    rec = _record(status="second_review", level="major", reviewer_user_id="u1",
                  rectification_user_id="u7")
    db = _review_db(ent, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "pass", "comment": "二次复核通过", "evidence": ["e.png"]})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "second_review"
    review = next(x for x in db.added if isinstance(x, HazardReview))
    assert review.review_type == "second_review"
    assert review.evidence == ["e.png"]


def test_review_fail_returns_rectifying(client):
    rec = _reviewing_record(reviewer_user_id="u1")
    db = _review_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "fail", "comment": "未整改到位"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "rectifying"
    review = next(x for x in db.added if isinstance(x, HazardReview))
    assert review.result == "fail"
    assert review.review_type == "first_review"
    db.commit.assert_awaited()


# ── review：身份/权限/状态校验 ──

def test_review_admin_member_bypasses_reviewer(client):
    ent = _ent(user_id="u0")
    admin = EnterpriseMember(id="m2", enterprise_id="e1", user_id="u1",
                             role="enterprise_admin", enabled=True)
    rec = _reviewing_record(reviewer_user_id="u7", rectification_user_id="u8")
    db = _review_db(ent, admin_member=admin, member=MagicMock(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "pass"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "reviewing"


def test_review_non_assigned_reviewer_422(client):
    ent = _ent(user_id="u0")
    plain = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1",
                             role="member", enabled=True)
    rec = _reviewing_record(reviewer_user_id="u7")
    db = _review_db(ent, admin_member=None, member=plain, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "pass"})
    assert resp.status_code == 422
    assert "复查" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_review_invalid_result_422(client):
    rec = _reviewing_record(reviewer_user_id="u1")
    db = _review_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "maybe"})
    assert resp.status_code == 422
    assert "pass 或 fail" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_review_wrong_state_409(client):
    rec = _record(status="rectifying", rectification_user_id="u1")
    db = _review_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "pass"})
    assert resp.status_code == 409
    assert "不允许执行动作" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_review_record_not_in_enterprise_404(client):
    db = _review_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r9/review",
                       json={"result": "pass"})
    assert resp.status_code == 404
    db.commit.assert_not_awaited()


# ── close：成功路径 ──

def test_close_success_writes_close_review_and_closed_at(client):
    rec = _reviewing_record(reviewer_user_id="u2")
    db = _review_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/close",
                       json={"comment": "验收合格，予以销号"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert resp.json()["code"] == 0
    assert data["status"] == "closed"
    assert data["closed_at"]
    added = db.added
    review = next(x for x in added if isinstance(x, HazardReview))
    assert review.review_type == "close"
    assert review.comment == "验收合格，予以销号"
    assert any(isinstance(x, HazardAuditLog) and x.action == "close"
               and x.record_id == "r1" for x in added)
    db.commit.assert_awaited()


def test_close_strict_major_after_second_review_success(client):
    ent = _ent(hazard_closure_mode="strict")
    rec = _record(status="second_review", level="major", reviewer_user_id="u2",
                  rectification_user_id="u7")
    db = _review_db(ent, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/close",
                       json={"comment": "二次复核通过后销号"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "closed"
    review = next(x for x in db.added if isinstance(x, HazardReview))
    assert review.review_type == "close"


# ── close：状态/权限校验 ──

def test_close_strict_major_without_second_review_409(client):
    ent = _ent(hazard_closure_mode="strict")
    rec = _reviewing_record(level="major")
    db = _review_db(ent, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/close", json={})
    assert resp.status_code == 409
    assert "二次复核" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_close_not_reviewing_409(client):
    rec = _record(status="registered")
    db = _review_db(_ent(), record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/close", json={})
    assert resp.status_code == 409
    assert "不允许执行动作" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_close_non_admin_403(client):
    ent = _ent(user_id="u0")
    plain = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1",
                             role="member", enabled=True)
    rec = _reviewing_record()
    db = _review_db(ent, admin_member=None, member=plain, record=rec)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/close", json={})
    assert resp.status_code == 403
    assert "无权限" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_close_record_not_in_enterprise_404(client):
    db = _review_db(_ent(), record=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/records/r9/close", json={})
    assert resp.status_code == 404
    db.commit.assert_not_awaited()


# ── 全链路：registered → grade → rectify → review → close ──

def test_full_flow_registered_to_closed_api(client):
    invalidate_dict_cache("e1", "deadline_rules")
    rec = _record()
    dict_rows = [_deadline_row("major", 15), _deadline_row("general", 7),
                 _deadline_row("review", 5)]
    db = _review_db(_ent(), member=MagicMock(), record=rec, dict_rows=dict_rows)
    client.app.dependency_overrides[get_db] = lambda: db

    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/grade",
                       json={"level": "general", "rectification_user_id": "u1"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rectifying"
    assert rec.rectification_user_id == "u1"

    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/rectify",
                       json={"content": "已更换箱门", "reviewer_user_id": "u2"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "reviewing"
    assert resp.json()["data"]["reviewer_user_id"] == "u2"
    assert resp.json()["data"]["review_deadline"] == (date.today() + timedelta(days=5)).isoformat()

    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/review",
                       json={"result": "pass", "comment": "整改合格"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "reviewing"  # standard 模式一般隐患 pass 停留

    resp = client.post("/enterprises/e1/hazard-inspection/records/r1/close",
                       json={"comment": "予以销号"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "closed"
    assert data["closed_at"]

    # 销号留痕：HazardReview(review_type=close) + HazardAuditLog(action=close)
    added = db.added
    assert any(isinstance(x, HazardRectification) and x.content == "已更换箱门" for x in added)
    assert any(isinstance(x, HazardNotification) and x.type == "review_due" for x in added)
    reviews = [x for x in added if isinstance(x, HazardReview)]
    assert any(x.review_type == "first_review" and x.result == "pass" for x in reviews)
    assert any(x.review_type == "close" for x in reviews)
    audit_actions = [x.action for x in added if isinstance(x, HazardAuditLog)]
    assert "grade" in audit_actions
    assert "rectify" in audit_actions
    assert "review" in audit_actions
    assert "close" in audit_actions
    assert rec.closed_at is not None
    db.commit.assert_awaited()
