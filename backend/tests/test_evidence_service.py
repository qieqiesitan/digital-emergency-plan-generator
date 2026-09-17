"""依据层服务测试：挂条文、查条文、幂等。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.evidence_service import (
    EvidenceInput,
    attach_evidence,
    list_evidence,
)


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


def _db(existing=None):
    added = []
    db = MagicMock()
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        return _Result(existing or [])

    db.execute = execute
    db._added = added
    return db


@pytest.mark.asyncio
async def test_attach_evidence_creates_rows():
    db = _db()
    await attach_evidence(
        db,
        owner_type="major_hazard_unit",
        owner_id="u1",
        items=[
            EvidenceInput(
                regulation_id="gb18218",
                article_anchor="GB 18218-2018 4.2.1",
                note="辨识指标",
            )
        ],
        user_id="user1",
    )
    assert len(db._added) == 1
    row = db._added[0]
    assert row.owner_type == "major_hazard_unit"
    assert row.owner_id == "u1"
    assert row.article_anchor == "GB 18218-2018 4.2.1"
    assert row.relation == "依据"


@pytest.mark.asyncio
async def test_attach_evidence_is_idempotent():
    """同一 owner + 同一条文锚点重复挂载时不产生重复行。"""
    existing = MagicMock()
    existing.id = "ex1"
    existing.owner_type = "major_hazard_unit"
    existing.owner_id = "u1"
    existing.article_anchor = "GB 18218-2018 4.2.1"
    existing.relation = "依据"
    db = _db(existing=[existing])
    await attach_evidence(
        db,
        owner_type="major_hazard_unit",
        owner_id="u1",
        items=[EvidenceInput(regulation_id="gb18218", article_anchor="GB 18218-2018 4.2.1")],
    )
    assert db._added == [], "重复挂载不应新增行"


@pytest.mark.asyncio
async def test_attach_evidence_rejects_empty_owner():
    db = _db()
    with pytest.raises(ValueError):
        await attach_evidence(db, owner_type="", owner_id="u1", items=[])


@pytest.mark.asyncio
async def test_list_evidence_returns_rows():
    row = MagicMock()
    row.id = "ex1"
    row.article_anchor = "GB 18218-2018 4.3.2"
    row.regulation_id = "gb18218"
    row.relation = "依据"
    row.note = "分级指标"
    db = _db(existing=[row])
    out = await list_evidence(db, owner_type="major_hazard_unit", owner_id="u1")
    assert out[0]["article_anchor"] == "GB 18218-2018 4.3.2"


def test_evidence_migration_sql_declares_table():
    import re
    from pathlib import Path

    sql = (
        Path(__file__).resolve().parents[1] / "db_migration_20260917_major_hazard.sql"
    ).read_text(encoding="utf-8")
    assert re.search(r"CREATE TABLE IF NOT EXISTS\s+evidence_refs\b", sql)
    assert "uq_evidence_owner_anchor" in sql
