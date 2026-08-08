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
