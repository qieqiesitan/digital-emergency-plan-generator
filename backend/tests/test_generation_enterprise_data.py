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
        {"name": "刘昕野", "position": "总经理", "phone": None, "email": None, "role": None}
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
    m.phone = "13800138000"
    m.email = None
    m.role = "team_leader"
    data = _collect_enterprise_data(ent, {"risk_sources": []}, [], org_members=[m])
    nodes = {n["id"]: n for n in data["org_structure"]}
    assert nodes["node-6"]["members"] == [
        {"name": "程磊", "position": "项目经理", "phone": "13800138000", "email": None, "role": "team_leader"}
    ]


def test_collect_enterprise_data_includes_chemical_msds_fields():
    ent = MagicMock()
    ent.name = "测试企业"
    ent.address = ""
    ent.industry = ""
    ent.business_scope = ""
    ent.employee_count = None
    ent.building_overview = ""
    ent.org_structure = []
    ent.surrounding_info = {}
    ent.legal_representative = ""
    ent.credit_code = ""
    ent.economic_type = ""
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = ""
    ent.fax = ""
    ent.postal_code = ""
    ent.land_area = None
    ent.building_area = None
    ent.annual_capacity = ""
    ent.safety_officer = ""
    ent.safety_officer_phone = ""
    ent.safety_staff_count = None
    ent.safety_standardization = ""
    ent.fire_approval = ""
    ent.fire_approval_date = None
    ent.main_products = ""
    ent.hazardous_chemicals = ""
    ent.special_equipment = ""
    ent.special_equipment_detail = ""
    ent.main_equipment_list = ""
    ent.fire_protection_summary = ""
    ent.natural_conditions = ""
    ent.floor_plan_url = None
    ent.risk_method_config = {}
    ent.last_plan_filing_date = None
    ent.last_plan_filing_authority = ""

    chem = MagicMock()
    chem.name = "液氨"
    chem.cas_no = "7664-41-7"
    chem.un_no = "1005"
    chem.physical_state = "气体"
    chem.flash_point = "不易燃"
    chem.explosion_limit = "15-28%"
    chem.ignition_temp = "651°C"
    chem.density = "0.68"
    chem.boiling_point = "-33°C"
    chem.health_hazard = "吸入有毒"
    chem.fire_hazard = "遇火爆炸"
    chem.leak_response = "喷水稀释"
    chem.storage_transport = "阴凉通风"
    chem.first_aid = "立即脱离现场"
    chem.protective_measures = "佩戴防毒面具"
    chem.location = "氨罐区"
    chem.max_storage = "20吨"

    data = _collect_enterprise_data(
        ent, {"risk_sources": [], "risk_events": [], "zones": [], "risk_objects": [], "floors": []},
        [], chemicals={"c1": chem},
    )
    c = data["chemicals"][0]
    assert c["health_hazard"] == "吸入有毒"
    assert c["first_aid"] == "立即脱离现场"
    assert c["leak_response"] == "喷水稀释"
    assert c["un_no"] == "1005"
    assert c["protective_measures"] == "佩戴防毒面具"


def test_collect_enterprise_data_includes_resource_contact_and_extended_fields():
    ent = MagicMock()
    ent.name = "测试企业"
    ent.address = ""
    ent.industry = ""
    ent.business_scope = ""
    ent.employee_count = None
    ent.building_overview = ""
    ent.org_structure = []
    ent.surrounding_info = {}
    ent.legal_representative = ""
    ent.credit_code = ""
    ent.economic_type = ""
    ent.established_date = None
    ent.registered_capital = None
    ent.phone = ""
    ent.fax = ""
    ent.postal_code = ""
    ent.land_area = None
    ent.building_area = None
    ent.annual_capacity = ""
    ent.safety_officer = ""
    ent.safety_officer_phone = "13800138000"
    ent.safety_staff_count = 5
    ent.safety_standardization = ""
    ent.fire_approval = ""
    ent.fire_approval_date = None
    ent.main_products = ""
    ent.hazardous_chemicals = ""
    ent.special_equipment = ""
    ent.special_equipment_detail = "锅炉2台"
    ent.main_equipment_list = "反应釜"
    ent.fire_protection_summary = "室内消火栓"
    ent.natural_conditions = "平原"
    ent.floor_plan_url = None
    ent.risk_method_config = {}
    ent.last_plan_filing_date = None
    ent.last_plan_filing_authority = ""

    res = MagicMock()
    res.category = "消防"
    res.name = "灭火器"
    res.specification = "MFZ/ABC4"
    res.quantity = 10
    res.unit = "具"
    res.location = "东墙"
    res.responsible_person = "张工"
    res.contact_phone = "13900139000"
    res.is_external = False
    res.external_address = None
    res.external_distance_km = None

    data = _collect_enterprise_data(
        ent, {"risk_sources": [], "risk_events": [], "zones": [], "risk_objects": [], "floors": []},
        [res],
    )
    assert data["emergency_resources"][0]["responsible_person"] == "张工"
    assert data["emergency_resources"][0]["contact_phone"] == "13900139000"
    assert data["safety_officer_phone"] == "13800138000"
    assert data["safety_staff_count"] == 5
    assert data["special_equipment_detail"] == "锅炉2台"
    assert data["fire_protection_summary"] == "室内消火栓"
