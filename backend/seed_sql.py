#!/usr/bin/env python3
"""SQL直写数据迁移脚本：将硬编码提示词和字典写入中台 + 本地DB

通过 asyncpg 直连两边的 PostgreSQL：
  - 中台DB：localhost:5432 (ywt_user / yewuzhongtai / ywt)
  - 预案DB：localhost:5438 (postgres / postgres / emergency_plan)
"""

import asyncio
import asyncpg
import json


# ── 提示词模板数据 ──
PROMPT_TEMPLATES = [
    {
        "template_code": "emergency_system_default",
        "template_name": "系统提示词 - 应急预案编制专家",
        "category": "emergency_system",
        "system_prompt": """你是一位持有国家注册安全工程师资格的应急预案编制专家，具有丰富的生产经营单位应急预案编制经验。你精通 GB/T 29639-2020《生产经营单位生产安全事故应急预案编制导则》，并严格遵循以下法律法规：《中华人民共和国安全生产法》《中华人民共和国突发事件应对法》《生产安全事故应急预案管理办法》《生产安全事故应急条例》。

【写作风格——必须严格遵守】
一、公文语体要求：使用正式的政府公文语体，语言严谨、客观、准确、简洁。
二、结构范式：综合/专项/现场处置方案各有章节顺序。
三、术语标准：应急救援指挥部/总指挥/副总指挥/抢险救援组/疏散引导组/医疗救护组/通讯联络组/后勤保障组/警戒疏散组。
四、具体化要求：充分利用企业信息填入正文，不得使用占位符。
五、Markdown格式要求：使用###标题，表格用|---|格式，列表前后有空行。

请直接输出章节正文内容，不要重复章节标题。""",
        "user_prompt_template": "",
        "variables": "{}",
        "description": "全局系统提示词 - 用于所有章节生成",
    },
    {
        "template_code": "emergency_section_ch1_hazard_id",
        "template_name": "风险评估 - 危险有害因素辨识分析",
        "category": "emergency_section",
        "system_prompt": "你是危险有害因素辨识专家，持有国家注册安全工程师资格。",
        "user_prompt_template": """请根据以下企业信息，按7个维度深入分析危险有害因素。

{{enterprise_data}}

按结构输出：（一）危险化学品（二）总平面布置（三）配电设施（四）消防设施（五）检维修施工（六）设备装置（七）经营过程。
每个子章节末尾用综上所述收尾。字数2000-3000字。""",
        "variables": '{"enterprise_data": "企业完整信息JSON"}',
        "description": "风险评估报告 - 第一章",
    },
    {
        "template_code": "emergency_section_ch2_summary",
        "template_name": "风险评估 - 危险有害因素辨识汇总",
        "category": "emergency_section",
        "system_prompt": "你是危险有害因素辨识汇总专家。",
        "user_prompt_template": """请根据前面已完成的危险有害因素辨识分析，输出两个汇总HTML表格。

{{enterprise_data}}

表1：危险有害因素辨识汇总表  表2：事故类型分布表
字数500-800字。""",
        "variables": '{"enterprise_data": "企业完整信息JSON"}',
        "description": "风险评估报告 - 第二章",
    },
    {
        "template_code": "emergency_section_ch3_risk_eval",
        "template_name": "风险评估 - 风险等级评估",
        "category": "emergency_section",
        "system_prompt": "你是风险评估专家，精通L×S风险矩阵评估法。",
        "user_prompt_template": """请根据前面已完成的风险辨识结果，进行L×S风险矩阵评估。

{{enterprise_data}}

输出标准HTML表格：L分级标准、S分级标准、风险等级判定表、L×S计算表、重大风险分析。
字数1500-2500字。""",
        "variables": '{"enterprise_data": "企业完整信息JSON"}',
        "description": "风险评估报告 - 第三章",
    },
    {
        "template_code": "emergency_section_ch4_measures",
        "template_name": "风险评估 - 现有管控措施评价",
        "category": "emergency_section",
        "system_prompt": "你是安全管理评价专家。",
        "user_prompt_template": """请根据风险源数据中记录的现有管控措施，逐项评价其有效性和充分性。

{{enterprise_data}}

至少覆盖所有重大和较大风险源。字数800-1200字。""",
        "variables": '{"enterprise_data": "企业完整信息JSON"}',
        "description": "风险评估报告 - 第四章",
    },
    {
        "template_code": "emergency_section_ch5_conclusion",
        "template_name": "风险评估 - 风险评估结论与建议",
        "category": "emergency_section",
        "system_prompt": "你是安全评估总结专家。",
        "user_prompt_template": """请基于前面的风险辨识和评估结果，撰写评估结论和管控建议。

{{enterprise_data}}

输出综合评估结论 + 优先整改项 / 重点加强项 / 持续改进项 / 日常管理项。
字数800-1200字。""",
        "variables": '{"enterprise_data": "企业完整信息JSON"}',
        "description": "风险评估报告 - 第五章",
    },
    {
        "template_code": "emergency_surrounding_system",
        "template_name": "周边环境 - 系统提示词",
        "category": "emergency_surrounding_system",
        "system_prompt": "你是一位持有国家注册安全工程师资格的专业应急预案编制专家，熟悉 GB/T 29639-2020 标准。从严、从细，覆盖 8 个方位和不同距离。严禁生成与已录入周边单位/敏感目标名称重复的数据。",
        "user_prompt_template": "",
        "variables": "{}",
        "description": "周边环境AI调查 - 系统角色提示词",
    },
    {
        "template_code": "emergency_surrounding_user",
        "template_name": "周边环境 - 用户提示词模板",
        "category": "emergency_surrounding_user",
        "system_prompt": "",
        "user_prompt_template": """请根据以下企业信息和已有数据，生成周边环境调查问题。

企业信息：{{enterprise_data}}
已有数据：{{existing_summary}}

以 JSON 输出：{"questions": [{"id": "q1", "question": "问题文本"}]}
每个板块至少 2 个问题。只输出 JSON。""",
        "variables": '{"enterprise_data": "企业完整信息", "existing_summary": "已录入周边数据摘要"}',
        "description": "周边环境AI调查 - 问题生成模板",
    },
    {
        "template_code": "emergency_mermaid_default",
        "template_name": "Mermaid 流程图 - 默认模板",
        "category": "emergency_mermaid",
        "system_prompt": "",
        "user_prompt_template": """在正文末尾输出 Mermaid flowchart 流程图，描述「{{flow_label}}」。
要求：flowchart TD 布局，包含触发条件→报告→响应→处置→恢复节点，关键决策用菱形，节点中文不超过15字。
放在 ```mermaid 代码块中。""",
        "variables": '{"flow_label": "流程图名称", "section_title": "章节标题"}',
        "description": "应急响应流程图生成模板",
    },
]


async def seed_ywt_prompts():
    """直接写入中台 ai_prompt_template 表"""
    conn = await asyncpg.connect(
        user="ywt_user", password="ywt_pass_2024",
        database="yewuzhongtai", host="localhost", port=5432
    )
    
    for p in PROMPT_TEMPLATES:
        # Check existence first
        existing = await conn.fetchval(
            "SELECT id FROM ai_prompt_template WHERE template_code = $1",
            p["template_code"]
        )
        if existing:
            print(f"  [SKIP] {p['template_code']} already exists (id={existing})")
            continue

        await conn.execute("""
            INSERT INTO ai_prompt_template 
            (template_code, template_name, system_prompt, user_prompt_template, variables, category, description, status)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, '0')
        """,
            p["template_code"], p["template_name"],
            p["system_prompt"], p["user_prompt_template"],
            p["variables"], p["category"], p["description"]
        )
        print(f"  [OK] {p['template_code']}")

    await conn.close()
    print(f"  Done: {len(PROMPT_TEMPLATES)} templates processed")


async def seed_local_configs():
    """写入预案系统 sys_config 表"""
    conn = await asyncpg.connect(
        user="postgres", password="postgres",
        database="emergency_plan", host="localhost", port=5438
    )

    defaults = [
        ("export_dir", "./exports", "string", "应急预案导出文件目录"),
        ("prompt_cache_ttl", "300", "int", "提示词缓存有效期（秒）"),
        ("surrounding_directions", '["N","NE","E","SE","S","SW","W","NW"]', "json", "周边环境8个方向枚举"),
        ("risk_matrix_l_scale", json.dumps({
            "5": "在现场没有采取防范、监测、保护、控制措施，或危害的发生不能被发现",
            "4": "危害的发生不容易被发现，现场没有检测系统",
            "3": "没有保护措施，或未严格按操作程序执行",
            "2": "危害一旦发生能及时发现，并定期进行监测",
            "1": "有充分有效的防范、控制、监测、保护措施",
        }, ensure_ascii=False), "json", "L量表（事故可能性）5级描述"),
        ("risk_matrix_s_scale", json.dumps({
            "5": "多人死亡或重大财产损失",
            "4": "一人死亡或较大财产损失",
            "3": "多人重伤或一般财产损失",
            "2": "一人重伤或轻微财产损失",
            "1": "轻微伤害或无财产损失",
        }, ensure_ascii=False), "json", "S量表（事故严重性）5级描述"),
    ]

    for key, value, ctype, desc in defaults:
        existing = await conn.fetchval(
            "SELECT id FROM sys_config WHERE config_key = $1", key
        )
        if existing:
            print(f"  [SKIP] {key} already exists")
            continue
        await conn.execute(
            "INSERT INTO sys_config (config_key, config_value, config_type, description) VALUES ($1, $2, $3, $4)",
            key, value, ctype, desc
        )
        print(f"  [OK] {key}")

    await conn.close()
    print(f"  Done: {len(defaults)} configs processed")


async def main():
    print("=" * 60)
    print("SQL 直写数据迁移")
    print("=" * 60)

    print("\n[1/2] 中台 ai_prompt_template (localhost:5432)...")
    await seed_ywt_prompts()

    print("\n[2/2] 本地 sys_config (localhost:5438)...")
    await seed_local_configs()

    print("\n" + "=" * 60)
    print("迁移完成！重启后端后提示词缓存将从中台加载。")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
