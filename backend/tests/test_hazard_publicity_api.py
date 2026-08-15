"""隐患排查治理任务 10 测试：隐患公示（企业内列表 + token 生成/重置 + 公开脱敏页）。

测试风格与 test_hazard_record_api.py / test_hazard_public_api.py 一致：
无 db fixture，端点用 FastAPI TestClient + dependency_overrides + SQL 文本分发
mock。

覆盖：
- 企业内公示列表：默认 all、scope 过滤（ongoing/closed）、非法 scope 422、
  字段含整改情况摘要（最近整改 content > 治理方案 goal > 未提交整改）、
  状态/来源中文标签、created_at 倒序、字典企业覆盖口径、非归属 404
- token 生成/重置：企业主/启用管理员 200 且返回 token + 完整公开链接、
  非管理员成员 403、企业不存在 404
- 公开脱敏页：脱敏字段不出现、企业名称脱敏（首字符 + **）、masked 标记、
  generated_at、无效 token 404「链接已失效」、scope 过滤、非法 scope 422
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models.data_dict import DataDict
from app.models.enterprise import Enterprise
from app.models.enterprise_org import EnterpriseMember
from app.models.hazard_management import HazardRectification, HazardRecord
from app.models.user import User
from app.routers import hazard_management, public_hazard
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


def _dict_row(dict_type, code, label):
    return DataDict(dict_type=dict_type, code=code, label=label,
                    value={}, scope="system", sort_order=1, enabled=True, is_system=True)


def _default_dict_rows():
    """系统种子对应字典：publicity_scope / record_status_label / source_type。"""
    return [
        _dict_row("publicity_scope", "ongoing", "整改中公开"),
        _dict_row("publicity_scope", "closed", "已销号公开"),
        _dict_row("publicity_scope", "all", "全部公开"),
        _dict_row("record_status_label", "registered", "已登记"),
        _dict_row("record_status_label", "grading", "待分级"),
        _dict_row("record_status_label", "rectifying", "整改中"),
        _dict_row("record_status_label", "reviewing", "复查中"),
        _dict_row("record_status_label", "second_review", "二次复核"),
        _dict_row("record_status_label", "closed", "已销号"),
        _dict_row("source_type", "inspection", "排查"),
        _dict_row("source_type", "report", "上报"),
        _dict_row("source_type", "regulatory", "监管检查"),
        _dict_row("source_type", "accident", "事故"),
        _dict_row("source_type", "manual", "手工"),
    ]


def _hazard_record(**kw):
    now = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)
    r = HazardRecord(
        id=kw.pop("id", "r1"),
        enterprise_id=kw.pop("enterprise_id", "e1"),
        code=kw.pop("code", "HD-001"),
        source_type=kw.pop("source_type", "manual"),
        title=kw.pop("title", "配电箱门破损"),
        description=kw.pop("description", "配电箱门变形无法闭合"),
        status=kw.pop("status", "rectifying"),
        created_at=kw.pop("created_at", now),
    )
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _rect(**kw):
    now = datetime(2026, 8, 15, 11, 0, 0, tzinfo=timezone.utc)
    r = HazardRectification(
        id=kw.pop("id", "fix1"),
        record_id=kw.pop("record_id", "r1"),
        content=kw.pop("content", "已更换配电箱门"),
        created_at=kw.pop("created_at", now),
    )
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def _pub_db(ent, *, member=None, admin_member=None, records=None,
            rectifications=None, dict_rows=None):
    """按 SQL 文本特征分发（参照 test_hazard_record_api.py 的 _record_db）。

    records：公示列表 mock 数据；rectifications：整改记录 mock 数据；
    admin_member：enterprise_admin 角色限定查询（role = ...）命中行；
    member：通用启用成员查询命中行。
    """
    records = records or []
    rectifications = rectifications or []
    dict_rows = dict_rows if dict_rows is not None else _default_dict_rows()
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
            if "role =" in text:
                return _first(admin_member if admin_member and getattr(admin_member, "enabled", True) else None)
            return _first(member if member and getattr(member, "enabled", True) else None)
        if "FROM data_dicts" in text:
            # 真实查询按 dict_type 过滤；mock 从编译参数还原过滤，避免跨字典串味
            compiled = stmt.compile().params
            dtype = compiled.get("dict_type_1") if isinstance(compiled, dict) else None
            rows = [r for r in dict_rows if r.dict_type == dtype] if dtype else dict_rows
            return _scalars(rows)
        if "FROM hazard_records" in text:
            if "status !=" in text:
                return _scalars([r for r in records if r.status != "closed"])
            if "status =" in text:
                return _scalars([r for r in records if r.status == "closed"])
            return _scalars(records)
        if "FROM hazard_rectifications" in text:
            return _scalars(rectifications)
        return _scalar(None)

    db.execute.side_effect = fake_execute
    return db


@pytest.fixture()
def client():
    invalidate_dict_cache()
    app = FastAPI()
    app.include_router(hazard_management.router)
    app.include_router(public_hazard.router)

    def _override_user():
        return User(id="u1", email="a@b.c", name="A", role="user")

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = lambda: _pub_db(_ent())
    with TestClient(app) as test_client:
        yield test_client
    invalidate_dict_cache()


def _two_records():
    older = _hazard_record(
        id="r1", code="HD-001", status="closed", level="general",
        source_type="inspection",
        created_at=datetime(2026, 8, 10, 10, 0, 0, tzinfo=timezone.utc),
    )
    newer = _hazard_record(
        id="r2", code="HD-002", status="rectifying", level="major",
        source_type="manual",
        created_at=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
    )
    return older, newer


# ── 企业内公示列表 ──

def test_publicity_list_default_all_sorted_desc(client):
    older, newer = _two_records()
    db = _pub_db(_ent(), records=[newer, older])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/publicity")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    items = resp.json()["data"]
    assert [i["code"] for i in items] == ["HD-002", "HD-001"]
    first = items[0]
    # 公示行字段白名单：不含责任人/联系方式/照片/位置/内部备注（§11.2 脱敏）
    assert set(first) == {"code", "title", "level", "status", "rectification", "source_type"}
    assert first["status"] == "整改中"
    assert first["level"] == "major"
    assert first["source_type"] == "手工"
    assert first["rectification"] == "未提交整改"
    # 排序：created_at 倒序由查询侧保证（mock 按序直通）
    executed = [str(a.args[0]) for a in db.execute.await_args_list
                if "FROM hazard_records" in str(a.args[0])]
    assert any("ORDER BY" in s and "created_at" in s for s in executed)


def test_publicity_list_scope_ongoing_filters(client):
    older, newer = _two_records()
    db = _pub_db(_ent(), records=[newer, older])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/publicity",
                      params={"scope": "ongoing"})
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert [i["code"] for i in items] == ["HD-002"]
    assert all(i["status"] != "已销号" for i in items)


def test_publicity_list_scope_closed_filters(client):
    older, newer = _two_records()
    db = _pub_db(_ent(), records=[newer, older])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/publicity",
                      params={"scope": "closed"})
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert [i["code"] for i in items] == ["HD-001"]
    assert items[0]["status"] == "已销号"


def test_publicity_list_invalid_scope_422(client):
    db = _pub_db(_ent(), records=[])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/publicity",
                      params={"scope": "foo"})
    assert resp.status_code == 422
    assert "scope 非法" in resp.json()["detail"]


def test_publicity_list_dict_enterprise_override_scope(client):
    """企业覆盖字典：口径码值以 get_dict_map 合并结果为准（企业条目优先）。"""
    rows = [_dict_row("publicity_scope", "ongoing", "整改中公开")]
    db = _pub_db(_ent(), records=[], dict_rows=rows)
    client.app.dependency_overrides[get_db] = lambda: db
    rejected = client.get("/enterprises/e1/hazard-inspection/publicity",
                          params={"scope": "all"})
    assert rejected.status_code == 422
    assert "可选" in rejected.json()["detail"]
    ok = client.get("/enterprises/e1/hazard-inspection/publicity",
                    params={"scope": "ongoing"})
    assert ok.status_code == 200


def test_publicity_list_rectification_summary_priority(client):
    r1 = _hazard_record(id="r1", code="HD-001", status="rectifying")
    r2 = _hazard_record(id="r2", code="HD-002", status="rectifying",
                        rectification_plan={"goal": "完成配电箱整体更换"})
    r3 = _hazard_record(id="r3", code="HD-003", status="rectifying",
                        rectification_plan={"goal": "备选目标"})
    fix = _rect(record_id="r3", content="已整改到位")
    db = _pub_db(_ent(), records=[r1, r2, r3], rectifications=[fix])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/publicity")
    assert resp.status_code == 200
    by_code = {i["code"]: i["rectification"] for i in resp.json()["data"]}
    assert by_code["HD-001"] == "未提交整改"
    assert by_code["HD-002"] == "完成配电箱整体更换"
    assert by_code["HD-003"] == "已整改到位"


def test_publicity_list_latest_rectification_wins(client):
    r1 = _hazard_record(id="r1", code="HD-001", status="rectifying")
    later = _rect(id="fix2", record_id="r1", content="已完成复检并准备销号",
                  created_at=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc))
    earlier = _rect(id="fix1", record_id="r1", content="第一次整改",
                    created_at=datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc))
    db = _pub_db(_ent(), records=[r1], rectifications=[later, earlier])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/publicity")
    assert resp.status_code == 200
    item = resp.json()["data"][0]
    assert item["rectification"] == "已完成复检并准备销号"
    # 查询侧按 created_at DESC 排序（mock 按序直通，latest.setdefault 取首条）
    rect_stmt = [str(a.args[0]) for a in db.execute.await_args_list
                 if "FROM hazard_rectifications" in str(a.args[0])]
    assert rect_stmt and "ORDER BY" in rect_stmt[0]
    assert "created_at" in rect_stmt[0]


def test_publicity_list_permission_404(client):
    db = _pub_db(_ent(user_id="u2"), member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/enterprises/e1/hazard-inspection/publicity")
    assert resp.status_code == 404
    assert "企业不存在" in resp.json()["detail"]


# ── token 生成/重置 ──

def test_publicity_token_owner_generates_token_and_link(client):
    ent = _ent()
    db = _pub_db(ent)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/publicity-token")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["token"]) == 64
    assert data["link"] == f"/h/{data['token']}"
    assert ent.hazard_public_token == data["token"]
    assert db.added == []  # 仅更新企业字段，不新增行
    db.commit.assert_awaited()


def test_publicity_token_admin_member_allowed(client):
    admin = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1",
                             role="enterprise_admin", enabled=True)
    db = _pub_db(_ent(user_id="u2"), admin_member=admin)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/publicity-token")
    assert resp.status_code == 200
    assert len(resp.json()["data"]["token"]) == 64
    db.commit.assert_awaited()


def test_publicity_token_non_admin_member_403(client):
    member = EnterpriseMember(id="m1", enterprise_id="e1", user_id="u1",
                              role="member", enabled=True)
    db = _pub_db(_ent(user_id="u2"), member=member, admin_member=None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/publicity-token")
    assert resp.status_code == 403
    assert "无权限" in resp.json()["detail"]
    db.commit.assert_not_awaited()


def test_publicity_token_enterprise_missing_404(client):
    db = _pub_db(None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.post("/enterprises/e1/hazard-inspection/publicity-token")
    assert resp.status_code == 404
    assert "企业不存在" in resp.json()["detail"]
    db.commit.assert_not_awaited()


# ── 公开脱敏页 ──

def test_public_hazard_publicity_masked_response(client):
    r = _hazard_record(
        id="r1", code="HD-001", status="rectifying", level="major",
        source_type="inspection",
        photo_urls=["/uploads/a.jpg"], location="3 号车间东侧",
        rectification_user_id="u9", reviewer_user_id="u8", created_by="u1",
        closed_at=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
        rectification_plan={"goal": "更换配电箱"},
    )
    fix = _rect(record_id="r1", content="已更换配电箱门")
    db = _pub_db(_ent(hazard_public_token="pub-token-1"),
                 records=[r], rectifications=[fix])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/public/hazard/pub-token-1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["enterprise_name"] == "甲**"
    assert data["masked"] is True
    assert data["generated_at"]
    item = data["items"][0]
    assert set(item) == {"code", "title", "level", "status", "rectification", "source_type"}
    assert item["code"] == "HD-001"
    assert item["status"] == "整改中"
    assert item["level"] == "major"
    assert item["source_type"] == "排查"
    assert item["rectification"] == "已更换配电箱门"
    for sensitive in ("photo_urls", "location", "description", "rectification_user_id",
                      "reviewer_user_id", "created_by", "closed_at", "created_at",
                      "object_id", "measure_id", "id", "enterprise_id", "rectification_plan"):
        assert sensitive not in item


def test_public_hazard_publicity_invalid_token_404(client):
    db = _pub_db(None)
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/public/hazard/bad-token")
    assert resp.status_code == 404
    assert "链接已失效" in resp.json()["detail"]


def test_public_hazard_publicity_scope_filter(client):
    older, newer = _two_records()
    db = _pub_db(_ent(hazard_public_token="pub-token-1"), records=[newer, older])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/public/hazard/pub-token-1", params={"scope": "ongoing"})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert [i["code"] for i in items] == ["HD-002"]


def test_public_hazard_publicity_invalid_scope_422(client):
    db = _pub_db(_ent(hazard_public_token="pub-token-1"), records=[])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/public/hazard/pub-token-1", params={"scope": "foo"})
    assert resp.status_code == 422
    assert "scope 非法" in resp.json()["detail"]


def test_public_hazard_publicity_blank_name_masked(client):
    db = _pub_db(_ent(hazard_public_token="pub-token-1", name="   "), records=[])
    client.app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/public/hazard/pub-token-1")
    assert resp.status_code == 200
    assert resp.json()["data"]["enterprise_name"] == "**"


def test_mask_enterprise_name_rules():
    assert hazard_management._mask_enterprise_name("甲公司") == "甲**"
    assert hazard_management._mask_enterprise_name("A") == "A**"
    assert hazard_management._mask_enterprise_name("  ") == "**"
