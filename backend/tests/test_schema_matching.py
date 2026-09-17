"""列映射建议：AI 建议 + 白名单过滤 + 兜底精确匹配。"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.schema_matching import suggest_mapping, validate_mapping


def test_validate_mapping_drops_unknown_targets():
    """只保留目标实体允许的字段——防止把任意字段写进业务表。"""
    out = validate_mapping(
        "major_hazard_unit_chemical",
        {"品名": "chemical_name", "数量": "q_design_max", "胡写": "evil_field"},
    )
    assert out == {"品名": "chemical_name", "数量": "q_design_max"}


def test_validate_mapping_drops_duplicate_targets():
    """两个源列映射到同一目标字段时，保留第一个，避免歧义。"""
    out = validate_mapping(
        "major_hazard_unit_chemical",
        {"品名": "chemical_name", "名称": "chemical_name"},
    )
    assert out == {"品名": "chemical_name"}


@pytest.mark.asyncio
async def test_suggest_mapping_falls_back_to_exact_match_on_ai_failure():
    """AI 不可用时退回精确匹配，不能整体失败——映射本来就是人工确认的。"""
    with patch(
        "app.services.schema_matching.llm_text_completion",
        new=AsyncMock(side_effect=RuntimeError("AI 挂了")),
    ):
        out = await suggest_mapping(
            headers=["chemical_name", "q_design_max", "备注"],
            target_entity="major_hazard_unit_chemical",
            ai_config=None,
        )
    assert out["mapping"]["chemical_name"] == "chemical_name"
    assert out["mapping"]["q_design_max"] == "q_design_max"
    assert out["source"] == "exact"


@pytest.mark.asyncio
async def test_suggest_mapping_returns_ai_result_when_available():
    import json

    ai = json.dumps({"品名": "chemical_name", "设计最大量": "q_design_max"}, ensure_ascii=False)
    with patch(
        "app.services.schema_matching.llm_text_completion",
        new=AsyncMock(return_value=ai),
    ):
        out = await suggest_mapping(
            headers=["品名", "设计最大量"],
            target_entity="major_hazard_unit_chemical",
            ai_config=object(),
        )
    assert out["source"] == "ai"
    assert out["mapping"]["品名"] == "chemical_name"
