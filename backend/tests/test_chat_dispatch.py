"""chat_dispatch 收尾回归测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.chat_dispatch import (
    _delegate_generic,
    _ErrorDict,
    _list_resources,
    _update_enterprise,
    _delete_plan,
    dispatch,
)


@pytest.mark.asyncio
async def test_delegate_generic_returns_error_data_on_erroDict():
    async def op(db, user, args, cfg):
        raise _ErrorDict({"error": "企业不存在或无权访问", "verified": False})

    out = await _delegate_generic(op, AsyncMock(), MagicMock(), {}, {})
    assert out == {"error": "企业不存在或无权访问", "verified": False}


@pytest.mark.asyncio
async def test_delegate_generic_passthrough():
    async def op(db, user, args, cfg):
        return {"id": "1", "verified": True}

    assert await _delegate_generic(op, AsyncMock(), MagicMock(), {}, {}) == {"id": "1", "verified": True}


@pytest.mark.asyncio
async def test_list_resources_requires_enterprise_id():
    out = await _list_resources(AsyncMock(), MagicMock(id="u1"), {})
    assert out == {"error": "请提供 enterprise_id", "verified": False}


@pytest.mark.asyncio
async def test_update_enterprise_delegates_generic():
    db = AsyncMock()
    ent = MagicMock(id="e1", name="企业A")
    result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    db.execute.return_value = result
    out = await _update_enterprise(db, MagicMock(id="u1"), {"enterprise_id": "e1", "name": "企业B"})
    assert out["verified"] is True
    assert ent.name == "企业B"


@pytest.mark.asyncio
async def test_delete_plan_missing_id():
    out = await _delete_plan(AsyncMock(), MagicMock(id="u1"), {})
    assert out["error"] == "请提供 plan_id"


@pytest.mark.asyncio
async def test_dispatch_unknown_function():
    out = await dispatch(AsyncMock(), MagicMock(id="u1"), "no_such_fn", {})
    assert "未知操作" in out


def test_enterprise_response_dedup_fields():
    from app.schemas.enterprise import EnterpriseBase, EnterpriseResponse
    base = EnterpriseBase.model_fields
    resp = EnterpriseResponse.model_fields
    # 5 个同类型字段不再被 Response 重新声明：注解与 Base 完全一致
    for f in ["last_plan_filing_authority", "building_overview", "floor_plan_url", "gis_lat", "gis_lng"]:
        assert f in resp
        assert resp[f].annotation is base[f].annotation
    # 3 个日期字段保留覆盖：类型不同（输出序列化格式）
    for f in ["established_date", "fire_approval_date", "last_plan_filing_date"]:
        assert resp[f].annotation is not base[f].annotation


@pytest.mark.asyncio
async def test_list_enterprises_keyword_search():
    from app.services.chat_dispatch import _list_enterprises
    db = AsyncMock()
    ent = MagicMock(id="e1")
    ent.name = "宝岳"
    ent.industry = "科技"
    ent.address = "西安"
    ent.plans = []
    result = MagicMock()
    result.scalars.return_value.all.return_value = [ent]
    db.execute.return_value = result
    out = await _list_enterprises(db, MagicMock(id="u1"), {"keyword": "宝岳"})
    assert out["enterprises"][0]["name"] == "宝岳"


@pytest.mark.asyncio
async def test_create_enterprise_dedup():
    from app.services.chat_dispatch import _create_enterprise
    db = AsyncMock()
    existing = MagicMock(id="e1")
    existing.name = "宝岳"
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    db.execute.return_value = result
    out = await _create_enterprise(db, MagicMock(id="u1"), {"name": "宝岳"})
    assert out == {"id": "e1", "name": "宝岳", "message": "企业已存在，无需重复创建", "verified": True}


@pytest.mark.asyncio
async def test_create_plan_with_template(monkeypatch):
    from app.services.chat_dispatch import _create_plan
    db = AsyncMock()
    ent = MagicMock(id="e1")
    tmpl = MagicMock(structure=[{"section_key": "sec_1", "title": "总则"}])
    results = [
        MagicMock(scalar_one_or_none=lambda: ent),     # Enterprise
        MagicMock(scalar_one_or_none=lambda: tmpl),    # PlanTemplate
    ]
    db.execute = AsyncMock(side_effect=results)
    added = {}

    def fake_add(obj):
        added["obj"] = obj

    db.add = fake_add
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    created = {}

    def fake_create_sections(db, plan_id, structure):
        created["plan_id"] = plan_id
        created["structure"] = structure

    monkeypatch.setattr("app.routers.plans._create_sections_from_template", fake_create_sections)
    out = await _create_plan(db, MagicMock(id="u1"), {
        "enterprise_id": "e1", "title": "预案A", "plan_type": "comprehensive",
    })
    assert out["id"] == added["obj"].id
    assert created["plan_id"] == out["id"]
    assert created["structure"] == tmpl.structure
