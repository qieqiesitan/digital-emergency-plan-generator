"""隐患关联重大危险源单元：字段、迁移、写入校验、筛选与详情。

字段可空是刻意的：多数隐患与重大危险源单元无关（比如配电箱门缺失），
强制关联会逼用户乱选，那样"重大危险源区域隐患数"就不可信了。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.hazard_management import HazardRecord


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _Result:
    def __init__(self, items=None):
        self._items = list(items or [])

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def first(self):
        return self._items[0] if self._items else None


def _ent():
    ent = MagicMock()
    ent.id = "e1"
    ent.user_id = "u1"
    return ent


def _user():
    u = MagicMock()
    u.id = "u1"
    return u


def _record(**kw):
    params = dict(
        enterprise_id="e1",
        code="HD-001",
        source_type="daily",
        title="罐区法兰渗漏",
        description="罐区A 法兰连接处发现渗漏",
    )
    params.update(kw)
    return HazardRecord(**params)


# --- 字段与迁移 -------------------------------------------------------------


def test_hazard_record_has_unit_field_and_is_nullable():
    col = HazardRecord.__table__.columns["major_hazard_unit_id"]
    assert col.nullable is True


def test_model_fk_sets_null_on_unit_delete():
    """单元删除不应连带删除隐患——隐患是独立事实，只解除引用。"""
    import app.models.major_hazard  # noqa: F401  # 注册表，供 FK 解析

    col = HazardRecord.__table__.columns["major_hazard_unit_id"]
    fk = next(iter(col.foreign_keys))
    assert fk.column.table.name == "major_hazard_units"
    assert fk.ondelete == "SET NULL"


def test_migration_declares_column():
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1]
        / "db_migration_20260917_hazard_unit_link.sql"
    ).read_text(encoding="utf-8")
    assert "major_hazard_unit_id" in sql
    assert "ADD COLUMN IF NOT EXISTS" in sql
    assert "ON DELETE SET NULL" in sql, "单元删除不应连带删除隐患"
    assert "CREATE INDEX IF NOT EXISTS" in sql


# --- 序列化与入参 -----------------------------------------------------------


def test_record_dict_includes_unit_id():
    from app.routers.hazard_management import _record_dict

    data = _record_dict(_record(major_hazard_unit_id="mh1"))
    assert data["major_hazard_unit_id"] == "mh1"


def test_record_create_accepts_unit_id():
    from app.routers.hazard_management import RecordCreate

    body = RecordCreate(
        source_type="daily",
        title="t",
        description="d",
        major_hazard_unit_id="mh1",
    )
    assert body.major_hazard_unit_id == "mh1"
    # 不传时为空（可空口径）
    body2 = RecordCreate(source_type="daily", title="t", description="d")
    assert body2.major_hazard_unit_id is None


# --- 写入校验 ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_unit_rejects_cross_enterprise():
    from fastapi import HTTPException

    from app.routers.hazard_management import _validate_major_hazard_unit

    async def execute(stmt, *a, **k):
        # 条件里带了 enterprise_id 过滤，查不到任何行
        return _Result([])

    db = MagicMock()
    db.execute = execute
    with pytest.raises(HTTPException) as ei:
        await _validate_major_hazard_unit(db, enterprise_id="e1", unit_id="mh-x")
    assert ei.value.status_code == 422
    assert "企业" in ei.value.detail


@pytest.mark.asyncio
async def test_validate_unit_passes_when_empty():
    from app.routers.hazard_management import _validate_major_hazard_unit

    async def execute(stmt, *a, **k):  # pragma: no cover - 不应被调用
        raise AssertionError("未提供 unit_id 时不应查询")

    db = MagicMock()
    db.execute = execute
    await _validate_major_hazard_unit(db, enterprise_id="e1", unit_id=None)


# --- 列表筛选 / 详情 --------------------------------------------------------


@pytest.mark.asyncio
async def test_list_records_filters_by_unit():
    from app.routers import hazard_management as hm

    stmts: list[str] = []

    async def execute(stmt, *a, **k):
        text = str(stmt)
        stmts.append(text)
        if "FROM enterprises" in text:
            return _Result([_ent()])
        return _Result([])

    db = MagicMock()
    db.execute = execute
    await hm.list_records(
        enterprise_id="e1",
        status=None,
        level=None,
        source_type=None,
        scope=None,
        q=None,
        major_hazard_unit_id="mh1",
        stats=False,
        current_user=_user(),
        db=db,
    )
    assert any("hazard_records.major_hazard_unit_id" in s for s in stmts)


@pytest.mark.asyncio
async def test_detail_returns_unit_name():
    from app.routers import hazard_management as hm

    record = _record(major_hazard_unit_id="mh1")
    record.id = "r1"

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _Result([_ent()])
        if "FROM hazard_records" in text:
            return _Result([record])
        if "major_hazard_units" in text:
            return _Result(["罐区A"])
        return _Result([])

    db = MagicMock()
    db.execute = execute
    resp = await hm.get_record_detail(
        enterprise_id="e1", rid="r1", current_user=_user(), db=db
    )
    assert resp.data["major_hazard_unit_id"] == "mh1"
    assert resp.data["major_hazard_unit_name"] == "罐区A"


@pytest.mark.asyncio
async def test_detail_unit_name_none_when_unlinked():
    from app.routers import hazard_management as hm

    record = _record()
    record.id = "r2"

    async def execute(stmt, *a, **k):
        text = str(stmt)
        if "FROM enterprises" in text:
            return _Result([_ent()])
        if "FROM hazard_records" in text:
            return _Result([record])
        return _Result([])

    db = MagicMock()
    db.execute = execute
    resp = await hm.get_record_detail(
        enterprise_id="e1", rid="r2", current_user=_user(), db=db
    )
    assert resp.data["major_hazard_unit_name"] is None
