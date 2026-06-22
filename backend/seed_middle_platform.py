#!/usr/bin/env python3
"""数据迁移脚本：将硬编码提示词和字典迁移到业务中台

用法:
  cd backend
  .venv\Scripts\python.exe seed_middle_platform.py

将执行:
  1. 提示词模板 → 中台 ai_prompt_template（通过 /ai/prompt API）
  2. 字典数据 → 中台 sys_dict_data（直接SQL，因API需要更高权限）
  3. 系统配置 → 本地 sys_config（通过本地API / 当前代码的 set_config）
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import ywt_client
from app.services.prompt_cache import FALLBACK_SYSTEM_PROMPT


# ── 章节提示词（来自 _chapter_data.json）──
SECTION_PROMPTS = [
    {
        "template_code": "emergency_section_ch1_hazard_id",
        "template_name": "风险评估 - 危险有害因素辨识分析",
        "category": "emergency_section",
        "system_prompt": "你是危险有害因素辨识专家，持有国家注册安全工程师资格。",
        "user_prompt_template": """请根据以下企业信息，按7个维度深入分析危险有害因素。

企业信息：
{{enterprise_data}}

按以下结构输出：
（一）危险化学品有害因素辨识
（二）总平面布置及建（构）筑物危险有害因素分析
（三）配电设施危险有害因素辨识分析
（四）消防设施危险有害因素分析
（五）检维修施工过程危险有害因素分析
（六）设备装置危险有害因素分析
（七）经营过程危险有害因素辨识分析

每个子章节末尾用\"综上所述XX存在的危险因素有XX\"收尾。字数2000-3000字。""",
        "variables": {"enterprise_data": "企业完整信息JSON"},
        "description": "风险评估报告 - 第一章",
    },
    {
        "template_code": "emergency_section_ch2_summary",
        "template_name": "风险评估 - 危险有害因素辨识汇总",
        "category": "emergency_section",
        "system_prompt": "你是危险有害因素辨识汇总专家。",
        "user_prompt_template": """请根据前面已完成的危险有害因素辨识分析，输出以下两个汇总HTML表格。

企业信息：
{{enterprise_data}}

表1：危险有害因素辨识汇总表
表2：事故类型分布表

字数500-800字。""",
        "variables": {"enterprise_data": "企业完整信息JSON"},
        "description": "风险评估报告 - 第二章",
    },
    {
        "template_code": "emergency_section_ch3_risk_eval",
        "template_name": "风险评估 - 风险等级评估",
        "category": "emergency_section",
        "system_prompt": "你是风险评估专家，精通L×S风险矩阵评估法。",
        "user_prompt_template": """请根据前面已完成的风险辨识结果，进行L×S风险矩阵评估。

企业信息：
{{enterprise_data}}

输出标准HTML表格：L分级标准、S分级标准、风险等级判定表、L×S计算表、重大风险分析。
字数1500-2500字。""",
        "variables": {"enterprise_data": "企业完整信息JSON"},
        "description": "风险评估报告 - 第三章",
    },
    {
        "template_code": "emergency_section_ch4_measures",
        "template_name": "风险评估 - 现有管控措施评价",
        "category": "emergency_section",
        "system_prompt": "你是安全管理评价专家。",
        "user_prompt_template": """请根据风险源数据中记录的现有管控措施，逐项评价其有效性和充分性。

企业信息：
{{enterprise_data}}

至少覆盖所有重大和较大风险源。字数800-1200字。""",
        "variables": {"enterprise_data": "企业完整信息JSON"},
        "description": "风险评估报告 - 第四章",
    },
    {
        "template_code": "emergency_section_ch5_conclusion",
        "template_name": "风险评估 - 风险评估结论与建议",
        "category": "emergency_section",
        "system_prompt": "你是安全评估总结专家。",
        "user_prompt_template": """请基于前面的风险辨识和评估结果，撰写评估结论和管控建议。

企业信息：
{{enterprise_data}}

输出综合评估结论 + 优先整改项 / 重点加强项 / 持续改进项 / 日常管理项。
字数800-1200字。""",
        "variables": {"enterprise_data": "企业完整信息JSON"},
        "description": "风险评估报告 - 第五章",
    },
]

# ── 周边环境调查提示词 ──
SURROUNDING_PROMPTS = [
    {
        "template_code": "emergency_surrounding_system",
        "template_name": "周边环境 - 系统提示词",
        "category": "emergency_surrounding_system",
        "system_prompt": "你是一位持有国家注册安全工程师资格的专业应急预案编制专家，熟悉 GB/T 29639-2020 标准。你的任务是一次性提出关于企业周边环境的调查问题。从严、从细，覆盖 8 个方位和不同距离。严禁生成与已录入周边单位/敏感目标名称重复的数据。",
        "user_prompt_template": "",
        "variables": {},
        "description": "周边环境AI调查 - 系统角色提示词",
    },
    {
        "template_code": "emergency_surrounding_user",
        "template_name": "周边环境 - 用户提示词模板",
        "category": "emergency_surrounding_user",
        "system_prompt": "",
        "user_prompt_template": """请根据以下企业信息和已有数据，生成周边环境调查问题。

企业信息：
{{enterprise_data}}

已有数据：
{{existing_summary}}

请以 JSON 格式输出，格式严格为：
{{"questions": [{{"id": "q1", "question": "问题文本"}}]}}
每个板块至少 2 个问题。只输出 JSON，不要任何解释。""",
        "variables": {"enterprise_data": "企业完整信息", "existing_summary": "已录入周边数据摘要"},
        "description": "周边环境AI调查 - 问题生成模板",
    },
]

# ── Mermaid 提示词 ──
MERMAID_PROMPT = {
    "template_code": "emergency_mermaid_default",
    "template_name": "Mermaid 流程图 - 默认模板",
    "category": "emergency_mermaid",
    "system_prompt": "",
    "user_prompt_template": """在正文末尾输出 Mermaid flowchart 流程图，描述「{{flow_label}}」。
要求：flowchart TD 布局，包含触发条件→报告→响应→处置→恢复节点，关键决策用菱形，节点中文不超过15字。
放在 ```mermaid 代码块中。""",
    "variables": {"flow_label": "流程图名称", "section_title": "章节标题"},
    "description": "应急响应流程图生成模板",
}

# ── 全局系统提示词 ──
SYSTEM_PROMPT_TEMPLATE = {
    "template_code": "emergency_system_default",
    "template_name": "系统提示词 - 应急预案编制专家",
    "category": "emergency_system",
    "system_prompt": FALLBACK_SYSTEM_PROMPT,
    "user_prompt_template": "",
    "variables": {},
    "description": "全局系统提示词 - 用于所有章节生成的 System Prompt",
}


async def seed_prompts():
    """写入提示词模板到中台"""
    all_prompts = (
        [SYSTEM_PROMPT_TEMPLATE]
        + SECTION_PROMPTS
        + SURROUNDING_PROMPTS
        + [MERMAID_PROMPT]
    )

    for p in all_prompts:
        data = {
            "templateCode": p["template_code"],
            "templateName": p["template_name"],
            "system_prompt" if "system_prompt" in p else "systemPrompt": p.get("system_prompt", ""),
            "userPromptTemplate": p.get("user_prompt_template", ""),
            "variables": p.get("variables", {}),
            "category": p["category"],
            "description": p.get("description", ""),
        }
        # Fix key names for the API
        data_fixed = {
            "templateCode": p["template_code"],
            "templateName": p["template_name"],
            "systemPrompt": p.get("system_prompt", ""),
            "userPromptTemplate": p.get("user_prompt_template", ""),
            "variables": json.dumps(p.get("variables", {})),
            "category": p["category"],
            "description": p.get("description", ""),
        }
        result = await ywt_client.create_prompt(data_fixed)
        if result.get("code") == 200:
            print(f"  [OK] {p['template_code']}")
        else:
            print(f"  [FAIL] {p['template_code']}: {result.get('msg', result)}")


async def seed_configs():
    """写入默认系统配置到本地数据库"""
    from app.database import async_session
    from app.models.system import SysConfig
    from sqlalchemy import select

    defaults = {
        "export_dir": ("./exports", "string", "应急预案导出文件目录"),
        "prompt_cache_ttl": ("300", "int", "提示词缓存有效期（秒）"),
        "surrounding_directions": ('["N","NE","E","SE","S","SW","W","NW"]', "json", "周边环境8个方向枚举"),
        "risk_matrix_l_scale": (
            json.dumps({
                "5": "在现场没有采取防范、监测、保护、控制措施，或危害的发生不能被发现",
                "4": "危害的发生不容易被发现，现场没有检测系统",
                "3": "没有保护措施，或未严格按操作程序执行",
                "2": "危害一旦发生能及时发现，并定期进行监测",
                "1": "有充分有效的防范、控制、监测、保护措施",
            }),
            "json",
            "L量表（事故可能性）5级描述",
        ),
        "risk_matrix_s_scale": (
            json.dumps({
                "5": "多人死亡或重大财产损失",
                "4": "一人死亡或较大财产损失",
                "3": "多人重伤或一般财产损失",
                "2": "一人重伤或轻微财产损失",
                "1": "轻微伤害或无财产损失",
            }),
            "json",
            "S量表（事故严重性）5级描述",
        ),
    }

    async with async_session() as db:
        for key, (value, ctype, desc) in defaults.items():
            existing = (await db.execute(
                select(SysConfig).where(SysConfig.config_key == key)
            )).scalar_one_or_none()

            if not existing:
                cfg = SysConfig(
                    config_key=key,
                    config_value=value,
                    config_type=ctype,
                    description=desc,
                )
                db.add(cfg)
                print(f"  [NEW] {key} = {value[:50]}...")
            else:
                print(f"  [SKIP] {key} already exists")

        await db.commit()
        print("  sys_config seeding complete")


async def main():
    print("=" * 60)
    print("数据迁移：提示词 + 字典 + 系统配置 → 中台")
    print("=" * 60)

    print("\n[1/2] 写入提示词模板到中台 ai_prompt_template...")
    await seed_prompts()

    print("\n[2/2] 写入系统配置到本地 sys_config...")
    await seed_configs()

    print("\n" + "=" * 60)
    print("迁移完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
