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


def test_archive_field_match_ignores_whitespace():
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    # 正文中地址被换行/空格打断，应视为已体现（归一化后匹配）
    result = check_plan(plan, enterprise, [
        _section("sec_1", "总则", "<p>企业地址：西安市高新区\n一路1号，法人：张三</p>"),
    ])
    assert not any("地址" in w["warning"] for w in result["warnings"])


def test_mermaid_missing_type_declaration_warning():
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    content = '<pre><code class="language-mermaid">A --> B</code></pre>'
    result = check_plan(plan, enterprise, [_section("sec_5", "应急响应", content)])
    assert any("Mermaid" in w["warning"] for w in result["warnings"])


from app.services.plan_quality_service import (
    check_plan, _extract_address_fragments, _must_have_section_key,
)


def test_must_have_section_keys():
    assert _must_have_section_key("comprehensive") == "sec_2"
    assert _must_have_section_key("special") == "sec_1"
    assert _must_have_section_key("onsite") == "sec_1"
    assert _must_have_section_key("unknown") is None


def test_extract_address_fragments():
    frags = _extract_address_fragments("陕西省西安市经济技术开发区民经一路726号2幢12402室")
    assert any("民经一路726号" in f for f in frags)
    assert any("经济技术开发区" in f for f in frags)


def test_non_must_have_section_no_archive_warning():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号2幢12402室",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [_section("sec_3", "处置程序与措施", "<p>内容</p>")])
    assert not any("未体现" in w["warning"] for w in result["warnings"])


def test_must_have_section_address_fragment_match_no_warning():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号2幢12402室",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>公司位于民经一路726号，法定代表人为刘昕野，安全负责人刘昕野。</p>")
    ])
    assert not any("未体现" in w["warning"] for w in result["warnings"])


def test_c1_cross_section_person_conflict():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "13800000000", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>总指挥：刘昕野</p>"),
        _section("sec_3", "处置程序", "<p>总指挥：王五</p>"),
    ])
    assert any("总指挥" in w["warning"] and "不一致" in w["warning"] for w in result["warnings"])


def test_c2_address_conflict():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>公司位于湖北省武汉市某街道。</p>"),
    ])
    assert any("地址" in w["warning"] and "不一致" in w["warning"] for w in result["warnings"])


def test_c3_level_notation_mixed():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>启动III级响应，执行一级响应程序。</p>"),
    ])
    assert any("响应分级" in w["warning"] for w in result["warnings"])


def test_c1_deputy_commander_not_matched_as_commander():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "138", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    # 只有副总指挥，不应误报总指挥不一致
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>副总指挥：王五</p>"),
    ])
    assert not any("总指挥" in w["warning"] for w in result["warnings"])


def test_c3_time_unit_mixed():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>30分钟内上报，0.5小时后处置完毕。</p>"),
    ])
    assert any("时限" in w["warning"] for w in result["warnings"])
