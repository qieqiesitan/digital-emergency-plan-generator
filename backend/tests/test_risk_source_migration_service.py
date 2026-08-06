import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.risk_source_migration_service import (
    build_default_mapping,
    execute_migration,
    split_control_measures,
)


def test_split_control_measures_supports_common_delimiters():
    text = "巡检；安装报警\n定期演练; 清理"
    result = split_control_measures(text)
    assert len(result) == 4
    assert "安装报警" in result


def test_default_mapping_uses_source_fields():
    src = MagicMock()
    src.id = "src-1"
    src.name = "火灾"
    src.categories = "火灾,电气"
    src.location = "仓库东区"
    src.likelihood = 4
    src.severity = 5
    src.control_measures = "定期巡检"

    item = build_default_mapping(src)

    assert item["suggested_object"] == "火灾"
    assert item["suggested_event"] == "火灾"
    assert item["source_categories"] == ["火灾", "电气"]
    assert item["suggested_params"] == {"l": 4, "s": 5}


def test_execute_migration_marks_sources_and_commits():
    db = AsyncMock()
    source = MagicMock()
    source.id = "src-1"
    source.enterprise_id = "ent-1"
    source.name = "火灾"
    source.categories = "火灾"
    source.location = "仓库"
    source.location_x = 10
    source.location_y = 20
    source.description = "可燃物堆积"
    source.likelihood = 3
    source.severity = 3
    source.control_measures = "定期巡检；安装报警"
    source.migrated = False

    mapping = MagicMock()
    mapping.source_id = "src-1"
    mapping.zone_name = "历史风险源"
    mapping.object_name = "火灾"
    mapping.accident_type = "火灾"
    mapping.method_params = {"l": 3, "s": 3}

    floor = MagicMock()
    floor.id = "floor-1"
    rating = MagicMock()
    rating.risk_level = "一般"
    rating.risk_score = "R=9"

    db.execute.return_value = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [source]
    db.execute.return_value.scalar_one_or_none.side_effect = [None, None]
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with patch(
        "app.services.risk_source_migration_service.ensure_default_floor",
        new=AsyncMock(return_value=floor),
    ), patch(
        "app.services.risk_source_migration_service.get_active_method_config",
        new=AsyncMock(return_value={"risk_thresholds": []}),
    ), patch(
        "app.services.risk_source_migration_service.compute_risk",
        return_value=rating,
    ):
        result = asyncio.run(execute_migration(db, "ent-1", [mapping]))

    assert result["migrated"] == 1
    assert result["created"]["objects"] == 1
    assert source.migrated is True
    db.commit.assert_awaited_once()
