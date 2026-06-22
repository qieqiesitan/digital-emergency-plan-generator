import asyncio, json
from uuid import uuid4
from app.database import async_session
from app.models.user import User
from app.models.enterprise import PlanTemplate
from sqlalchemy import select

# GB/T 29639-2020 based template structures
COMPREHENSIVE_STRUCTURE = [
    {
        "key": "sec_1", "title": "总则", "level": 1, "sort_order": 1,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.1条",
        "prompt_template": None, "data_dependencies": [],
        "subsections": [
            {"key": "sec_1_1", "title": "编制目的", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_1_2", "title": "编制依据", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_1_3", "title": "适用范围", "level": 2, "sort_order": 3, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_1_4", "title": "应急预案体系", "level": 2, "sort_order": 4, "ai_generatable": True, "user_editable": True, "required": False, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_1_5", "title": "应急工作原则", "level": 2, "sort_order": 5, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
        ]
    },
    {
        "key": "sec_2", "title": "事故风险描述", "level": 1, "sort_order": 2,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.2条",
        "prompt_template": None, "data_dependencies": ["risk_sources"],
        "subsections": [
            {"key": "sec_2_1", "title": "风险源识别与等级评估", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["risk_sources"], "subsections": []},
            {"key": "sec_2_2", "title": "事故发生的可能性及后果", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["risk_sources"], "subsections": []},
        ]
    },
    {
        "key": "sec_3", "title": "应急组织机构及职责", "level": 1, "sort_order": 3,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.3条",
        "prompt_template": None, "data_dependencies": ["org_structure"],
        "subsections": [
            {"key": "sec_3_1", "title": "应急组织机构设置", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["org_structure"], "subsections": []},
            {"key": "sec_3_2", "title": "各机构职责分工", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["org_structure"], "subsections": []},
        ]
    },
    {
        "key": "sec_4", "title": "预警及信息报告", "level": 1, "sort_order": 4,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.4条",
        "prompt_template": None, "data_dependencies": [],
        "subsections": [
            {"key": "sec_4_1", "title": "预警分级与发布", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_4_2", "title": "信息报告程序", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
        ]
    },
    {
        "key": "sec_5", "title": "应急响应", "level": 1, "sort_order": 5,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.5条",
        "prompt_template": None, "data_dependencies": ["risk_sources", "emergency_resources"],
        "subsections": [
            {"key": "sec_5_1", "title": "响应分级", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["risk_sources"], "subsections": []},
            {"key": "sec_5_2", "title": "响应程序", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_5_3", "title": "处置措施", "level": 2, "sort_order": 3, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["risk_sources", "emergency_resources"], "subsections": []},
        ]
    },
    {
        "key": "sec_6", "title": "信息公开", "level": 1, "sort_order": 6,
        "ai_generatable": True, "user_editable": True, "required": False,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.6条",
        "prompt_template": None, "data_dependencies": [],
        "subsections": []
    },
    {
        "key": "sec_7", "title": "后期处置", "level": 1, "sort_order": 7,
        "ai_generatable": True, "user_editable": True, "required": False,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.7条",
        "prompt_template": None, "data_dependencies": [],
        "subsections": []
    },
    {
        "key": "sec_8", "title": "保障措施", "level": 1, "sort_order": 8,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.8条",
        "prompt_template": None, "data_dependencies": ["emergency_resources"],
        "subsections": []
    },
    {
        "key": "sec_9", "title": "应急预案管理", "level": 1, "sort_order": 9,
        "ai_generatable": True, "user_editable": True, "required": False,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第5.9条",
        "prompt_template": None, "data_dependencies": [],
        "subsections": [
            {"key": "sec_9_1", "title": "培训与演练", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": False, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_9_2", "title": "预案修订与更新", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": False, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
        ]
    },
]

SPECIAL_STRUCTURE = [
    {
        "key": "sec_1", "title": "事故风险分析", "level": 1, "sort_order": 1,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第6条",
        "prompt_template": None, "data_dependencies": ["risk_sources"],
        "subsections": [
            {"key": "sec_1_1", "title": "事故类型与危险程度", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["risk_sources"], "subsections": []},
            {"key": "sec_1_2", "title": "事故影响范围及后果", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["risk_sources"], "subsections": []},
        ]
    },
    {
        "key": "sec_2", "title": "应急指挥机构及职责", "level": 1, "sort_order": 2,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第6条",
        "prompt_template": None, "data_dependencies": ["org_structure"],
        "subsections": []
    },
    {
        "key": "sec_3", "title": "处置程序与措施", "level": 1, "sort_order": 3,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第6条",
        "prompt_template": None, "data_dependencies": ["risk_sources", "emergency_resources"],
        "subsections": [
            {"key": "sec_3_1", "title": "应急响应启动流程", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_3_2", "title": "现场应急处置措施", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["risk_sources", "emergency_resources"], "subsections": []},
            {"key": "sec_3_3", "title": "扩大应急", "level": 2, "sort_order": 3, "ai_generatable": True, "user_editable": True, "required": False, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
        ]
    },
    {
        "key": "sec_4", "title": "应急保障", "level": 1, "sort_order": 4,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第6条",
        "prompt_template": None, "data_dependencies": ["emergency_resources"],
        "subsections": []
    },
]

ONSITE_STRUCTURE = [
    {
        "key": "sec_1", "title": "事故风险提示", "level": 1, "sort_order": 1,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第7条",
        "prompt_template": None, "data_dependencies": ["risk_sources"],
        "subsections": []
    },
    {
        "key": "sec_2", "title": "应急组织与联络", "level": 1, "sort_order": 2,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": True, "auto_fill_source": "org_structure",
        "gb_requirement": "GB/T 29639-2020 第7条",
        "prompt_template": None, "data_dependencies": ["org_structure"],
        "subsections": []
    },
    {
        "key": "sec_3", "title": "应急处置卡", "level": 1, "sort_order": 3,
        "ai_generatable": True, "user_editable": True, "required": True,
        "auto_fill": False, "auto_fill_source": None,
        "gb_requirement": "GB/T 29639-2020 第7条",
        "prompt_template": None, "data_dependencies": ["risk_sources", "emergency_resources"],
        "subsections": [
            {"key": "sec_3_1", "title": "发现事故第一响应", "level": 2, "sort_order": 1, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_3_2", "title": "紧急处置步骤", "level": 2, "sort_order": 2, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": ["risk_sources", "emergency_resources"], "subsections": []},
            {"key": "sec_3_3", "title": "人员疏散路线", "level": 2, "sort_order": 3, "ai_generatable": True, "user_editable": True, "required": True, "auto_fill": False, "auto_fill_source": None, "gb_requirement": "", "prompt_template": None, "data_dependencies": [], "subsections": []},
            {"key": "sec_3_4", "title": "紧急联系电话", "level": 2, "sort_order": 4, "ai_generatable": False, "user_editable": True, "required": True, "auto_fill": True, "auto_fill_source": "org_structure", "gb_requirement": "", "prompt_template": None, "data_dependencies": ["org_structure"], "subsections": []},
        ]
    },
]

async def seed():
    async with async_session() as db:
        # Check existing
        r = await db.execute(select(PlanTemplate))
        existing = len(r.scalars().all())
        if existing > 0:
            print(f"Already have {existing} templates, skipping seed")
            return

        templates = [
            PlanTemplate(
                id=str(uuid4()),
                plan_type="comprehensive",
                name="综合应急预案模板",
                version="1.0.0",
                structure=COMPREHENSIVE_STRUCTURE,
                is_active=True,
            ),
            PlanTemplate(
                id=str(uuid4()),
                plan_type="special",
                name="专项应急预案模板",
                version="1.0.0",
                structure=SPECIAL_STRUCTURE,
                is_active=True,
            ),
            PlanTemplate(
                id=str(uuid4()),
                plan_type="onsite",
                name="现场处置方案模板",
                version="1.0.0",
                structure=ONSITE_STRUCTURE,
                is_active=True,
            ),
        ]
        for t in templates:
            db.add(t)
            print(f"Added template: {t.name} ({t.plan_type}) with {len(t.structure)} top-level sections")
        await db.commit()
        print(f"Seeded {len(templates)} templates")

asyncio.run(seed())
