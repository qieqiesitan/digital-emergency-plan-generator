import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from app.models.hazardous_chemicals import HazardousChemical
from app.routers import hazardous_chemicals as hc
from app.schemas.hazardous_chemicals import HazardousChemicalCreate, HazardousChemicalUpdate


def _db_with_ent(ent):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    db.execute.return_value = result
    return db


async def _fake_refresh(obj):
    # 模拟真实 DB refresh：回填服务端生成的 id / 时间戳
    if obj.id is None:
        obj.id = "chem-new"
    if obj.created_at is None:
        obj.created_at = datetime.now()
    if obj.updated_at is None:
        obj.updated_at = datetime.now()


@pytest.mark.asyncio
async def test_create_carries_library_id():
    ent = MagicMock(id="ent-1", user_id="u1")
    db = _db_with_ent(ent)
    db.add = MagicMock()  # Session.add 为同步方法
    db.refresh = AsyncMock(side_effect=_fake_refresh)
    body = HazardousChemicalCreate(name="乙醇", cas_no="67-56-1", library_id="lib-9")
    # _get_enterprise 内部 execute().scalar_one_or_none()
    db.execute.return_value = result = MagicMock()
    result.scalar_one_or_none.return_value = ent
    resp = await hc.create_chemical("ent-1", body, MagicMock(id="u1"), db)
    added: HazardousChemical = db.add.call_args[0][0]
    assert added.library_id == "lib-9"
    assert resp.data.library_id == "lib-9"


@pytest.mark.asyncio
async def test_update_preserves_library_id():
    chem = HazardousChemical(
        id="chem-1",
        enterprise_id="ent-1",
        name="乙醇",
        library_id="lib-9",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=lambda: chem)
    body = HazardousChemicalUpdate(location="2#仓库")
    resp = await hc.update_chemical("ent-1", "chem-1", body, MagicMock(id="u1"), db)
    assert resp.data.library_id == "lib-9"
