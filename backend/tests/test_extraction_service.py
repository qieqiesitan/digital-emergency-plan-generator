"""抽取服务：解析模型输出、常量表复核、落队列。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.extraction_service import (
    extract_candidates,
    parse_model_json,
    reconcile_with_constants,
)


def test_parse_model_json_tolerates_code_fence():
    raw = '```json\n[{"payload": {"name": "罐区A"}, "confidence": "high"}]\n```'
    rows = parse_model_json(raw)
    assert rows[0]["payload"]["name"] == "罐区A"


def test_parse_model_json_handles_single_object():
    rows = parse_model_json('{"payload": {"name": "X"}, "confidence": "high"}')
    assert len(rows) == 1


def test_parse_model_json_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_model_json("模型今天不想干活")


def _cq(name, q):
    c = MagicMock()
    c.chemical_name = name
    c.critical_t = q
    return c


def _beta(name=None, beta="4.0", table="3"):
    b = MagicMock()
    b.chemical_name = name
    b.beta = beta
    b.source_table = table
    return b


def test_reconcile_fills_q_and_beta_from_constants():
    """模型给的 Q/beta 一律不采信；能查表就填表值。"""
    row = {
        "chemical_name": "氯",
        "q_design_max": 5.0,
        "critical_quantity_t": 999.0,
        "beta": 1.0,
        "source_locator": "报告.pdf 段1",
        "confidence": "high",
    }
    out = reconcile_with_constants(
        row, critical_rows=[_cq("氯", 5)], beta_rows=[_beta(name="氯", beta="4.0")]
    )
    assert out["critical_quantity_t"] == 5
    assert out["beta"] == 4.0
    assert out["confidence"] == "high"


def test_reconcile_downgrades_when_not_found():
    row = {
        "chemical_name": "某种混合物",
        "q_design_max": 3.0,
        "critical_quantity_t": 1.0,
        "beta": 2.0,
        "source_locator": "报告.pdf 段9",
        "confidence": "high",
    }
    out = reconcile_with_constants(row, critical_rows=[], beta_rows=[])
    assert out["critical_quantity_t"] is None
    assert out["beta"] is None
    assert out["confidence"] == "low", "查不到法定值时必须降级"
    assert "临界量" in out["review_note"]


def _empty_db():
    db = MagicMock()

    async def execute(stmt, *a, **k):
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    db.execute = execute
    return db


@pytest.mark.asyncio
async def test_extract_candidates_writes_pending_items():
    ai_json = json.dumps(
        [
            {
                "payload": {"chemical_name": "氯", "q_design_max": 5},
                "source_locator": "报告.pdf 段1",
                "confidence": "high",
            }
        ],
        ensure_ascii=False,
    )
    created: list = []

    async def fake_create(db, **kwargs):
        created.append(kwargs)
        return {"created": True, "item_id": "i1"}

    with patch(
        "app.services.extraction_service.llm_text_completion",
        new=AsyncMock(return_value=ai_json),
    ), patch("app.services.extraction_service.create_item", side_effect=fake_create):
        out = await extract_candidates(
            _empty_db(),
            job_id="j1",
            source_id="s1",
            target_entity="major_hazard_unit_chemical",
            text="罐区A 储存氯 5 吨",
            filename="报告.pdf",
            ai_config=MagicMock(),
        )

    assert out["queued"] == 1
    assert created[0]["target_entity"] == "major_hazard_unit_chemical"
    assert created[0]["source_locator"] == "报告.pdf 段1"


@pytest.mark.asyncio
async def test_extract_candidates_skips_invalid_rows():
    """单条结构不合法只跳过该条，不让整批抽取失败。"""
    ai_json = json.dumps(
        [
            {"payload": {"chemical_name": "氯", "q_design_max": 5}, "source_locator": "a", "confidence": "high"},
            {"payload": {"chemical_name": "缺数量"}, "source_locator": "b", "confidence": "high"},
        ],
        ensure_ascii=False,
    )
    calls: list = []

    async def fake_create(db, **kwargs):
        calls.append(kwargs)
        return {"created": True, "item_id": "i"}

    with patch(
        "app.services.extraction_service.llm_text_completion",
        new=AsyncMock(return_value=ai_json),
    ), patch("app.services.extraction_service.create_item", side_effect=fake_create):
        out = await extract_candidates(
            _empty_db(),
            job_id="j1",
            source_id="s1",
            target_entity="major_hazard_unit_chemical",
            text="x",
            filename="报告.pdf",
            ai_config=MagicMock(),
        )

    assert out["queued"] == 1
    assert out["invalid"] == 1
