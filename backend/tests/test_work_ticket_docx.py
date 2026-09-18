"""法定票面渲染与打印快照。"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


from app.services.work_ticket_docx import (
    build_snapshot,
    content_hash,
    render_ticket_docx,
)


def _instance():
    i = MagicMock()
    i.id = "wt1"
    i.code = "DHZY-TYKJ-20260917-0001"
    i.ticket_type = "DHZY"
    i.level = "一级"
    i.status = "approved"
    i.values = {"work_content": "焊接", "fire_location": "罐区A 北侧管廊"}
    i.valid_from = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
    i.valid_to = datetime(2026, 9, 17, 17, 0, tzinfo=timezone.utc)
    return i


def _template():
    t = MagicMock()
    t.name = "动火安全作业票"
    f1 = MagicMock()
    f1.field_key = "work_content"
    f1.label = "作业内容"
    f1.sort_order = 1
    f2 = MagicMock()
    f2.field_key = "fire_location"
    f2.label = "动火地点及动火部位"
    f2.sort_order = 2
    t.fields = [f1, f2]
    m1 = MagicMock()
    m1.measure_text = "动火设备内部构件清洗干净"
    m1.article_anchor = "GB 30871-2022 5"
    m1.sort_order = 1
    t.measures = [m1]
    return t


def test_build_snapshot_contains_faces_and_measures():
    snap = build_snapshot(
        instance=_instance(),
        template=_template(),
        node_records=[{"node_key": "approve", "action": "approve", "acted_by": "u1", "opinion": "同意"}],
        gas_tests=[{"sampled_at": "2026-09-17T08:40:00+00:00", "result": "合格"}],
    )
    assert snap["code"] == "DHZY-TYKJ-20260917-0001"
    assert snap["fields"][0]["label"] == "作业内容"
    assert snap["measures"][0]["article_anchor"] == "GB 30871-2022 5"
    assert snap["node_records"][0]["opinion"] == "同意"
    assert snap["copies"] == ["第一联 监护人/作业单位", "第二联 所在基层单位", "第三联 存档"]


def test_content_hash_is_stable_and_changes_on_content():
    snap1 = {"a": 1, "b": [1, 2]}
    snap2 = {"b": [1, 2], "a": 1}  # 键序不同
    assert content_hash(snap1) == content_hash(snap2), "键序变化不应改变 hash"
    assert content_hash(snap1) != content_hash({"a": 1, "b": [1, 3]})


def test_snapshot_excludes_nothing_sensitive_field_keys():
    """票面可能含人名电话，快照要留痕但不额外存无关字段。"""
    snap = build_snapshot(
        instance=_instance(), template=_template(), node_records=[], gas_tests=[]
    )
    assert set(snap) == {
        "code", "ticket_type", "level", "status", "valid_from", "valid_to",
        "fields", "measures", "node_records", "gas_tests", "copies",
    }


def test_render_ticket_docx_calls_docx_template():
    with patch("app.services.work_ticket_docx.build_table") as bt, patch(
        "app.services.work_ticket_docx.Document"
    ) as doc:
        doc.return_value = MagicMock()
        render_ticket_docx(snapshot=build_snapshot(
            instance=_instance(), template=_template(), node_records=[], gas_tests=[]
        ))
        assert bt.call_count >= 2, "票面字段表与措施表都要渲染成表格"
