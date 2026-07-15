from app.regulations.injector import inject_regulations
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.enterprise import Enterprise, EmergencyResource
from app.models.risk_assessment import RiskAssessmentReport
from app.models.resource_investigation import ResourceInvestigationReport

logger = logging.getLogger(__name__)

from app.services.prompt_cache import get_report_system_prompt, get_report_section_prompt


async def build_resource_investigation_context(enterprise_id: str, db: AsyncSession) -> dict:
    enterprise_result = await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id)
    )
    enterprise = enterprise_result.scalar_one_or_none()
    if not enterprise:
        raise ValueError("企业不存在")

    resource_result = await db.execute(
        select(EmergencyResource).where(EmergencyResource.enterprise_id == enterprise_id)
    )
    resources = resource_result.scalars().all()
    internal = [r for r in resources if not r.is_external]
    external = [r for r in resources if r.is_external]

    # Try to get risk assessment conclusion
    risk_conclusion = None
    top_risks = []
    risk_result = await db.execute(
        select(RiskAssessmentReport).where(
            RiskAssessmentReport.enterprise_id == enterprise_id,
            RiskAssessmentReport.status == "completed",
        )
    )
    risk_report = risk_result.scalar_one_or_none()
    if risk_report and isinstance(risk_report.summary, dict):
        risk_conclusion = risk_report.summary.get("overall_assessment", risk_conclusion)
        top_risks = risk_report.summary.get("top_risks", [])

    return {
        "enterprise": {
            "name": enterprise.name,
            "industry": enterprise.industry,
            "address": enterprise.address,
            "employee_count": enterprise.employee_count,
            "building_overview": enterprise.building_overview,
            "org_structure": enterprise.org_structure,
            "legal_representative": enterprise.legal_representative,
            "credit_code": enterprise.credit_code,
            "economic_type": enterprise.economic_type,
            "established_date": str(enterprise.established_date) if enterprise.established_date else None,
            "registered_capital": enterprise.registered_capital,
            "phone": enterprise.phone,
            "land_area": enterprise.land_area,
            "building_area": enterprise.building_area,
            "safety_officer": enterprise.safety_officer,
            "safety_standardization": enterprise.safety_standardization,
            "fire_approval": enterprise.fire_approval,
            "main_products": enterprise.main_products,
            "hazardous_chemicals": enterprise.hazardous_chemicals,
            "special_equipment": enterprise.special_equipment,
            "business_scope": enterprise.business_scope,
            "surrounding_info": enterprise.surrounding_info,
            "fire_protection_summary": enterprise.fire_protection_summary,
            "special_equipment_detail": enterprise.special_equipment_detail,
            "main_equipment_list": enterprise.main_equipment_list,
            "natural_conditions": enterprise.natural_conditions,
        },
        "internal_resources": [
            {
                "category": r.category,
                "name": r.name,
                "specification": r.specification,
                "quantity": r.quantity,
                "unit": r.unit,
                "location": r.location,
                "responsible_person": r.responsible_person,
                "contact_phone": r.contact_phone,
            }
            for r in internal
        ],
        "external_resources": [
            {
                "category": r.category,
                "name": r.name,
                "address": r.external_address,
                "distance_km": r.external_distance_km,
                "contact_phone": r.contact_phone,
                "responsible_person": r.responsible_person,
            }
            for r in external
        ],
        "risk_conclusion": risk_conclusion,
        "top_risks": top_risks,
    }


SYSTEM_PROMPT = """你是一位持有国家注册安全工程师资格的应急管理专家，具有丰富的生产经营单位应急资源调查与评估经验。你精通以下标准和法律法规：

【技术标准】
- 《应急物资分类及编码》（GB/T 38565）
- 《生产经营单位生产安全事故应急预案编制导则》（GB/T 29639-2020）

【法律法规】
- 《中华人民共和国安全生产法》
- 《中华人民共和国消防法》
- 《生产安全事故应急预案管理办法》
- 《生产安全事故应急条例》

你的任务是根据企业提供的应急资源数据、风险评估结论和组织架构信息，撰写一份完整、专业、合规的《应急资源调查报告》。

【写作风格——必须严格遵守】

一、公文语体要求
1. 使用正式的政府公文语体，语言规范、简洁、专业。
2. 高频动词使用：贯彻落实、贯彻执行、组织开展、负责、协调、配合、调查、保障、配备、储备、依托、建立、签订。
3. 避免口语化表达、修辞性语言、主观评论。不使用"应该""大概""也许"等不确定词汇。
4. 开篇格式：

二、术语标准
1. 应急组织统一用："应急救援指挥部""总指挥""副总指挥""应急救援小组""抢险救援组""通讯联络组""警戒疏散组""后勤保障组""医疗救护组"。
2. 外部力量描述范式：名称（距离XX公里，约XX分钟车程/响应时间）。
3. 物资描述范式：类别->名称->规格->数量->存放位置->责任人（联系电话）。
4. 差距分析结论格式："通过对XX的应急物资调查和分析，建议XX补充XX等物资。"

三、报告结构范式

单位内部应急资源部分：
1. 应急组织机构及职责（指挥部组成名单+各小组组长/成员+具体职责）
2. 应急物资保障（分类物资清单，含名称/规格/数量/存放位置/责任人）
3. 应急通信与信息保障（24小时应急电话、内外部通讯录）
4. 交通运输保障
5. 应急资金保障（安全生产专项经费、专款专用）
6. 应急队伍保障
7. 医疗保障
8. 治安保障

单位外部应急资源部分：
逐项列出消防队、公安部门、应急管理部门、医疗单位、交警部门、供电公司、燃气公司等，每项说明名称、距离、响应时间、主要职能。

应急资源差距分析部分：
1. 应急物资分析（现有资源是否满足主要风险场景需求）
2. 应急物资补充建议（具体列出建议补充的物资名称和数量）
3. 完善应急资源的具体措施（储备管理、采购制度、监督检查）

四、写作范式参考

示例——应急职责描述：
"抢险救援组：熟悉各种灭火器材、安全设施、救护器材的用途、操作方法、存放地点及使用范围。在事故发生后，负责第一时间按预定方案进行消防控制、协助涉险人员脱险等处理。负责事故现场切断电源等。"

示例——外部资源描述：
"中国消防救援（距离酒店5.8公里，约20分钟车程）：主要在发生事故后，进行现场灭火和救助。"

示例——差距分析：
"通过对酒店的应急物资调查和分析，建议酒店补充警戒线5卷、警戒锥桶10个、医用担架1副、医用氧气袋2个等物资。酒店消防设施必须配备齐全，所有应急物资责任到人，加强监管和维护。"

五、强制输出格式
1. 使用正式公文体，语言规范、简洁、专业，段落分明
2. 禁止使用 Markdown 格式符号（#、##、*、**、_、- 等）。章节标题使用中文序号（一、二、三...）加空格即可
3. 每个章节之间空一行分隔，章节标题独占一行
4. 列表内容使用"1）2）3）"编号，不使用 - 或 * 符号
5. 表格数据用文字描述或分行列举，不使用 | 制表符
6. 内容必须基于企业实际数据，数据缺失处标注"（待补充）"
7. 直接输出报告正文，不要加任何前言、后记或说明性文字
8. 报告应充分体现企业已录入的应急物资、风险源、周边环境等数据，不得遗漏重要信息"""

def _get_ri_system_prompt() -> str:
    """获取应急资源调查系统提示词，优先从数据库取。"""
    cached = get_report_system_prompt("resource_investigation_system")
    return cached if cached else SYSTEM_PROMPT


CHAPTER_DEFINITIONS = [
    {
        "key": "ch1_purpose",
        "title": "一、调查目的与依据",
        "instruction": (
            "你是应急管理专家。请撰写应急资源调查报告的「一、调查目的与依据」章节。\n\n"
            "内容包括：\n"
            "1）调查背景——说明为何开展本次应急资源调查\n"
            "2）调查目的——明确调查想要达到的目标\n"
            "3）调查依据——列出相关法律法规和标准规范\n"
            "4）调查范围——说明本次调查覆盖的资源类型和区域范围\n\n"
            "【输出要求】直接输出本章正文，语言规范简洁。字数 300-500 字。禁止使用 Markdown 符号。"
        ),
    },
    {
        "key": "ch2_basic_info",
        "title": "二、企业基本情况与风险概况",
        "instruction": (
            "你是应急管理专家。请撰写应急资源调查报告的「二、企业基本情况与风险概况」章节。\n\n"
            "内容包括：\n"
            "1）企业基本信息概述\n"
            "2）组织架构与安全管理体系\n"
            "3）风险概况——引用风险评估结论，概述主要风险类型和等级\n"
            "4）应急管理形势——说明企业应急资源需求的总体现状\n\n"
            "【输出要求】数据缺失处标注「（待补充）」。字数 400-600 字。禁止使用 Markdown 符号。"
        ),
    },
    {
        "key": "ch3_internal",
        "title": "三、内部应急资源调查",
        "instruction": (
            "你是应急资源调查专家。请撰写「三、内部应急资源调查」章节。\n\n"
            "请按以下类别逐一清点：\n"
            "1）消防设施 2）急救物资 3）防护装备 4）通讯设备\n"
            "5）照明设备 6）破拆工具 7）侦检设备 8）堵漏器材 9）其他\n\n"
            "每类列出名称、规格、数量、存放位置、责任人。\n"
            "某类不具备时说明「该类别暂无配置」。\n\n"
            "【输出要求】数据须基于实际录入数据，不得编造。字数 800-1200 字。禁止使用 Markdown 符号。"
        ),
    },
    {
        "key": "ch4_external",
        "title": "四、外部救援资源调查",
        "instruction": (
            "你是应急资源调查专家。请撰写「四、外部救援资源调查」章节。\n\n"
            "请逐项说明：\n"
            "1）消防力量 2）医疗力量 3）公安力量\n"
            "4）应急管理部门 5）环保部门 6）其他可依托力量\n\n"
            "每项说明名称、地址、距离、联系方式、救援能力。\n\n"
            "【输出要求】数据须基于实际录入数据。字数 600-900 字。禁止使用 Markdown 符号。"
        ),
    },
    {
        "key": "ch5_gap_analysis",
        "title": "五、应急资源需求与能力评估",
        "instruction": (
            "你是应急管理专家。请撰写「五、应急资源需求与能力评估」章节。\n\n"
            "请逐项评估：\n"
            "1）针对各主要风险场景，分析需要哪些应急资源\n"
            "2）对照现有内部资源，判断是否充足\n"
            "3）对照外部可依托资源，判断响应时间\n"
            "4）识别资源缺口——具体说明缺什么、为什么缺、建议补充什么、预估数量\n\n"
            "【输出要求】缺口分析必须具体、有针对性。字数 600-900 字。禁止使用 Markdown 符号。\n\n请在以上正文内容之后，额外输出一个 Mermaid flowchart 流程图，描述「应急资源调查与评估流程」。\n要求：\n1. 使用 flowchart TD（自上而下）布局\n2. 包含关键节点：确定调查范围→内部资源清点→外部资源调查→风险场景需求分析→资源缺口识别→补充建议→结论\n3. 节点用方括号[]表示，决策节点用菱形{}表示\n4. 流程图放在单独的 ```mermaid 代码块中，放在章节正文末尾\n5. 节点文字使用中文，简洁明了（每节点不超过15个字）"
        ),
    },
    {
        "key": "ch6_conclusion",
        "title": "六、调查结论与建议",
        "instruction": (
            "你是应急管理专家。请撰写「六、调查结论与建议」章节。\n\n"
            "内容包括：\n"
            "（一）综合评估结论——对应急资源整体状况给出定性判断\n"
            "（二）资源补充计划——优先整改项/重点加强项/持续改进项\n"
            "（三）管理改进建议——制度、培训演练、协议管理\n\n"
            "【输出要求】建议须具体可操作。字数 500-800 字。禁止使用 Markdown 符号。\n\n请在「管理改进建议」之后，输出以下JSON摘要（不要markdown代码块，直接输出纯JSON）：\n{\"internal_resource_count\":N,\"external_resource_count\":N,\"internal_by_category\":{\"<类别>\":N},\"external_by_category\":{\"<类别>\":N},\"resource_gaps\":[{\"category\":\"\",\"needed\":\"\",\"reason\":\"\",\"severity\":\"\"}],\"key_findings\":[\"发现1\"],\"overall_assessment\":\"一句话综合评估结论\"}"
        ),
    },
]


def build_chapter_prompt(chapter_key, context, previous_chapters=None, custom_instruction=None):
    enterprise = context["enterprise"]
    internal = context.get("internal_resources", [])
    external = context.get("external_resources", [])
    risk_conclusion = context.get("risk_conclusion")
    top_risks = context.get("top_risks", [])

    chapter_def = next((c for c in CHAPTER_DEFINITIONS if c["key"] == chapter_key), None)
    if not chapter_def:
        raise ValueError("Unknown chapter key: " + chapter_key)

    chapter_title = chapter_def["title"]
    tmpl = get_report_section_prompt("resource_investigation_section", chapter_key)
    if tmpl and tmpl.get("user_prompt_template"):
        chapter_instruction = tmpl["user_prompt_template"]
    else:
        chapter_instruction = chapter_def["instruction"]

    lines_out = [
        "请撰写应急资源调查报告的" + chapter_title + "章节。",
        "",
        "【企业基本信息】",
        "企业名称：" + str(enterprise.get("name", "")),
        "行业类型：" + str(enterprise.get("industry", "")),
        "地址：" + str(enterprise.get("address", "")),
        "员工人数：" + str(enterprise.get("employee_count", "")),
        "建筑概况：" + str(enterprise.get("building_overview", "") or "（待补充）"),
        "经营范围：" + str(enterprise.get("business_scope", "") or "（待补充）"),
        "周边环境：" + str(enterprise.get("surrounding_info", "") or "（待补充）"),
        "消防设施概况：" + str(enterprise.get("fire_protection_summary", "") or "（待补充）"),
        "特种设备详情：" + str(enterprise.get("special_equipment_detail", "") or "（待补充）"),
        "主要设备清单：" + str(enterprise.get("main_equipment_list", "") or "（待补充）"),
        "自然条件：" + str(enterprise.get("natural_conditions", "") or "（待补充）"),
        "",
        "【风险评估结论】",
    ]
    if risk_conclusion is not None:
        lines_out.append(risk_conclusion)
    else:
        lines_out.append("（尚未完成风险评估，本章请基于企业基本信息和已录入的风险源数据进行评估）")

    if top_risks:
        lines_out.append("")
        lines_out.append("主要风险：")
        for tr in top_risks:
            lines_out.append(
                tr.get("name", "") + "（" + tr.get("risk_level", "")
                + "）——" + tr.get("location", "")
            )

    lines_out.append("")
    lines_out.append("【内部应急资源清单（共 " + str(len(internal)) + " 项）】")
    idx = 1
    for r in internal:
        lines_out.append(
            str(idx) + "）[" + str(r.get("category", "")) + "] " + str(r.get("name", ""))
            + " （" + str(r.get("specification", "")) + "，" + str(r.get("quantity", 0))
            + str(r.get("unit", "个")) + "）"
            + "存放位置：" + str(r.get("location", "")) + "，"
            + "责任人：" + str(r.get("responsible_person", ""))
            + "（" + str(r.get("contact_phone", "")) + "）"
        )
        idx += 1

    lines_out.append("")
    lines_out.append("【外部救援资源清单（共 " + str(len(external)) + " 项）】")
    idx = 1
    for r in external:
        lines_out.append(
            str(idx) + "）[" + str(r.get("category", "")) + "] " + str(r.get("name", ""))
            + " 地址：" + str(r.get("address", "")) + "，"
            + "距离：约" + str(r.get("distance_km", "")) + "公里，"
            + "联系电话：" + str(r.get("contact_phone", "")) + "，"
            + "联系人：" + str(r.get("responsible_person", ""))
        )
        idx += 1

    if previous_chapters:
        lines_out.append("")
        lines_out.append("【前面章节内容（供参考，保持一致性）】")
        for prev in previous_chapters:
            lines_out.append("--- " + prev["title"] + " ---")
            lines_out.append(prev["content"])
            lines_out.append("")
        lines_out.append("请确保本章内容与前面章节一致，不要重复或矛盾。")
        lines_out.append("")

    lines_out.append("【本章写作要求】")
    lines_out.append(chapter_instruction)
    lines_out.append("")
    lines_out.append("【格式要求——必须遵守】")
    lines_out.append("1）直接输出本章正文，不要输出章节标题（系统自动添加），不要加任何前言")
    lines_out.append("2）禁止使用 Markdown 符号（# * - _ | 等）")
    lines_out.append("3）列表项使用「1）2）3）」格式编号")
    lines_out.append("4）段落之间空行分隔")
    lines_out.append("5）数据缺失处标注「（待补充）」")

    if custom_instruction:
        lines_out.append("")
        lines_out.append("【用户补充要求】")
        lines_out.append(custom_instruction)

    prompt = "\n".join(lines_out)
    try:
        prompt = inject_regulations(
            plan_type="resource_investigation",
            section_key=chapter_key,
            section_title=chapter_title,
            prompt=prompt,
            enterprise_data=context.get("enterprise", {}),
        )
    except Exception:
        pass
    return prompt


def get_chapter_keys():
    return [c["key"] for c in CHAPTER_DEFINITIONS]


def get_chapter_title(chapter_key):
    for c in CHAPTER_DEFINITIONS:
        if c["key"] == chapter_key:
            return c["title"]
    return chapter_key

