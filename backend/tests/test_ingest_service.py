"""接入服务：幂等键、条目创建、确认入库、任务计数。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ingest_service import (
    IngestError,
    build_idempotency_key,
    confirm_items,
    create_item,
    register_target_writer,
    skip_items,
    update_job_counts,
)


def _db(existing=None):
    added: list = []
    db = MagicMock()
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = existing
        # 默认没有需要回填计数的任务（避免迭代 MagicMock）
        res.scalars.return_value.all.return_value = []
        return res

    db.execute = execute
    db._added = added
    return db


def test_idempotency_key_is_stable_and_source_scoped():
    a = build_idempotency_key(source_id="s1", target="chem", external_id="P12-3")
    b = build_idempotency_key(source_id="s1", target="chem", external_id="P12-3")
    c = build_idempotency_key(source_id="s2", target="chem", external_id="P12-3")
    assert a == b, "同源同键必须稳定"
    assert a != c, "不同来源不能撞键"
    assert len(a) <= 300


def test_idempotency_key_without_external_id_uses_payload_hash():
    k1 = build_idempotency_key(source_id="s1", target="t", external_id=None, payload={"a": 1})
    k2 = build_idempotency_key(source_id="s1", target="t", external_id=None, payload={"a": 1})
    k3 = build_idempotency_key(source_id="s1", target="t", external_id=None, payload={"a": 2})
    assert k1 == k2
    assert k1 != k3


def test_idempotency_key_requires_identifiable_input():
    with pytest.raises(IngestError):
        build_idempotency_key(source_id="s1", target="t", external_id=None, payload=None)


@pytest.mark.asyncio
async def test_create_item_skips_duplicate():
    existing = MagicMock()
    existing.id = "i1"
    db = _db(existing=existing)
    out = await create_item(
        db, job_id="j1", idempotency_key="k1", raw_payload={"a": 1}, target_entity="t"
    )
    assert out["created"] is False
    assert out["item_id"] == "i1"
    assert db._added == [], "重复键不得新增行"


@pytest.mark.asyncio
async def test_create_item_inserts_new_as_pending():
    db = _db(existing=None)
    out = await create_item(
        db,
        job_id="j1",
        idempotency_key="k2",
        raw_payload={"a": 1},
        target_entity="t",
        source_locator="报告.pdf P12",
        confidence="high",
    )
    assert out["created"] is True
    row = db._added[0]
    assert row.status == "pending", "新条目一律先进待确认队列"
    assert row.raw_payload == {"a": 1}
    assert row.source_locator == "报告.pdf P12"
    assert row.confidence == "high"


@pytest.mark.asyncio
async def test_confirm_items_only_processes_selected():
    """只入库被选中的条目——"整批默认全选 + 勾掉错的"的代码落点。"""
    item_ok = MagicMock()
    item_ok.id = "i1"
    item_ok.status = "pending"
    item_ok.target_entity = "unit_chemical"
    item_ok.raw_payload = {"chemical_name": "氯"}
    item_skip = MagicMock()
    item_skip.id = "i2"
    item_skip.status = "pending"

    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        # SQLAlchemy 默认用绑定参数，str(stmt) 看不到 id 值；
        # 用 literal_binds 把值内联后再判断，才能按 id 区分返回对象。
        rendered = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        res = MagicMock()
        res.scalar_one_or_none.return_value = item_ok if "i1" in rendered else item_skip
        res.scalars.return_value.all.return_value = []
        return res

    db.execute = execute

    async def _writer(dbc, payload, item):
        return "target-1"

    register_target_writer("unit_chemical", _writer)
    out = await confirm_items(db, item_ids=["i1"], approved_by="user1")

    assert out["confirmed"] == 1
    assert item_ok.status == "imported"
    assert item_ok.target_id == "target-1"
    assert item_ok.reviewed_by == "user1"
    assert item_skip.status == "pending", "未被选中的条目状态不变"


@pytest.mark.asyncio
async def test_confirm_items_rejects_already_reviewed():
    done = MagicMock()
    done.id = "i1"
    done.status = "imported"
    db = _db(existing=done)
    with pytest.raises(IngestError):
        await confirm_items(db, item_ids=["i1"], approved_by="u1")


@pytest.mark.asyncio
async def test_confirm_items_isolates_single_failure():
    """单条入库失败不能让整批回滚——失败的留在队列里可重试。"""
    bad = MagicMock()
    bad.id = "bad1"
    bad.status = "pending"
    bad.target_entity = "unit_chemical"
    bad.raw_payload = {}

    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalar_one_or_none.return_value = bad
        return res

    db.execute = execute

    async def _boom(dbc, payload, item):
        raise RuntimeError("目标表约束冲突")

    register_target_writer("unit_chemical", _boom)
    out = await confirm_items(db, item_ids=["bad1"], approved_by="u1")
    assert out["confirmed"] == 0
    assert out["failed"][0]["item_id"] == "bad1"
    assert bad.status == "failed"
    assert "约束冲突" in bad.error


@pytest.mark.asyncio
async def test_update_job_counts_derives_from_items():
    counts = {"pending": 3, "imported": 5, "skipped": 1, "failed": 2}
    db = MagicMock()
    db.commit = AsyncMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.all.return_value = list(counts.items())
        return res

    db.execute = execute
    job = MagicMock()
    job.id = "j1"
    out = await update_job_counts(db, job=job)
    assert out["total"] == 11
    assert out["pending_review"] == 3
    assert out["imported"] == 5
    assert job.status == "partial", "有失败项时任务状态为 partial"


@pytest.mark.asyncio
async def test_skip_items_marks_skipped_without_deleting():
    """跳过是标记不是删除——raw_payload 永久保留，"为什么没入库"也要有答案。"""
    item = MagicMock()
    item.id = "i1"
    item.status = "pending"
    db = _db(existing=item)
    out = await skip_items(db, item_ids=["i1"], reviewed_by="u1")
    assert out["skipped"] == 1
    assert item.status == "skipped"
    assert item.reviewed_by == "u1"


@pytest.mark.asyncio
async def test_skip_items_rejects_already_reviewed():
    done = MagicMock()
    done.id = "i1"
    done.status = "imported"
    db = _db(existing=done)
    with pytest.raises(IngestError):
        await skip_items(db, item_ids=["i1"], reviewed_by="u1")


@pytest.mark.asyncio
async def test_skip_items_requires_selection():
    db = _db(existing=None)
    with pytest.raises(IngestError):
        await skip_items(db, item_ids=[], reviewed_by="u1")


@pytest.mark.asyncio
async def test_skip_items_refreshes_job_counts():
    """跳过之后任务计数必须同步，否则列表页一直显示旧的"待确认 N 条"。"""
    item = MagicMock()
    item.id = "i1"
    item.job_id = "j1"
    item.status = "pending"
    job = MagicMock()
    job.id = "j1"

    db = MagicMock()
    db.commit = AsyncMock()
    calls: list[str] = []

    async def execute(stmt, *a, **k):
        calls.append(str(stmt))
        res = MagicMock()
        if len(calls) == 1:
            res.scalar_one_or_none.return_value = item
        elif len(calls) == 2:
            res.scalars.return_value.all.return_value = [job]
        else:
            res.all.return_value = [("skipped", 1)]
        return res

    db.execute = execute
    out = await skip_items(db, item_ids=["i1"], reviewed_by="u1")
    assert out["skipped"] == 1
    assert job.skipped == 1
    assert job.pending_review == 0
    assert db.commit.await_count == 2
