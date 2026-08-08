from unittest.mock import MagicMock
from app.services.plan_quality_service import check_plan


def _section(key, title, content):
    s = MagicMock()
    s.section_key = key
    s.title = title
    s.content = content
    return s


def test_empty_required_section_is_issue():
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [_section("sec_1", "总则", "")])
    assert result["valid"] is False
    assert any(i["section_key"] == "sec_1" and "空" in i["issue"] for i in result["issues"])


def test_placeholder_residue_is_warning():
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [_section("sec_2", "风险描述", "<p>地址（待补充）</p>")])
    assert any("待补充" in w["warning"] for w in result["warnings"])


def test_suspected_inferred_address_warning():
    enterprise = MagicMock(address="（待补充）", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [_section("sec_2", "风险描述", "<p>事故发生在湖北省武汉市某街道</p>")])
    assert any("推断" in w["warning"] for w in result["warnings"])


def test_clean_plan_no_issues():
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [
        _section("sec_1", "总则", "<p>企业地址：西安市高新区一路1号，法人：张三</p>"),
    ])
    assert result["valid"] is True
    assert result["issues"] == []
