import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.data_dict_service import get_dict_map, invalidate_dict_cache
from app.models.data_dict import DataDict

def test_data_dict_table_metadata():
    assert DataDict.__tablename__ == "data_dicts"
    cols = DataDict.__table__.columns
    assert "id" in cols and "dict_type" in cols and "code" in cols and "value" in cols
    assert cols["enterprise_id"].nullable
    assert any(getattr(c, "name", None) == "uq_data_dicts_type_ent_code"
               for c in DataDict.__table__.constraints)

def test_data_dict_model_construct():
    row = DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                   value={"factor": 0.5}, scope="system", is_system=True)
    assert row.value["factor"] == 0.5
    assert row.enabled is True
    assert DataDict(enabled=False).enabled is False


@pytest.mark.asyncio
async def test_enterprise_overrides_system():
    invalidate_dict_cache("ent-1", "measure_factors")
    db = MagicMock()
    db.execute = AsyncMock()
    rows = [
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.5}, scope="system", is_system=True),
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.3}, scope="enterprise", enterprise_id="ent-1"),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result
    merged = await get_dict_map(db, "ent-1", "measure_factors")
    assert merged["engineering"]["value"]["factor"] == 0.3

@pytest.mark.asyncio
async def test_disabled_entry_excluded():
    invalidate_dict_cache("ent-1", "measure_factors")
    db = MagicMock()
    db.execute = AsyncMock()
    result = MagicMock()
    # 真实数据库按 enabled.is_(True) 过滤禁用行，mock 仅模拟过滤后的启用行
    result.scalars.return_value.all.return_value = [
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.5}, scope="system", enabled=True, is_system=True),
    ]
    db.execute.return_value = result
    merged = await get_dict_map(db, "ent-1", "measure_factors")
    # 真实验证：缓存已清理，查询确实执行（非命中缓存），且语句携带 enabled 过滤条件
    db.execute.assert_awaited_once()
    assert "enabled" in str(db.execute.await_args.args[0])
    assert merged["engineering"]["value"]["factor"] == 0.5


@pytest.mark.asyncio
async def test_enterprise_wins_regardless_of_row_order():
    invalidate_dict_cache("ent-1", "measure_factors")
    db = MagicMock()
    db.execute = AsyncMock()
    rows = [
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.3}, scope="enterprise", enterprise_id="ent-1"),
        DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                 value={"factor": 0.5}, scope="system", is_system=True),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute.return_value = result
    merged = await get_dict_map(db, "ent-1", "measure_factors")
    assert merged["engineering"]["value"]["factor"] == 0.3
