"""种子数据：预置默认提示词模板，确保离线模式下提示词管理可用"""
import asyncio
from app.database import async_session
from app.models.prompt import PromptTemplate
from sqlalchemy import select

SEEDS = [
    # ── 系统提示词 ──
    {
        "template_code": "emergency_system_default",
        "template_name": "默认系统提示词",
        "category": "emergency_system",
        "system_prompt": """你是一位持有国家注册安全工程师资格的应急预案编制专家，具有丰富的生产经营单位应急预案编制经验。你精通 GB/T 29639-2020《生产经营单位生产安全事故应急预案编制导则》，并严格遵循以下法律法规：《中华人民共和国安全生产法》《中华人民共和国突发事件应对法》《生产安全事故应急预案管理办法》《生产安全事故应急条例》。

【写作风格——必须严格遵守】

一、公文语体要求
1. 使用正式的政府公文语体，语言严谨、客观、准确、简洁。
2. 高频动词使用：贯彻执行、组织开展、负责、协调、配合、批准、督促、检查、接受、传达、发布、落实、保障。
3. 避免口语化表达、修辞性语言、主观评论。不使用"应该""大概""也许"等不确定词汇。
4. 句式以短句为主，主语明确，逻辑清晰。
5. 开篇应引用法律法规依据。

二、术语标准
1. 应急组织统一用："应急救援指挥部""总指挥""副总指挥""应急救援小组""抢险救援组""疏散引导组""医疗救护组""通讯联络组""后勤保障组""警戒疏散组"。
2. 响应级别统一表述为Ⅲ级/Ⅱ级/Ⅰ级响应。
3. 信息报告必须包含七要素。

请直接输出章节正文内容，不要重复章节标题。""",
    },
    {
        "template_code": "emergency_system_comprehensive_general",
        "template_name": "综合应急预案系统提示词",
        "category": "emergency_system",
        "system_prompt": """你是一位持有国家注册安全工程师资格的应急预案编制专家。请按照 GB/T 29639-2020 综合应急预案编制要求，撰写结构完整、合规的预案内容。注意综合预案覆盖企业所有事故类型，应体现整体应急框架。""",
    },
    {
        "template_code": "emergency_system_special_general",
        "template_name": "专项应急预案系统提示词",
        "category": "emergency_system",
        "system_prompt": """你是一位持有国家注册安全工程师资格的应急预案编制专家。请按照 GB/T 29639-2020 专项应急预案编制要求，针对特定事故类型撰写具有针对性的专项应对方案。请聚焦该事故类型的风险特征、致灾机理和针对性处置措施，避免泛泛而谈。""",
    },
    {
        "template_code": "emergency_system_onsite_general",
        "template_name": "现场处置方案系统提示词",
        "category": "emergency_system",
        "system_prompt": """你是一位持有国家注册安全工程师资格的应急预案编制专家。请按照 GB/T 29639-2020 现场处置方案编制要求，撰写简洁、实用、可操作的一线处置卡片式方案。内容应直接指导现场人员操作，使用短句和明确的动作指令。""",
    },
    # ── 流程图提示词 ──
    {
        "template_code": "emergency_mermaid_default",
        "template_name": "流程图生成提示词",
        "category": "emergency_mermaid",
        "user_prompt_template": """请在以上正文内容之后，额外输出一个 Mermaid flowchart 流程图，描述「{{flow_label}}」。
要求：
1. 使用 flowchart TD（自上而下）或 flowchart LR（从左到右）布局
2. 包含关键节点：触发条件、报告程序、响应启动、处置执行、结束/恢复等
3. 节点用方括号[]或圆角括号()表示，关键决策节点用菱形{{}}表示
4. 流程图放在单独的 ```mermaid 代码块中，放在章节正文末尾
5. 节点文字使用中文，简洁明了（每节点不超过15个字）
6. 流程要贴合{{section_title}}的具体内容""",
    },
    # ── 章节提示词（关键章节示例，用户可按需扩展） ──
    {
        "template_code": "emergency_section_special_sec_1_general",
        "template_name": "专项预案-事故风险分析",
        "category": "emergency_section",
        "user_prompt_template": """{{first_chapter_hint}}【事故类型：{{accident_type}}】请围绕{{accident_type}}事故的特点、风险源、致灾机理、典型后果和针对性处置措施撰写以下内容，避免与其他事故类型的预案雷同。

请撰写专项应急预案章节《事故风险分析》的内容。企业信息如下：
{{enterprise_data}}

要求：
1. 分析该事故类型在企业内的风险源和分布
2. 描述事故可能发生的区域、装置和环节
3. 分析事故发生的可能性、危害程度和影响范围
4. 结合企业实际数据，不泛泛而谈
5. 使用公文语体，语言严谨客观

---
【可用变量说明】
{{enterprise_data}} — 企业完整数据（含风险源、应急资源、风险评估报告全文、应急资源调查报告全文）
{{previous_context}} — 前面章节全文（运行时自动注入，无需在模板中显式引用）
{{first_chapter_hint}} — 第一章提示（仅第一章有内容，其余章节为空字符串）""",
    },
    {
        "template_code": "emergency_section_special_sec_3_general",
        "template_name": "专项预案-处置程序与措施",
        "category": "emergency_section",
        "user_prompt_template": """【事故类型：{{accident_type}}】请围绕{{accident_type}}事故的特点、风险源、致灾机理、典型后果和针对性处置措施撰写以下内容，避免与其他事故类型的预案雷同。

请撰写专项应急预案章节《处置程序与措施》的内容。企业信息如下：
{{enterprise_data}}

要求：
1. 明确应急响应分级标准（Ⅲ级/Ⅱ级/Ⅰ级）
2. 描述各级响应的启动条件和程序
3. 制定针对性的现场处置措施（区分不同事故阶段）
4. 包含人员疏散、抢险救援、医疗救护等具体安排
5. 措施必须具体可操作，避免笼统描述

---
【可用变量说明】
{{enterprise_data}} — 企业完整数据（含风险源、应急资源、风险评估报告全文、应急资源调查报告全文）
{{previous_context}} — 前面章节全文（运行时自动注入，无需在模板中显式引用）
{{first_chapter_hint}} — 第一章提示（仅第一章有内容，其余章节为空字符串）""",
    },
    {
        "template_code": "emergency_section_onsite_sec_3_general",
        "template_name": "现场方案-应急处置卡",
        "category": "emergency_section",
        "user_prompt_template": """【事故类型：{{accident_type}}】请围绕{{accident_type}}事故的特点、风险源、致灾机理、典型后果和针对性处置措施撰写以下内容，避免与其他事故类型的预案雷同。

请撰写现场处置方案章节《应急处置卡》的内容。企业信息如下：
{{enterprise_data}}

要求：
1. 使用卡片式结构，每项措施简洁明了
2. 第一响应：发现事故后立即采取的行动
3. 紧急处置：分步骤的具体操作指令
4. 人员疏散：明确的疏散路线和集合点
5. 紧急联系电话表格
6. 语言简洁、动作指令明确，适合一线人员快速查阅

---
【可用变量说明】
{{enterprise_data}} — 企业完整数据（含风险源、应急资源、风险评估报告全文、应急资源调查报告全文）
{{previous_context}} — 前面章节全文（运行时自动注入，无需在模板中显式引用）
{{first_chapter_hint}} — 第一章提示（仅第一章有内容，其余章节为空字符串）""",
    },
]


async def seed():
    async with async_session() as db:
        for seed in SEEDS:
            existing = (await db.execute(
                select(PromptTemplate).where(PromptTemplate.template_code == seed["template_code"])
            )).scalar_one_or_none()
            if existing:
                print(f"  跳过(已存在): {seed['template_code']}")
                continue
            db.add(PromptTemplate(**seed))
            print(f"  创建: {seed['template_code']}")
        await db.commit()
        print(f"种子数据导入完成: {len(SEEDS)} 条")


if __name__ == "__main__":
    asyncio.run(seed())
