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


def test_placeholder_warning_has_evidence():
    """质量提示必须带正文证据片段，便于预览/导出高亮定位。"""
    enterprise = MagicMock(address="西安市高新区一路1号", legal_representative="张三", safety_officer="李四")
    plan = MagicMock()
    result = check_plan(plan, enterprise, [_section("sec_2", "风险描述", "<p>地址（待补充）</p>")])
    assert any(w.get("evidence") == "（待补充）" for w in result["warnings"])


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
    # E2 新规则允许「缺少总指挥或副总指挥」告警；此处只验证 C1 不误报总指挥姓名不一致
    assert not any(
        "总指挥" in w["warning"] and ("不一致" in w["warning"] or "不符" in w["warning"])
        for w in result["warnings"]
    )


def test_c3_time_unit_rule_removed():
    # 时限混用检查已移除（2026-08-11）：纯正则无法判断分钟/小时数值是否属于同一场景，
    # 「持续观察 30 分钟」（普通火灾）与「观察时间延长至 2 小时」（锂电池）等独立场景不再误报。
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>持续观察30分钟，观察时间延长至2小时。</p>"),
    ])
    assert not any("时限" in w["warning"] for w in result["warnings"])


def test_c1_verb_not_matched_as_name():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "138", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>总指挥负责抢险救援。</p>"),
    ])
    assert not any("姓名不一致" in w["warning"] for w in result["warnings"])


def test_c2_correct_and_wrong_address_no_conflict_warning():
    enterprise = MagicMock(address="陕西省西安市经济技术开发区民经一路726号",
                           legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>公司位于民经一路726号，另一处位于武汉市某街道。</p>"),
    ])
    assert not any("地址" in w["warning"] and "不一致" in w["warning"] for w in result["warnings"])


def test_c3_equivalent_time_no_warning():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>30分钟内上报，0.5小时后处置完毕。</p>"),
    ])
    assert not any("时限" in w["warning"] for w in result["warnings"])


def test_c1_verb_with_punct_not_matched():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "138", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>总指挥下令。</p>"),
    ])
    assert not any("姓名不一致" in w["warning"] for w in result["warnings"])


def test_c3_compound_duration_no_warning():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>1小时30分钟内完成处置。</p>"),
    ])
    assert not any("时限" in w["warning"] for w in result["warnings"])


def test_c3_chinese_level_with_yingji():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>启动III级响应，执行一级应急响应程序。</p>"),
    ])
    assert any("响应分级" in w["warning"] for w in result["warnings"])


def test_e1_org_member_missing_phone():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>联系电话：12345</p>"),
    ])
    # 正文电话格式检查已收敛移除：正文「联系电话：12345」不应再告警；
    # 仅组织架构成员缺电话触发完整性告警
    assert any("无联系电话" in w["warning"] for w in result["warnings"])
    assert not any("格式错误" in w["warning"] for w in result["warnings"])


def test_e2_missing_commander():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "抢险组", "members": [
            {"name": "李四", "position": "组长", "phone": "13800000000", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ])
    assert any("总指挥" in w["warning"] for w in result["warnings"])


def test_e3_missing_fire_resource():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ], resources=[])
    assert any("消防" in w["warning"] for w in result["warnings"])


def test_e2_org_mentions_commander_but_missing():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "抢险组", "members": [
            {"name": "李四", "position": "组长", "phone": "13800000000", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_2", "应急指挥机构", "<p>应急指挥部职责……</p>"),
    ])
    assert any("应急指挥机构" in w["warning"] for w in result["warnings"])


def test_e3_zero_quantity_resource_warning():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    plan.risk_sources = [{"name": "储罐"}]
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ], resources=[{"category": "消防", "name": "灭火器", "quantity": 0}], has_risk=True)
    assert any("数量均为 0" in w["warning"] for w in result["warnings"])


def test_e2_role_field_counts_as_position():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "role": "总指挥", "position": "", "phone": "13800000000", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ])
    # role=总指挥 应被识别为已设总指挥；仅缺副总指挥，不报「缺少总指挥」
    assert not any("缺少总指挥" in w["warning"] for w in result["warnings"])
    assert any("缺少副总指挥" in w["warning"] for w in result["warnings"])


def test_e2_combined_position_role_no_false_commander():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "李四", "role": "总指挥", "position": "组长", "phone": "13800000000", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ])
    # 有 role=总指挥 → 不应报缺总指挥（position/role 分别检查，不再拼接误判）
    assert not any("缺少总指挥" in w["warning"] for w in result["warnings"])
    assert any("缺少副总指挥" in w["warning"] for w in result["warnings"])


def test_e3_null_quantity_not_reported():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ], resources=[{"category": "消防", "name": "灭火器", "quantity": None}], has_risk=True)
    # NULL 数量视为未知，不报「数量为 0」
    assert not any("数量为 0" in w["warning"] for w in result["warnings"])


def test_c1_phrase_after_role_not_matched_as_name():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "138", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>总指挥不在岗时。总指挥职责。总指挥负责制。总指挥接报后。总指挥组织讲评。</p>"),
    ])
    assert not any("姓名不一致" in w["warning"] for w in result["warnings"])


def test_c1_group_leader_not_cross_section_compared():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总指挥", "phone": "138", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>抢险救援组组长：刘昕野</p>"),
        _section("sec_2", "应急指挥", "<p>疏散引导组组长：程磊</p>"),
    ])
    # 不同小组组长不同人是正常的，不报组长不一致
    assert not any("组长" in w["warning"] for w in result["warnings"])


def test_c1_general_manager_matches_commander():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    enterprise.org_structure = [
        {"group_name": "指挥部", "members": [
            {"name": "刘昕野", "position": "总经理", "role": "chief", "phone": "138", "responsibilities": ""},
        ]},
    ]
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>总指挥：刘昕野</p>"),
    ])
    # E2 规则仍会提示「缺少副总指挥」（档案只有总经理）；此处只验证 C1 不误报总指挥与档案不符
    assert not any(
        "总指挥" in w["warning"] and ("不一致" in w["warning"] or "不符" in w["warning"])
        for w in result["warnings"]
    )


def test_c3_setting_levels_not_counted():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>本预案设置三级响应，启动III级响应执行相应程序。</p>"),
    ])
    assert not any("响应分级" in w["warning"] for w in result["warnings"])


def test_c3_quantity_phrase_not_counted_with_roman_present():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>本预案设置三级响应，启动III级响应执行相应程序。</p>"),
    ])
    # 只有罗马数字级别名，中文「三级响应」是数量表述 → 不应报混用
    assert not any("响应分级" in w["warning"] for w in result["warnings"])


def test_c3_real_level_mix_still_detected():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    result = check_plan(plan, enterprise, [
        _section("sec_3", "处置程序", "<p>启动III级响应，执行一级应急响应程序。</p>"),
    ])
    assert any("响应分级" in w["warning"] for w in result["warnings"])


def test_e3_category_with_positive_resource_not_reported():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    plan.risk_sources = [{"name": "储罐"}]
    result = check_plan(plan, enterprise, [
        _section("sec_1", "事故风险分析", "<p>内容</p>"),
    ], resources=[
        {"category": "公安机关", "name": "明光路派出所", "quantity": 1},
        {"category": "公安机关", "name": "属地派出所", "quantity": 0},
    ], has_risk=True)
    assert not any("公安机关" in w["warning"] for w in result["warnings"])


def test_role_matches_deputy_not_commander():
    from app.services.plan_quality_service import _role_matches
    assert _role_matches({"position": "副总指挥", "role": ""}, "副总指挥") is True
    assert _role_matches({"position": "副总指挥", "role": ""}, "总指挥") is False
    assert _role_matches({"position": "总经理", "role": ""}, "总指挥") is True
    assert _role_matches({"position": "副总经理", "role": ""}, "副总指挥") is True


def test_role_matches_vice_gm_not_commander():
    from app.services.plan_quality_service import _role_matches
    assert _role_matches({"position": "副总经理", "role": ""}, "副总指挥") is True
    assert _role_matches({"position": "副总经理", "role": ""}, "总指挥") is False
    assert _role_matches({"position": "总经理", "role": ""}, "总指挥") is True
    assert _role_matches({"position": "总经理", "role": ""}, "副总指挥") is False


def test_c3_more_quantity_phrases_excluded():
    enterprise = MagicMock(address="地址", legal_representative="刘昕野", safety_officer="刘昕野")
    plan = MagicMock(plan_type="special")
    for phrase in ("本预案设置三级响应", "将响应分为三级响应", "共设定三级响应"):
        result = check_plan(plan, enterprise, [
            _section("sec_3", "处置程序", f"<p>{phrase}，启动III级响应执行相应程序。</p>"),
        ])
        assert not any("响应分级" in w["warning"] for w in result["warnings"]), phrase
