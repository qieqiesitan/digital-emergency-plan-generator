"""回归：报告提示词必须把风险管控数据的关键字段带进 LLM。

根因：build_chapter_prompt 只手拼 name/categories/location/description/L/S/
risk_level/control_measures，漏掉事故类型、风险分值、所属层级、触发条件、
后果、化学品明细、组织成员——模型无数据可依导致内容编造/偏差。
"""

from app.services.risk_assessment_service import build_chapter_prompt as ra_build
from app.services.resource_investigation_service import (
    build_chapter_prompt as ri_build,
)


RA_CTX = {
    "enterprise": {
        "name": "测试企业",
        "industry": "商贸服务",
        "address": "测试路1号",
    },
    "chemicals": [
        {
            "name": "乙醇",
            "cas_no": "64-17-5",
            "physical_state": "液体",
            "flash_point": "13℃",
            "explosion_limit": "3.3%~19%",
            "health_hazard": "吸入高浓度蒸气可致麻醉",
            "location": "库房A",
        }
    ],
    "org_members": [
        {"name": "刘昕野", "position": "总经理", "phone": "13800000000"}
    ],
    "risk_sources": [
        {
            "name": "燃气灶台",
            "categories": "火灾",
            "location": "厨房",
            "zone": "一层",
            "object": "厨房区域",
            "unit": "燃气灶台",
            "accident_type": "火灾爆炸",
            "risk_level": "较大",
            "risk_score": 16,
            "description": "燃气软管老化",
            "triggers": "胶管破损、忘关阀门",
            "consequences": "火灾爆炸、人员伤亡",
            "likelihood": 3,
            "severity": 5,
            "control_measures": "安装燃气报警器",
        }
    ],
}


RI_CTX = {
    "enterprise": {
        "name": "测试企业",
        "industry": "商贸服务",
        "employee_count": 3,
    },
    "org_members": [
        {"name": "刘昕野", "position": "总经理", "phone": "13800000000"}
    ],
    "internal_resources": [
        {
            "category": "消防设施",
            "name": "干粉灭火器",
            "specification": "4kg",
            "quantity": 6,
            "unit": "具",
            "location": "走廊",
            "responsible_person": "刘昕野",
            "contact_phone": "13800000000",
        }
    ],
    "external_resources": [],
    "risk_conclusion": None,
    "top_risks": [],
    "risk_overview": [
        {"accident_type": "火灾爆炸", "risk_level": "较大", "count": 1},
        {"accident_type": "触电", "risk_level": "低", "count": 4},
    ],
    "top_risk_sources": [
        {
            "name": "燃气灶台",
            "location": "厨房",
            "risk_level": "较大",
            "accident_type": "火灾爆炸",
            "control_measures": "安装燃气报警器",
        }
    ],
}


def test_risk_prompt_includes_full_risk_source_fields():
    prompt = ra_build("ch1_hazard_id", RA_CTX)
    # 之前缺失的关键数据：事故类型、分值、所属层级、触发条件、后果
    assert "火灾爆炸" in prompt
    assert "事故类型" in prompt
    assert "风险分值" in prompt
    assert "一层" in prompt
    assert "胶管破损、忘关阀门" in prompt
    assert "火灾爆炸、人员伤亡" in prompt


def test_risk_prompt_includes_chemicals_and_members():
    prompt = ra_build("ch1_hazard_id", RA_CTX)
    assert "乙醇" in prompt
    assert "64-17-5" in prompt
    assert "刘昕野" in prompt


def test_resource_prompt_includes_members_and_risk_overview():
    prompt = ri_build("ch2_basic_info", RI_CTX)
    assert "刘昕野" in prompt
    assert "火灾爆炸" in prompt
    assert "燃气灶台" in prompt


def test_risk_prompt_includes_style_instruction():
    style = {
        "formality": "formal",
        "detail_level": "comprehensive",
        "table_preference": "heavy",
        "diagram_preference": "none",
        "mode": "panel",
    }
    prompt = ra_build("ch1_hazard_id", RA_CTX, style_preference=style)
    assert "正式" in prompt or "公文语体" in prompt
