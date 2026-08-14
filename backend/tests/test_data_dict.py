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


import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.data_dict_service import get_dict_map, invalidate_dict_cache
from app.models.data_dict import DataDict

@pytest.mark.asyncio
async def test_enterprise_overrides_system():
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
    db = MagicMock()
    db.execute = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        DataDict(dict_type="measure_factors", code="ppe", label="个体防护",
                 value={"factor": 0.85}, scope="system", enabled=False, is_system=True),
    ]
    db.execute.return_value = result
    merged = await get_dict_map(db, "ent-1", "measure_factors")
    assert "ppe" not in merged


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
