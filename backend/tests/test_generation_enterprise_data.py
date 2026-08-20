from unittest.mock import MagicMock

from app.routers.generation import _collect_enterprise_data


def test_collect_enterprise_data_uses_hierarchical_risk_context():
    ent = MagicMock()
    ent.name = "测试企业"
    ent.address = "测试地址"
    ent.industry = "化工"
    ent.business_scope = "生产"
    ent.employee_count = 100
    ent.building_overview = ""
    ent.org_structure = []
    ent.surrounding_info = {}
    ent.legal_representative = ""
    ent.credit_code = ""
    ent.economic_type = ""
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = ""
    ent.land_area = None
    ent.building_area = None
    ent.safety_officer = ""
    ent.safety_standardization = ""
    ent.fire_approval = ""
    ent.main_products = ""
    ent.hazardous_chemicals = ""
    ent.special_equipment = ""

    risk_context = {
        "risk_sources": [{
            "zone": "生产区",
            "object": "原料仓",
            "unit": None,
            "name": "原料仓",
            "categories": "火灾",
            "location": "东区",
            "accident_type": "火灾",
            "risk_level": "较大",
            "description": "可燃物",
            "triggers": "明火",
            "consequences": "损失",
            "control_measures": "巡检",
            "measures": [],
        }]
    }
    resources = []

    data = _collect_enterprise_data(ent, risk_context, resources)

    assert data["risk_sources"][0]["name"] == "原料仓"
    assert data["risk_sources"][0]["categories"] == "火灾"
    assert data["risk_sources"][0]["control_measures"] == "巡检"
    assert data["risk_sources"][0]["accident_type"] == "火灾"


def test_collect_enterprise_data_marks_missing_fields():
    ent = MagicMock()
    ent.name = "测试企业"
    ent.address = None
    ent.industry = ""
    ent.business_scope = "生产"
    ent.employee_count = 100
    ent.building_overview = ""
    ent.org_structure = []
    ent.surrounding_info = None
    ent.legal_representative = ""
    ent.credit_code = None
    ent.economic_type = ""
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = ""
    ent.land_area = None
    ent.building_area = None
    ent.safety_officer = ""
    ent.safety_standardization = ""
    ent.fire_approval = ""
    ent.main_products = ""
    ent.hazardous_chemicals = ""
    ent.special_equipment = ""

    data = _collect_enterprise_data(ent, {"risk_sources": []}, [])
    assert data["address"] == "（待补充）"
    assert data["industry"] == "（待补充）"
    assert data["legal_representative"] == "（待补充）"
    assert data["business_scope"] == "生产"  # 非空值保持原样


def test_compliance_block_contains_truth_guard():
    from app.services.prompt_cache import COMPLIANCE_BLOCK
    assert "数据真实性护栏" in COMPLIANCE_BLOCK
    assert "禁止推断" in COMPLIANCE_BLOCK


def _org_ent_with_inline_members():
    ent = MagicMock()
    ent.name = "测试企业"
    ent.address = "测试地址"
    ent.industry = "化工"
    ent.business_scope = "生产"
    ent.employee_count = 100
    ent.building_overview = ""
    ent.org_structure = [
        {"id": "preset-headquarters-0", "name": "总指挥", "type": "position",
         "members": [{"name": "张三", "position": "总指挥"}], "parent_id": "preset-headquarters"},
        {"id": "node-6", "name": "部门经理", "type": "position",
         "members": [{"name": "李四", "position": "部门经理"}], "parent_id": "node-2"},
    ]
    ent.surrounding_info = {}
    ent.legal_representative = ""
    ent.credit_code = ""
    ent.economic_type = ""
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = ""
    ent.land_area = None
    ent.building_area = None
    ent.safety_officer = ""
    ent.safety_standardization = ""
    ent.fire_approval = ""
    ent.main_products = ""
    ent.hazardous_chemicals = ""
    ent.special_equipment = ""
    return ent


def test_collect_enterprise_data_uses_member_table_to_override_org_members():
    """生成时若存在成员表数据，组织树节点成员必须以成员表为准（覆盖内嵌旧名）。"""
    ent = _org_ent_with_inline_members()
    org_members = [
        {"name": "刘昕野", "position": "总经理", "org_node_id": "preset-headquarters-0"},
    ]
    data = _collect_enterprise_data(ent, {"risk_sources": []}, [], org_members=org_members)
    nodes = {n["id"]: n for n in data["org_structure"]}
    assert nodes["preset-headquarters-0"]["members"] == [
        {"name": "刘昕野", "position": "总经理"}
    ]
    # 无成员表关联的节点：内嵌旧名（李四）必须被清空，而不是带入预案
    assert nodes["node-6"]["members"] == []


def test_collect_enterprise_data_keeps_inline_members_without_member_table():
    """无成员表数据时保持向后兼容：组织树内嵌成员原样保留。"""
    ent = _org_ent_with_inline_members()
    data = _collect_enterprise_data(ent, {"risk_sources": []}, [])
    nodes = {n["id"]: n for n in data["org_structure"]}
    assert nodes["preset-headquarters-0"]["members"] == [{"name": "张三", "position": "总指挥"}]


def test_collect_enterprise_data_accepts_orm_member_objects():
    """成员表数据为 ORM 对象时同样生效（getattr 路径）。"""
    ent = _org_ent_with_inline_members()
    m = MagicMock()
    m.name = "程磊"
    m.position = "项目经理"
    m.org_node_id = "node-6"
    data = _collect_enterprise_data(ent, {"risk_sources": []}, [], org_members=[m])
    nodes = {n["id"]: n for n in data["org_structure"]}
    assert nodes["node-6"]["members"] == [{"name": "程磊", "position": "项目经理"}]
