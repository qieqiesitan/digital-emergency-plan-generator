"""报告章节装配：纯逻辑测试，不连数据库。"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.services.major_hazard_report_data import (
    ReportNotReadyError,
    build_chapters,
    conclusion_sentence,
)


def _unit(name="罐区A", unit_type="storage"):
    u = MagicMock()
    u.name = name
    u.unit_type = unit_type
    u.address = "厂区北侧"
    u.department = "生产部"
    u.responsible_person = "张峰"
    u.responsible_phone = "13800000000"
    u.unit_type = unit_type
    u.boundary_desc = "以罐区防火堤为界"
    return u


def _chem(name, q, Q, beta, source="table3"):
    c = MagicMock()
    c.chemical_name = name
    c.q_design_max = Decimal(str(q))
    c.critical_quantity_t = Decimal(str(Q))
    c.beta = Decimal(str(beta))
    c.beta_source = source
    c.physical_state = "液态"
    c.storage_location = "罐区A"
    return c


def _snapshot(is_major=True, level="四级", s=1.5, r=7.5, alpha=1.5, pop=60):
    return {
        "seq": 1,
        "s_value": s,
        "r_value": r,
        "alpha": alpha,
        "exposed_population": pop,
        "is_major_hazard": is_major,
        "level": level,
        "formula_version": "GB18218-2018",
        "chemicals": [
            {"name": "氯", "q": 5.0, "Q": 5.0, "beta": 4.0, "q_over_Q": 1.0,
             "beta_times_q_over_Q": 4.0},
            {"name": "氨", "q": 5.0, "Q": 10.0, "beta": 2.0, "q_over_Q": 0.5,
             "beta_times_q_over_Q": 1.0},
        ],
    }


def _record():
    r = MagicMock()
    r.hazard_code = "TYKJ001"
    r.filing_status = "已备案"
    r.chief_name = "李总"
    r.tech_name = "王工"
    r.oper_name = "张峰"
    return r


def test_conclusion_sentence_for_major_hazard():
    s = conclusion_sentence(_snapshot(), "罐区A")
    assert "罐区A" in s
    assert "构成" in s
    assert "四级" in s
    assert "GB 18218" in s


def test_conclusion_sentence_for_non_major():
    s = conclusion_sentence(_snapshot(is_major=False, level=None, s=0.4, r=2.0), "锅炉房")
    assert "不构成" in s
    assert "未达到" in s
    assert "四级" not in s


def test_build_chapters_requires_snapshot():
    """没有快照就不允许出报告——空报告会被误读成"不构成"。"""
    with pytest.raises(ReportNotReadyError) as ei:
        build_chapters(
            enterprise_name="某公司",
            unit=_unit(),
            chemicals=[_chem("氯", 5, 5, 4)],
            snapshot=None,
            record=None,
            evidences=[],
        )
    assert "尚未进行辨识计算" in str(ei.value)


def test_build_chapters_has_all_sections_in_order():
    chapters = build_chapters(
        enterprise_name="某公司",
        unit=_unit(),
        chemicals=[_chem("氯", 5, 5, 4), _chem("氨", 5, 10, 2)],
        snapshot=_snapshot(),
        record=_record(),
        evidences=[{"article_anchor": "GB 18218-2018 4.2.1", "relation": "依据"}],
    )
    keys = [c["key"] for c in chapters]
    assert keys == [
        "basic", "basis", "units", "chemicals",
        "metrics", "grading", "conclusion", "responsible", "appendix",
    ]
    for c in chapters:
        assert c["title"] and c["content"]


def test_chemicals_chapter_contains_q_and_beta():
    chapters = {c["key"]: c for c in build_chapters(
        enterprise_name="某公司",
        unit=_unit(),
        chemicals=[_chem("氯", 5, 5, 4), _chem("氨", 5, 10, 2)],
        snapshot=_snapshot(),
        record=None,
        evidences=[],
    )}
    assert "氯" in chapters["chemicals"]["content"]
    assert "5" in chapters["chemicals"]["content"]
    assert "4" in chapters["chemicals"]["content"]  # β


def test_grading_chapter_explicit_for_non_major():
    chapters = {c["key"]: c for c in build_chapters(
        enterprise_name="某公司",
        unit=_unit(name="锅炉房"),
        chemicals=[_chem("氯", 1, 5, 4)],
        snapshot=_snapshot(is_major=False, level=None, s=0.2, r=0.8),
        record=None,
        evidences=[],
    )}
    assert "不构成" in chapters["grading"]["content"]
    assert "不构成" in chapters["conclusion"]["content"]


def test_appendix_lists_evidence_anchors():
    chapters = {c["key"]: c for c in build_chapters(
        enterprise_name="某公司",
        unit=_unit(),
        chemicals=[_chem("氯", 5, 5, 4)],
        snapshot=_snapshot(),
        record=None,
        evidences=[
            {"article_anchor": "GB 18218-2018 4.2.1", "relation": "依据"},
            {"article_anchor": "GB 18218-2018 4.3.2", "relation": "依据"},
        ],
    )}
    assert "GB 18218-2018 4.2.1" in chapters["appendix"]["content"]
    assert "GB 18218-2018 4.3.2" in chapters["appendix"]["content"]


def test_responsible_chapter_omitted_when_no_record():
    """没建档时该章留占位说明，不能整章消失（章节完整性会被审查）。"""
    chapters = {c["key"]: c for c in build_chapters(
        enterprise_name="某公司",
        unit=_unit(),
        chemicals=[_chem("氯", 5, 5, 4)],
        snapshot=_snapshot(),
        record=None,
        evidences=[],
    )}
    assert "responsible" in chapters
    assert "尚未建立" in chapters["responsible"]["content"]
