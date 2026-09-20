"""D-2：危化品台账是事实源，企业档案文本是派生摘要。

覆盖：摘要生成规则、台账为空时保留手填文本、台账写入端点自动重算档案文本、
以及台账 AI 引导的「档案自述」交叉校验块。修复前应失败。
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.dependencies import get_current_user
from app.main import app
from app.models.enterprise import Enterprise
from app.models.hazardous_chemicals import HazardousChemical
from app.models.user import User
from app.services.chemical_summary import (
    archive_text_block,
    build_chemicals_summary,
    sync_enterprise_chemicals_summary,
)


class _Rows:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows if rows is not None else []

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        m = MagicMock()
        m.all.return_value = self._rows
        return m

    def all(self):
        return self._rows


def _chem(name, cas=None, amount=None, unit=None, max_storage=None):
    return HazardousChemical(
        id=f"c-{name}", enterprise_id="e1", name=name, cas_no=cas,
        storage_amount=Decimal(str(amount)) if amount is not None else None,
        storage_unit=unit, max_storage=max_storage,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )


# ---------- 摘要生成规则 ----------

def test_summary_lists_names_with_cas_and_storage():
    text = build_chemicals_summary([
        _chem("乙醇（酒精）", cas="64-17-5", amount=5, unit="t"),
        _chem("氢气"),
    ])
    assert text.startswith("共 2 种：")
    assert "乙醇（酒精）（CAS 64-17-5，储量 5 t）" in text
    assert "氢气" in text


def test_summary_falls_back_to_max_storage_text():
    text = build_chemicals_summary([_chem("甲醇", max_storage="2 吨")])
    assert "最大储存量 2 吨" in text


def test_summary_empty_for_no_rows():
    assert build_chemicals_summary([]) == ""


def test_summary_truncates_long_ledger():
    rows = [_chem(f"品种{i:02d}") for i in range(45)]
    text = build_chemicals_summary(rows)
    assert text.startswith("共 45 种：")
    assert text.endswith("等 45 种")
    assert len(text) <= 2000


# ---------- 同步规则 ----------

def test_sync_overwrites_archive_text_when_ledger_present():
    db = AsyncMock()
    ent = Enterprise(id="e1", user_id="u1", name="企业", hazardous_chemicals="无")
    db.execute.side_effect = [_Rows(rows=[_chem("次氯酸钠溶液")]), _Rows(scalar=ent)]

    out = asyncio.run(sync_enterprise_chemicals_summary(db, "e1"))

    assert out and "次氯酸钠溶液" in out
    assert ent.hazardous_chemicals == out
    assert ent.hazardous_chemicals != "无"


def test_sync_keeps_manual_text_when_ledger_empty():
    db = AsyncMock()
    ent = Enterprise(id="e1", user_id="u1", name="企业", hazardous_chemicals="手填：少量乙醇")
    db.execute.side_effect = [_Rows(rows=[]), _Rows(scalar=ent)]

    assert asyncio.run(sync_enterprise_chemicals_summary(db, "e1")) is None
    assert ent.hazardous_chemicals == "手填：少量乙醇"


def test_sync_noop_when_already_equal():
    db = AsyncMock()
    summary = build_chemicals_summary([_chem("氢气")])
    ent = Enterprise(id="e1", user_id="u1", name="企业", hazardous_chemicals=summary)
    db.execute.side_effect = [_Rows(rows=[_chem("氢气")]), _Rows(scalar=ent)]

    assert asyncio.run(sync_enterprise_chemicals_summary(db, "e1")) is None


# ---------- 档案自述交叉校验块 ----------

def test_archive_text_block_marks_missing_and_mismatch():
    blank = archive_text_block(Enterprise(id="e1", user_id="u1", name="企业"))
    assert "（未填写）" in blank
    filled = archive_text_block(Enterprise(id="e1", user_id="u1", name="企业",
                                           hazardous_chemicals="无"))
    assert "企业档案自述危险化学品：无" in filled
    assert "以台账为准" in filled


# ---------- 台账写入端点自动重算档案文本 ----------

def _create_db():
    db = AsyncMock()
    ent = Enterprise(id="e1", user_id="u1", name="测试企业", hazardous_chemicals="无")
    created = _chem("次氯酸钠溶液", cas="1310-73-2")

    def fake_execute(stmt, *a, **kw):
        t = str(stmt)
        if "FROM hazardous_chemicals" in t:
            return _Rows(rows=[created], scalar=created)
        if "FROM enterprises" in t:
            return _Rows(scalar=ent)
        return _Rows(scalar=None, rows=[])

    db.execute.side_effect = fake_execute

    async def _refresh(obj, *a, **kw):
        # 模拟数据库行为：refresh 后必须有 id（ORM default）与时间戳（server_default）
        now = datetime.now(timezone.utc)
        if getattr(obj, "id", None) is None:
            obj.id = str(uuid4())
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now

    db.refresh.side_effect = _refresh
    return db, ent


def test_create_chemical_refreshes_archive_text():
    db, ent = _create_db()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="u@t.com", role="user", password_hash="x"
    )
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = asyncio.run(_post("/api/v1/enterprises/e1/chemicals",
                                 {"name": "次氯酸钠溶液", "cas_no": "1310-73-2"}))
        assert resp.status_code in (200, 201), resp.text
        assert ent.hazardous_chemicals != "无", "台账新增后台账应重算档案文本（消除双源矛盾）"
        assert "次氯酸钠溶液" in ent.hazardous_chemicals
        assert db.flush.await_count >= 1, "重算前必须先 flush，否则查不到刚加的台账行"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


async def _post(path: str, body: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(path, json=body)
