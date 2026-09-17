"""调用留痕服务测试：写入成功、失败不影响主流程。"""

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.llm_telemetry import LlmCallRecord, record_call

BACKEND = Path(__file__).resolve().parents[1]
SQL = (BACKEND / "db_migration_20260917_llm_call_log.sql").read_text(encoding="utf-8")


def _db():
    db = MagicMock()
    added: list = []
    db.add = lambda obj: added.append(obj)
    db.commit = AsyncMock()
    db._added = added
    return db


@pytest.mark.asyncio
async def test_record_call_persists_row():
    db = _db()
    await record_call(
        db,
        LlmCallRecord(
            module="major_hazard",
            capability="extract",
            model="deepseek-chat",
            duration_ms=1234,
            success=True,
            total_tokens=456,
        ),
    )
    assert len(db._added) == 1, "必须写入一条留痕"
    row = db._added[0]
    assert row.module == "major_hazard"
    assert row.capability == "extract"
    assert row.duration_ms == 1234
    assert row.success is True
    assert row.total_tokens == 456
    assert row.truncated is False
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_record_call_swallows_db_failure():
    """留痕是 best-effort：写库炸了也绝不能把业务请求带崩。"""
    db = _db()
    db.commit = AsyncMock(side_effect=RuntimeError("db down"))
    await record_call(db, LlmCallRecord(module="m", capability="c", model="x"))


@pytest.mark.asyncio
async def test_record_call_marks_failure_and_retry():
    db = _db()
    await record_call(
        db,
        LlmCallRecord(
            module="m",
            capability="c",
            model="x",
            success=False,
            error_code=429,
            error_message="rate limited",
            retry_count=3,
            truncated=True,
        ),
    )
    row = db._added[0]
    assert row.success is False
    assert row.error_code == 429
    assert row.retry_count == 3
    assert row.truncated is True


@pytest.mark.asyncio
async def test_record_call_truncates_long_error_message():
    """错误消息截断到 2000 字符，避免一条异常把表撑爆。"""
    db = _db()
    await record_call(
        db,
        LlmCallRecord(module="m", capability="c", model="x", error_message="x" * 5000),
    )
    assert len(db._added[0].error_message) <= 2000


def test_migration_sql_declares_table():
    assert re.search(r"CREATE TABLE IF NOT EXISTS\s+llm_call_logs\b", SQL)
    for col in ("module", "capability", "model", "duration_ms", "success", "truncated"):
        assert col in SQL, col


def test_migration_indexes_for_stats_queries():
    """统计按 module+时间、按时间查，两个索引都要有。"""
    assert re.search(r"INDEX[^\n]*llm_call_logs\s*\(module,\s*created_at\)", SQL, re.I)
    assert re.search(r"INDEX[^\n]*llm_call_logs\s*\(created_at\)", SQL, re.I)
