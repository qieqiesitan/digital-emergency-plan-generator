"""目标实体写入器：把确认后的载荷写进正式表。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ingest_service import TARGET_WRITERS
from app.services.ingest_writers import register_default_writers


def test_register_default_writers_registers_two_targets():
    register_default_writers()
    assert "major_hazard_unit" in TARGET_WRITERS
    assert "major_hazard_unit_chemical" in TARGET_WRITERS


@pytest.mark.asyncio
async def test_unit_writer_requires_enterprise_id():
    """缺 enterprise_id 时明确报错——单元必须挂在企业下。"""
    register_default_writers()
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    with pytest.raises(Exception) as ei:
        await TARGET_WRITERS["major_hazard_unit"](db, {"name": "罐区A", "unit_type": "storage"}, MagicMock())
    assert "enterprise" in str(ei.value).lower()


@pytest.mark.asyncio
async def test_unit_chemical_writer_requires_existing_unit():
    """按 unit_name 找单元；找不到明确报错，不静默丢弃。"""
    register_default_writers()
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.all.return_value = []
        return res

    db.execute = execute
    with pytest.raises(Exception) as ei:
        await TARGET_WRITERS["major_hazard_unit_chemical"](
            db,
            {"unit_name": "不存在的单元", "chemical_name": "氯", "q_design_max": 5},
            MagicMock(),
        )
    assert "单元" in str(ei.value)


@pytest.mark.asyncio
async def test_unit_chemical_writer_rejects_ambiguous_same_name():
    """多企业同名单元时明确报错并提示补 enterprise_id——不猜、不崩。"""
    register_default_writers()
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
        return res

    db.execute = execute
    with pytest.raises(Exception) as ei:
        await TARGET_WRITERS["major_hazard_unit_chemical"](
            db,
            {"unit_name": "罐区A", "chemical_name": "氯", "q_design_max": 5},
            MagicMock(),
        )
    assert "enterprise_id" in str(ei.value)
    assert "2" in str(ei.value)


@pytest.mark.asyncio
async def test_unit_chemical_writer_narrows_by_enterprise():
    """载荷带 enterprise_id 时按企业收敛，单命中即写入。"""
    register_default_writers()
    unit = MagicMock()
    unit.id = "unit-1"
    captured: list[str] = []

    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()

    async def execute(stmt, *a, **k):
        captured.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
        res = MagicMock()
        res.scalars.return_value.all.return_value = [unit]
        return res

    db.execute = execute
    await TARGET_WRITERS["major_hazard_unit_chemical"](
        db,
        {
            "unit_name": "罐区A",
            "enterprise_id": "e1",
            "chemical_name": "氯",
            "q_design_max": 5,
            "critical_quantity_t": 5,
            "beta": 4,
        },
        MagicMock(),
    )
    # mock 环境不会生成 row.id；这里验证的是"按企业收敛"这一步确实发生在 SQL 里
    assert captured, "应查询归属单元"
    assert "enterprise_id" in captured[0]
