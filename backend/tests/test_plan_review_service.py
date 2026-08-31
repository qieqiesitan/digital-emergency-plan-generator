"""test_plan_review_service.py — 规则审查。"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.plan_review_service import review_plan


def _section(key, title, content):
    s = MagicMock(section_key=key, title=title, content=content,
                  diagram_svgs={}, mermaid_svgs=None, ai_generated=True)
    return s


def test_review_detects_empty_and_placeholder():
    plan = MagicMock(plan_type="comprehensive")
    ent = MagicMock(address="西安市高新区软件园", legal_representative="张三",
                    safety_officer="李四")
    sections = [
        _section("sec_1", "总则", ""),
        _section("sec_2", "事故风险描述", "<p>风险内容（待补充）</p>"),
    ]
    out = review_plan(plan, ent, sections)
    keys = [i["section_key"] for i in out["issues"]]
    assert "sec_1" in keys          # 空章节
    assert any("待补充" in w["warning"] for w in out["warnings"])


def test_review_detects_fake_regulation():
    plan = MagicMock(plan_type="comprehensive")
    ent = MagicMock(address="西安市高新区软件园", legal_representative="张三",
                    safety_officer="李四")
    sections = [_section("sec_1", "总则", "<p>依据《不存在的假法规》编制。</p>")]
    with patch("app.services.plan_review_service._regulation_exists", return_value=False):
        out = review_plan(plan, ent, sections)
    assert any("法规" in i["issue"] for i in out["issues"])


def test_review_clean_plan_no_issues():
    plan = MagicMock(plan_type="comprehensive")
    ent = MagicMock(address="西安市高新区软件园", legal_representative="张三",
                    safety_officer="李四")
    sections = [_section("sec_1", "总则", "<p>依据《中华人民共和国安全生产法》编制。</p>")]
    with patch("app.services.plan_review_service._regulation_exists", return_value=True):
        out = review_plan(plan, ent, sections)
    assert out["issues"] == []
