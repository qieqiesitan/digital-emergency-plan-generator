import json
import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.enterprise import Enterprise, RiskSource
from app.models.risk_assessment import RiskAssessmentReport
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 提示词缓存（延迟导入，避免循环引用）
from app.services.prompt_cache import get_report_system_prompt, get_report_section_prompt

RISK_ORDER = {"重大": 0, "较大": 1, "一般": 2, "低": 3}


async def build_risk_assessment_context(enterprise_id: str, db: AsyncSession) -> dict:
    enterprise_result = await db.execute(
        select(Enterprise).where(Enterprise.id == enterprise_id)
    )
    enterprise = enterprise_result.scalar_one_or_none()
    if not enterprise:
        raise ValueError("企业不存在")

    risk_result = await db.execute(
        select(RiskSource).where(RiskSource.enterprise_id == enterprise_id)
    )
    risk_sources = risk_result.scalars().all()
    risk_sources_sorted = sorted(
        risk_sources,
        key=lambda r: RISK_ORDER.get(r.risk_level or "低", 99),
    )

    return {
        "enterprise": {
            "name": enterprise.name,
            "industry": enterprise.industry,
            "address": enterprise.address,
            "employee_count": enterprise.employee_count,
            "business_scope": enterprise.business_scope,
            "building_overview": enterprise.building_overview,
            "surrounding_info": enterprise.surrounding_info,
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
            "fire_protection_summary": enterprise.fire_protection_summary,
            "special_equipment_detail": enterprise.special_equipment_detail,
            "main_equipment_list": enterprise.main_equipment_list,
            "natural_conditions": enterprise.natural_conditions,
        },
        "risk_sources": [
            {
                "name": rs.name,
                "categories": rs.categories,
                "location": rs.location,
                "description": rs.description,
                "likelihood": rs.likelihood,
                "severity": rs.severity,
                "risk_level": rs.risk_level,
                "control_measures": rs.control_measures,
            }
            for rs in risk_sources_sorted
        ],
    }


SYSTEM_PROMPT = """你是一位持有国家注册安全工程师资格的风险评估专家，具有丰富的生产经营单位事故风险评估经验。你精通以下标准和法律法规：

【技术标准】
- 《生产过程危险和有害因素分类与代码》（GB/T 13861-2022）
- 《企业职工伤亡事故分类》（GB 6441-1986）
- 《危险化学品目录（2022调整版）》
- 《危险货物品名表》（GB 12268-2012）
- 《建筑灭火器配置设计规范》（GB 50140-2005）
- 《用电安全导则》（GB/T 13869-2017）

【法律法规】
- 《中华人民共和国安全生产法》
- 《中华人民共和国消防法》
- 《中华人民共和国特种设备安全法》
- 《中华人民共和国突发事件应对法》
- 《生产安全事故报告和调查处理条例》
- 《生产安全事故应急条例》
- 《生产安全事故应急预案管理办法》
- 《工贸企业有限空间作业安全规定》

你的任务是撰写一份完整、专业、合规的《生产安全事故风险评估报告》。

【写作风格——必须严格遵守】

一、公文语体要求
1. 使用正式的政府公文语体，语言严谨、客观、准确、简洁。
2. 高频动词使用：辨识、分析、评估、确定、可能导致、存在、应设置、应配备、应定期、贯彻执行、督促检查。
3. 避免口语化表达、修辞性语言、主观评论。不使用"应该""大概""也许"等不确定词汇。
4. 每个辨识维度末尾统一用"综上所述，XX存在的危险因素有：XXX"收尾。
5. 综合评估结论统一格式：，语言准确、简洁、客观。像一位资深安全工程师在撰写内部技术报告，而不是写政府公文。
2. 自然使用技术术语，避免空洞的套话、重复性的句式、过度的法律条文引用。
3. 每个分析点都要有具体的、针对该企业实际情况的内容，不要通用模板化的描述。
4. 不要使用"综上所述……"等模板化收尾句式，每个分析维度自然结尾即可。

二、术语标准
1. 风险等级统一表述为：重大风险、较大风险、一般风险、低风险。
2. 事故类型统一按 GB 6441-1986 分类：物体打击、车辆伤害、机械伤害、起重伤害、触电、淹溾、灼烫、火灾、高处坠落、坍塌、锅炉爆炸、容器爆炸、其他爆炸、中毒和窒息、其他伤害。
3. 辨识维度统一为：危险化学品有害因素辨识、总平面布置及建（构）筑物危险有害因素分析、配电设施危险有害因素辨识分析、消防设施危险有害因素分析、检维修施工过程危险有害因素分析、设备装置危险有害因素分析、经营过程危险有害因素辨识分析、安全管理危险有害因素辨识分析。物体打击、车辆伤害、机械伤害、起重伤害、触电、淹溺、灼烫、火灾、高处坠落、坍塌、锅炉爆炸、容器爆炸、其他爆炸、中毒和窒息、其他伤害。

三、L\u00d7S 风险矩阵法标准定义（必须使用以下标准值）

事故发生的可能性（L）分级标准：
L=5：在现场没有采取防范、监测、保护、控制措施，或危害的发生不能被发现，或在正常情况下经常发生此类事故或事件。
L=4：危害的发生不容易被发现，现场没有检测系统，或控制措施未有效执行或不恰当，或危害常发生在预期情况下发生。
L=3：没有保护措施，或未严格按操作程序执行，或危害的发生容易被发现，或过去曾经发生类似事故或事件。
L=2：危害一旦发生能及时发现，并定期进行监测，或现场有防范控制措施并能有效执行，或过去偶尔发生事故或事件。
L=1：有充分有效的防范、控制、监测、保护措施，员工安全意识高，严格执行操作规程，极不可能发生事故。

风险等级判定标准：R=L\u00d7S。20-25\u2192重大风险（1级）\u2192立刻整改；15-16\u2192较大风险（2级）\u2192立即或近期整改；9-12\u2192一般风险（3级）\u21922年内治理；<8\u2192低风险（4级）\u2192有条件有经费时治理。

四、写作范式参考

示例——结论章节标准写法：
"本评估报告结论依据《生产安全事故应急预案管理办法》（中华人民共和国应急管理部令第2号）《生产过程危险和有害因素分类与代码》（GB/T 13861-2022）和《企业职工伤亡事故分类》（GB 6441-1986）等国家法律法规及国家、行业规范标准，对XX生产安全事故风险进行分析，得出以下评估结论：
XX在生产经营过程中主要可能发生的较大风险事故类型为：火灾、爆炸；一般风险事故类型为：触电、中毒和窒息、车辆伤害；低风险事故类型为：物体打击、高处坠落、灼伤、淹溺、起重伤害、机械伤害，引起事故的主要原因是设备设施故障、电缆线路老化、人员违规操作、安全管理不到位。"

五、强制输出格式
1. 所有表格必须使用 HTML <table> 标签输出，不得使用 Markdown 表格或文字描述代替
2. 涉及危险化学品的章节必须包含「理化特性及危害特性表」
3. 风险评估必须使用 L×S 风险矩阵法，采用 5 级量表（L: 1-5, S: 1-5, R = L×S）
4. 风险评估章节必须输出完整的「L×S 风险评估计算表」（含所有事故类型的 L、S、R 值和风险等级）
5. 报告以正式公文语言撰写，段落分明，章节标题使用中文序号（一、二、三…）
6. 内容必须基于企业实际数据，数据缺失处标注"（待补充）"
7. 直接输出报告正文，不要加任何前言、后记或说明性文字"""


def _get_ra_system_prompt() -> str:
    """获取风险评估系统提示词，优先从数据库取。"""
    cached = get_report_system_prompt("risk_assessment_system")
    return cached if cached else SYSTEM_PROMPT



def build_risk_prompt(context: dict, custom_instruction: str | None = None) -> str:
    enterprise = context["enterprise"]
    risk_sources = context["risk_sources"]

    lines = [
        "请根据以下企业信息和风险源数据，撰写一份完整的《事故风险评估报告》。",
        "",
        "【企业基本信息】",
        f"企业名称：{enterprise.get('name', '')}",
        f"统一社会信用代码：{enterprise.get('credit_code', '')}",
        f"法定代表人：{enterprise.get('legal_representative', '')}",
        f"成立日期：{enterprise.get('established_date', '')}",
        f"经济类型：{enterprise.get('economic_type', '')}",
        f"注册资本：{enterprise.get('registered_capital', '')}",
        f"行业类型：{enterprise.get('industry', '')}",
        f"地址：{enterprise.get('address', '')}",
        f"联系电话：{enterprise.get('phone', '')}",
        f"员工人数：{enterprise.get('employee_count', '')}",
        f"占地面积：{enterprise.get('land_area', '')}平方米",
        f"建筑面积：{enterprise.get('building_area', '')}平方米",
        f"建筑概况：{enterprise.get('building_overview', '')}",
        f"安全标准化等级：{enterprise.get('safety_standardization', '')}",
        f"消防审批情况：{enterprise.get('fire_approval', '')}",
        f"主要产品/业务：{enterprise.get('main_products', '')}",
        f"危险化学品情况：{enterprise.get('hazardous_chemicals', '')}",
        f"特种设备情况：{enterprise.get('special_equipment', '')}",
        "",
        "【组织架构与应急职责】",
        f"安全负责人：{enterprise.get('safety_officer', '')}",
        f"组织架构数据：{enterprise.get('org_structure', '')}",
        "",
        f"【风险源清单（共 {len(risk_sources)} 项）】",
    ]

    for i, rs in enumerate(risk_sources, 1):
        lines.append(f"{i}）风险源名称：{rs.get('name', '')}")
        lines.append(f"   风险类别：{rs.get('categories', '')}")
        lines.append(f"   所在位置：{rs.get('location', '')}")
        lines.append(f"   风险描述：{rs.get('description', '')}")
        lines.append(f"   可能性：{rs.get('likelihood', '')}")
        lines.append(f"   严重性：{rs.get('severity', '')}")
        lines.append(f"   风险等级：{rs.get('risk_level', '')}")
        lines.append(f"   现有管控措施：{rs.get('control_measures', '')}")
        lines.append("")

    lines.extend([
        "",
        "【报告结构要求——严格按以下格式输出，不得使用 Markdown 符号】",
        "",
        f"{enterprise.get('name', '企业')} 事故风险评估报告",
        "",
        "一、评估目的与依据",
        "简述评估背景、目的，列出依据的法律法规和技术标准。",
        "",
        "二、企业基本情况",
        "概述企业生产经营特点、厂区布局、周边环境、组织架构等基本信息。",
        "",
        "三、风险辨识",
        "（一）危险有害因素辨识",
        "按 GB/T 13861 分类，系统辨识企业存在的各类危险有害因素，说明分布位置和影响范围。",
        "（二）主要事故类型分析",
        "按 GB 6441 事故分类，列出企业可能发生的主要事故类型，分析每种类型的可能场景和触发条件。",
        "",
        "四、风险等级评估",
        "（一）评估方法与标准",
        "说明采用的评估方法（L\u00d7S 风险矩阵法）和风险等级划分标准。",
        "（二）风险评估结果",
        "对每项风险源给出评估结论，按风险等级从高到低排列，说明赋值依据。",
        "（三）重大风险分析",
        "对评定为重大风险的项目进行详细分析，说明可能造成的后果和影响范围。",
        "",
        "五、现有管控措施评价",
        "逐项评价现有管控措施的有效性和充分性，指出存在的不足和薄弱环节。",
        "",
        "六、风险评估结论与建议",
        "（一）综合评估结论",
        "对企业整体风险水平给出定性判断。",
        "（二）风险管控建议",
        "针对评估中发现的问题，提出具体、可操作的改进建议，按优先级排列。",
        "",
        "【输出格式要求——必须遵守】",
        "1）直接输出报告正文，不要加「以下是根据...」之类的前言",
        "2）不要使用任何 Markdown 标记符号",
        "3）章节标题使用「一、二、三\u2026」和「（一）（二）（三）\u2026」中文序号",
        "4）段落之间有明显的空行分隔",
        "5）列表项使用「1）2）3）」格式编号",
        "6）数据缺失处用「（待补充）」标注",
        "7）报告正文总字数控制在 3000-5000 字",
    ])

    if custom_instruction:
        lines.append("")
        lines.append("【用户补充要求】")
        lines.append(custom_instruction)

    return "\n".join(lines)


# L/S value normalizers
_LS_TEXT_MAP = {"\u9ad8": 4, "\u4e2d": 3, "\u4f4e": 2, "\u8f83\u9ad8": 4, "\u8f83\u4f4e": 2, "\u5f88\u9ad8": 5, "\u5f88\u4f4e": 1}

def _to_l_num(val):
    if isinstance(val, int):
        return max(1, min(5, val))
    if isinstance(val, str):
        v = val.strip()
        if v.isdigit():
            return max(1, min(5, int(v)))
        for k, num in sorted(_LS_TEXT_MAP.items(), key=lambda x: -len(x[0])):
            if k in v:
                return num
    return 3

def _to_s_num(val):
    if isinstance(val, int):
        return max(1, min(5, val))
    if isinstance(val, str):
        v = val.strip()
        if v.isdigit():
            return max(1, min(5, int(v)))
        for k, num in sorted(_LS_TEXT_MAP.items(), key=lambda x: -len(x[0])):
            if k in v:
                return num
    return 3


# ============================================================
# 逐章批量生成引擎
# ============================================================

CHAPTER_DEFINITIONS = [
    {
        "key": "ch1_hazard_id",
        "title": "一、危险有害因素辨识分析",
        "instruction": "你是危险有害因素辨识专家。请根据企业信息，按以下7个维度深入分析：\n\n（一）危险化学品有害因素辨识——根据企业涉及的危险化学品，分析其理化特性及危害特性。如有具体化学品，输出理化特性及危害特性表（HTML table）。\n\n（二）总平面布置及建（构）筑物危险有害因素分析——分析建筑布局、疏散通道、防护栏杆、防雷接地等。\n\n（三）配电设施危险有害因素辨识分析——分析电气线路、配电柜、开关、用电设备的电流热量、电气火花、短路、电弧、雷电、触电等风险。\n\n（四）消防设施危险有害因素分析——分析消防供水、灭火器材配置、自动报警/灭火系统、消防通道的充分性和有效性。\n\n（五）检维修施工过程危险有害因素分析——分析电气作业、高处作业、机械作业、有限空间作业中的爆炸、中毒、触电、坠落风险。\n\n（六）设备装置危险有害因素分析——逐类分析电气设备（触电/短路/电火花）、特种设备（电梯困人/剪切/坠落）、发电机（火灾/中毒/触电）、锅炉（爆炸/灼烧）等。\n\n（七）经营过程危险有害因素辨识分析——按火灾/爆炸、中毒和窒息、灼烧、触电、机械伤害、高处坠落、物体打击、车辆伤害、淹溺、其他伤害等事故类型，逐一分析触发场景和可能后果。\n\n【输出要求】每个子章节末尾用综上所述XX存在的危险因素有XX收尾。危险化学品如有数据输出HTML理化特性表。直接输出正文，字数4000-6000字。",
    },
    {
        "key": "ch2_summary",
        "title": "二、危险有害因素辨识汇总",
        "instruction": "请根据前面已完成的危险有害因素辨识分析，输出以下两个汇总HTML表格：\n\n表1：危险有害因素辨识汇总表（序号 | 辨识类型 | 事故类型）\n四种辨识类型：物质危险有害因素、自然条件危险有害因素、作业过程危险有害因素、设备设施危险有害因素\n\n表2：事故类型分布表（序号 | 事故种类 | 危险有害因素分布 | 危害后果 | 影响范围）\n\n【输出要求】直接输出两个HTML表格，表格前加简短引导语。内容必须基于前面辨识分析结果，不得凭空编造。字数800-1200字。",
    },
    {
        "key": "ch3_risk_eval",
        "title": "三、风险等级评估",
        "instruction": "请根据前面已完成的风险辨识结果，进行L\u00d7S风险矩阵评估。\n\n（一）评估方法与标准——说明采用L\u00d7S风险矩阵法（5级量表，L:1-5, S:1-5, R=L\u00d7S）。\n\n请输出以下三个标准HTML表格：\n\n表1：事故发生的可能性（L）分级标准（等级1-5 | 标准描述）\nL=5: 在现场没有采取防范、监测、保护、控制措施，或危害的发生不能被发现，或在正常情况经常发生此类事故或事件\nL=4: 危害的发生不容易被发现，现场没有检测系统，或控制措施未有效执行或不恰当，或危害常发生在预期情况下发生\nL=3: 没有保护措施，或未严格按操作程序执行，或危害的发生容易被发现，或过去曾经发生类似事故或事件\nL=2: 危害一旦发生能及时发现，并定期进行监测，或现场有防范控制措施并能有效执行，或过去偶尔发生事故或事件\nL=1: 有充分有效的防范、控制、监测、保护措施，员工安全意识高，严格执行操作规程，极不可能发生事故\n\n表2：事故后果严重程度（S）分级标准（等级1-5 | 法律法规及其他要求 | 人员 | 财产损失/万元 | 停止运营 | 企业形象）\n包含5级完整描述，每级覆盖5个维度\n\n表3：风险等级判定及控制措施（风险度 | 等级 | 应采取的行动/控制措施 | 实施期限）\n20-25\u21921级重大\u2192立刻 | 15-16\u21922级较大\u2192立即或近期整改 | 9-12\u21923级一般\u21922年内治理 | <8\u21924级低\u2192有条件有经费时治理\n\n（二）L\u00d7S风险评估计算表——对前面辨识出的所有事故类型逐项计算，输出HTML表格：序号 | 事故类型 | L | S | R | 风险等级\n\n（三）重大风险分析——对R\u226520的项目详细分析后果和影响范围。\n\n【输出要求】所有表格使用HTML table格式。L/S值须结合企业实际合理赋值。字数2000-3500字。",
    },
    {
        "key": "ch4_measures",
        "title": "四、现有管控措施评价",
        "instruction": "请根据风险源数据中记录的现有管控措施，逐项评价其有效性和充分性。\n\n对每项重大和较大风险源对应的管控措施进行评价，格式如下：\n1）风险源名称：XXX\n   现有措施：XXX\n   评价：XXX（指出优点和不足）\n   定性：有效/基本有效/需改进\n\n【输出要求】直接输出正文，评价应具体有针对性。至少覆盖所有重大和较大风险源。字数800-1500字。",
    },
    {
        "key": "ch5_conclusion",
        "title": "五、风险评估结论与建议",
        "instruction": "请基于前面的风险辨识和评估结果，撰写评估结论和管控建议。\n\n（一）综合评估结论——对企业整体风险水平给出定性判断，包括整体风险等级、主要风险特征概括、风险管控紧迫性判断。\n\n（二）风险管控建议——按优先级提出具体可操作的改进建议：\n1）优先整改项（与重大风险直接相关）\n2）重点加强项（与较大风险相关）\n3）持续改进项（一般风险）\n4）日常管理项（低风险）\n\n每条建议含：针对什么风险、具体做什么、达到什么目标。字数800-1500字。",
    }
]


def build_chapter_prompt(chapter_key, context, previous_chapters=None, custom_instruction=None):
    enterprise = context["enterprise"]
    risk_sources = context["risk_sources"]
    for rs in risk_sources:
        rs["_l_num"] = _to_l_num(rs.get("likelihood", 2))
        rs["_s_num"] = _to_s_num(rs.get("severity", 2))
    chapter_def = next((c for c in CHAPTER_DEFINITIONS if c["key"] == chapter_key), None)
    if not chapter_def:
        raise ValueError("Unknown chapter key: " + chapter_key)
    chapter_title = chapter_def["title"]
    # 尝试从数据库模板获取章节指令，未命中则用硬编码兜底
    tmpl = get_report_section_prompt("risk_assessment_section", chapter_key)
    if tmpl and tmpl.get("user_prompt_template"):
        chapter_instruction = tmpl["user_prompt_template"]
    else:
        chapter_instruction = chapter_def["instruction"]
    lines_out = [
        "请撰写风险评估报告的" + chapter_title + "章节。",
        "",
        "【企业基本信息】",
        "企业名称：" + str(enterprise.get("name", "")),
        "行业类型：" + str(enterprise.get("industry", "")),
        "地址：" + str(enterprise.get("address", "")),
        "员工人数：" + str(enterprise.get("employee_count", "")),
        "经营范围：" + str(enterprise.get("business_scope", "")),
        "建筑概况：" + str(enterprise.get("building_overview", "") or "（待补充）"),
        "周边环境：" + str(enterprise.get("surrounding_info", "") or "（待补充）"),
    "消防设施概况：" + str(enterprise.get("fire_protection_summary", "") or "（待补充）"),
    "特种设备详情：" + str(enterprise.get("special_equipment_detail", "") or "（待补充）"),
    "主要设备清单：" + str(enterprise.get("main_equipment_list", "") or "（待补充）"),
    "自然条件：" + str(enterprise.get("natural_conditions", "") or "（待补充）"),
    ]
    extra_fields = {
        "主要产品/服务": enterprise.get("main_products"),
        "危险化学品": enterprise.get("hazardous_chemicals"),
        "特种设备": enterprise.get("special_equipment"),
    }
    for label, val in extra_fields.items():
        if val:
            lines_out.append(label + "：" + str(val))
    lines_out.append("")
    lines_out.append("【风险源清单（共 " + str(len(risk_sources)) + " 项）】")
    for i, rs in enumerate(risk_sources, 1):
        lines_out.append(str(i) + "）风险源名称：" + str(rs.get("name", "")))
        lines_out.append("   风险类别：" + str(rs.get("categories", "")))
        lines_out.append("   所在位置：" + str(rs.get("location", "")))
        lines_out.append("   风险描述：" + str(rs.get("description", "")))
        lines_out.append("   可能性参考：L级" + str(rs.get("_l_num", 2)) + "级)")
        lines_out.append("   严重性参考：S级" + str(rs.get("_s_num", 2)) + "级)")
        lines_out.append("   风险等级参考：" + str(rs.get("risk_level", "")))
        lines_out.append("   现有管控措施：" + str(rs.get("control_measures", "")))
        lines_out.append("")
    if previous_chapters:
        lines_out.append("【前面章节内容（供参考，保持一致）】")
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
    lines_out.append("1）直接输出本章正文，不要加任何前言")
    lines_out.append("2）表格使用HTML table标签，border=1 cellpadding=4 cellspacing=0")
    lines_out.append("3）列表项使用1）2）3）格式编号")
    lines_out.append("4）段落之间空行分隔")
    lines_out.append("5）内容必须基于企业实际数据，缺失处标注（待补充）")
    if custom_instruction:
        lines_out.append("")
        lines_out.append("【用户补充要求】")
        lines_out.append(custom_instruction)
    return "\n".join(lines_out)


def get_chapter_keys():
    return [c["key"] for c in CHAPTER_DEFINITIONS]


def get_chapter_title(chapter_key):
    for c in CHAPTER_DEFINITIONS:
        if c["key"] == chapter_key:
            return c["title"]
    return chapter_key


SUMMARY_EXTRACTION_PROMPT = """
请从以下风险评估报告中提取结构化摘要，仅返回 JSON（不要 Markdown 代码块）：

{
  "risk_source_count": <数字>,
  "risk_level_distribution": {"重大": <N>, "较大": <N>, "一般": <N>, "低": <N>},
  "top_risks": [
    {"name": "", "category": "", "risk_level": "", "likelihood": "", "severity": "", "location": "", "key_control_measures": ""}
  ],
  "risk_by_category": {"<类别名>": <N>},
  "key_findings": ["发现1", "发现2"],
  "overall_assessment": "一句话综合评估结论"
}

报告内容：
"""


async def extract_summary_from_content(content: str, stream_llm_fn) -> dict:
    """Call LLM to extract structured summary from the full report content."""
    try:
        prompt = SUMMARY_EXTRACTION_PROMPT + content[:8000]
        raw = await stream_llm_fn(prompt)
        raw = raw.strip()
        if raw.startswith("`"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("`"):
                raw = raw[:-3]
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Summary extraction failed: {e}")
        return {
            "risk_source_count": 0,
            "risk_level_distribution": {},
            "top_risks": [],
            "risk_by_category": {},
            "key_findings": [],
            "overall_assessment": "",
        }
