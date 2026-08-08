"""提示词缓存模块 — 本地DB加载"""

import logging
import time
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# ── 缓存结构 ──
_cache: dict = {}          # {category: [templates]}
_loaded_at: float = 0      # epoch timestamp
_cache_ttl: int = 300      # 5 分钟

# ponytail: asyncio.Event instead of spin-wait + bool flag
_load_event = asyncio.Event()
_load_event.set()  # 初始无加载进行中

# ── 硬编码 fallback ──
REGULATION_WRITING_RULE = """
以下【法规写作纲要】列出了适用于本章节的参考法规条文。请根据本企业的行业类型、
实际风险特征和事故类型，逐条判断法规的适用性。仅引用与企业实际情况相关的条款，
对于明确不适用于本企业的条文（如危化品企业专用标准不适用于非危化品企业），
请直接忽略、不要写入正文。
在行文中自然提及法规名称，正文应读起来像一份完整的专业文档，不是引注论文。
"""

# ── 三段式 System Prompt 组件 ──

ROLE_BLOCK = (
    "你是一位持有国家注册安全工程师资格的应急预案编制专家，"
    "具有丰富的生产经营单位应急预案编制经验。"
    "你精通 GB/T 29639-2020《生产经营单位生产安全事故应急预案编制导则》，"
    "并严格遵循以下法律法规：《中华人民共和国安全生产法》《中华人民共和国突发事件应对法》"
    "《生产安全事故应急预案管理办法》《生产安全事故应急条例》。"
)

STYLE_BLOCK_DEFAULT = (
    "【写作风格——必须严格遵守】\n"
    "一、公文语体要求\n"
    "1. 使用正式的政府公文语体，语言严谨、客观、准确、简洁。\n"
    "2. 高频动词：贯彻执行、组织开展、负责、协调、配合、批准、督促、检查。\n"
    "3. 避免口语化表达、修辞性语言、主观评论。不使用\"应该\"\"大概\"\"也许\"等不确定词汇。\n"
    "4. 句式以短句为主，主语明确，逻辑清晰。\n"
    "5. 开篇应引用法律法规依据。\n\n"
    "二、结构范式\n"
    "综合应急预案章节顺序：总则 → 事故风险描述 → 应急组织机构及职责 → 预警及信息报告 → 应急响应 → 信息公开 → 后期处置 → 保障措施 → 应急预案管理\n"
    "专项应急预案章节顺序：事故风险分析 → 应急指挥机构及职责 → 处置程序与措施 → 应急保障\n"
    "现场处置方案章节顺序：事故风险分析 → 应急工作职责 → 应急处置 → 注意事项"
)

COMPLIANCE_BLOCK = (
    "【术语标准与结构底线——必须严格遵守】\n"
    "1. 应急组织统一使用：应急救援指挥部、总指挥、副总指挥、应急救援小组、抢险救援组、疏散引导组、医疗救护组、通讯联络组、后勤保障组、警戒疏散组。\n"
    "2. 响应级别统一表述为III级/II级/I级响应。\n"
    "3. 信息报告必须包含七要素：事故发生时间、地点、单位名称、事故类型、伤亡人数、影响范围、已采取措施。\n"
    "4. 请直接输出章节正文内容，不要重复章节标题作为正文第一行。\n"
    "5. 【数据真实性护栏——必须严格遵守】\n"
    "   5.1 企业档案中以\"（待补充）\"标注的信息一律视为缺失，禁止推断、禁止编造。\n"
    "   5.2 严禁编造地址、法定代表人、联系电话、统一社会信用代码、注册资本等企业基本信息。\n"
    "   5.3 正文涉及缺失信息时，直接书写\"（待补充）\"，不得用其他文字替代。\n"
    "   5.4 全部正文内容必须以企业档案数据为唯一事实来源，不得引入档案之外的企业信息。"
)

# ── 风格参数翻译表 ──

STYLE_PARAM_MAP: dict[str, dict[str, str]] = {
    "formality": {
        "formal": (
            "使用正式的政府公文语体，语言严谨、客观、准确、简洁。"
            "高频动词：贯彻执行、组织开展、负责、协调、配合、批准、督促、检查。"
            "禁止使用\"应该\"\"大概\"\"也许\"等不确定词汇。"
        ),
        "standard": (
            "使用规范的公文语体，语言严谨、客观、准确。"
            "以陈述句为主，避免主观评论和口语化表达。"
        ),
        "practical": (
            "使用实用简洁的工程文体，直接陈述事实和措施。"
            "避免冗余修饰和套话，以动词开头的短句为主。"
            "可以使用条目式、清单式表达。"
        ),
    },
    "detail_level": {
        "concise": "正文力求简洁，每个要点控制在2-3句话以内，只写关键信息。",
        "balanced": "正文详略得当，关键内容充分展开，非关键内容点到为止。",
        "comprehensive": "正文详尽展开，每个要点充分论述，提供具体说明和示例。",
    },
    "table_preference": {
        "minimal": "尽量不用表格，用文字段落描述数据关系。",
        "moderate": "在适合的场景使用表格呈现结构化数据，但不过度依赖。",
        "heavy": "优先使用表格呈现数据和流程，通过表格组织对照关系和清单。",
    },
    "diagram_preference": {
        "none": "不生成Mermaid流程图，用文字描述流程即可。",
        "mermaid": "在描述流程的章节末尾插入mermaid流程图，用图形辅助理解。",
    },
}




def generate_style_instruction(style_preference: dict | None) -> str:
    """将风格参数翻译为自然语言注入指令。None/空 → 标准默认风格。"""
    if not style_preference:
        return "【写作风格——请严格遵循】\n" + STYLE_BLOCK_DEFAULT

    lines = ["【风格偏好——请严格遵循以下写作风格】"]

    for param, value in style_preference.items():
        if param in ("mode",):
            continue
        text = STYLE_PARAM_MAP.get(param, {}).get(value, "")
        if text:
            lines.append(f"- {text}")

    if len(lines) > 1:
        return "\n".join(lines)
    return "【写作风格——请严格遵循】\n" + STYLE_BLOCK_DEFAULT


def build_system_prompt_with_style(
    plan_type: str = "*",
    style_preference: dict | None = None,
    advanced_overrides: dict | None = None,
) -> str:
    """构建三段式 System Prompt，支持风格参数注入。

    Args:
        plan_type: 预案类型（保留，未来可按预案类型区分风格）
        style_preference: {"formality":"standard","detail_level":"balanced",...}
        advanced_overrides: {"system_prompt_override":"...","section_overrides":{...}}

    Returns:
        完整的 system prompt 字符串
    """
    # 高级模式：用户全文覆盖（跳过三段式组装）
    if advanced_overrides and advanced_overrides.get("system_prompt_override"):
        return advanced_overrides["system_prompt_override"]

    parts = [ROLE_BLOCK, generate_style_instruction(style_preference), COMPLIANCE_BLOCK]
    return "\n\n".join(parts)

async def ensure_loaded(force: bool = False) -> None:
    """确保缓存已加载。force=True强制刷新。"""
    global _cache, _loaded_at

    if not force and _cache and (time.time() - _loaded_at) < _cache_ttl:
        return

    if not _load_event.is_set():
        await _load_event.wait()
        if not force and _cache:
            return

    _load_event.clear()
    try:
        await _load_from_local_db()
        logger.info(f"提示词缓存已加载(本地DB): {sum(len(v) for v in _cache.values())} 个模板, {len(_cache)} 个分类")
    finally:
        _load_event.set()


async def _load_from_local_db() -> None:
    """从本地DB加载提示词到内存缓存"""
    global _cache, _loaded_at
    try:
        from app.database import async_session
        from app.models.prompt import PromptTemplate
        from sqlalchemy import select
        async with async_session() as db:
            rows = (await db.execute(
                select(PromptTemplate).where(PromptTemplate.status.in_(["active", "0"]))
            )).scalars().all()
            _cache = {}
            for row in rows:
                cat = row.category or ""
                if cat:
                    _cache.setdefault(cat, []).append({
                        "id": row.id,
                        "template_code": row.template_code,
                        "template_name": row.template_name,
                        "category": row.category,
                        "system_prompt": row.system_prompt or "",
                        "user_prompt_template": row.user_prompt_template or "",
                    })
            _loaded_at = time.time()
    except Exception as e:
        logger.error(f"本地DB提示词加载失败: {e}")
        _cache = {}


def invalidate_cache():
    """强制下次访问时刷新缓存（本地CRUD操作后调用）"""
    global _loaded_at
    _loaded_at = 0


# ── 通用报告提示词查询（非应急预案） ──

def get_report_system_prompt(category: str) -> str:
    templates = _cache.get(category, [])
    for t in templates:
        sp = t.get("system_prompt", "")
        if sp:
            return sp
    return ""


def get_report_section_prompt(category: str, chapter_key: str) -> Optional[dict]:
    templates = _cache.get(category, [])
    target_code = f"{category}_{chapter_key}"
    for t in templates:
        if t.get("template_code", "") == target_code:
            return {
                "system_prompt": t.get("system_prompt", ""),
                "user_prompt_template": t.get("user_prompt_template", ""),
            }
    return None


def get_system_prompt(plan_type: str = "*") -> str:
    category = "emergency_system"
    templates = _cache.get(category, [])
    target_code = f"emergency_system_{plan_type}_general"
    for t in templates:
        if t.get("template_code", "") == target_code:
            return t.get("system_prompt", "") or build_system_prompt_with_style(plan_type)
    for t in templates:
        if t.get("template_code", "") == "emergency_system_default":
            return t.get("system_prompt", "") or build_system_prompt_with_style(plan_type)
    for t in templates:
        return t.get("system_prompt", "") or build_system_prompt_with_style(plan_type)

    # 数据库无模板时使用三段式默认（无风格参数 = 标准风格）
    return build_system_prompt_with_style(plan_type)


def get_section_prompt(plan_type: str, section_key: str) -> Optional[dict]:
    category = "emergency_section"
    templates = _cache.get(category, [])
    target_code = f"emergency_section_{plan_type}_{section_key}_general"
    for t in templates:
        if t.get("template_code", "") == target_code:
            return {
                "system_prompt": t.get("system_prompt", ""),
                "user_prompt_template": t.get("user_prompt_template", ""),
            }
    prefix = f"emergency_section_{plan_type}_{section_key}_"
    for t in templates:
        if t.get("template_code", "").startswith(prefix):
            return {
                "system_prompt": t.get("system_prompt", ""),
                "user_prompt_template": t.get("user_prompt_template", ""),
            }
    return None


def get_mermaid_prompt() -> Optional[str]:
    templates = _cache.get("emergency_mermaid", [])
    if templates:
        return templates[0].get("user_prompt_template", "")
    return None


def get_diagram_prompt(diagram_type: str) -> Optional[str]:
    """Query emergency_diagram category for a diagram-type-specific prompt template.
    Falls back through: exact type match → base type match → emergency_mermaid default."""
    # Exact match (e.g. "flowchart TD", "graph LR", "sequenceDiagram")
    templates = _cache.get("emergency_diagram", [])
    exact_code = f"emergency_diagram_{diagram_type}"
    for t in templates:
        if t.get("template_code", "") == exact_code:
            return t.get("user_prompt_template", "") or None
    # Base type match (e.g. "flowchart", "graph", "pie")
    base_type = diagram_type.split()[0]
    base_code = f"emergency_diagram_{base_type}"
    for t in templates:
        if t.get("template_code", "") == base_code:
            return t.get("user_prompt_template", "") or None
    # Fallback to emergency_mermaid (backward compat)
    return get_mermaid_prompt()


def render_template(template: str, variables: dict) -> str:
    """替换模板中的 {{变量名}} 为实际值。"""
    import re
    def replacer(match):
        key = match.group(1).strip()
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", replacer, template)
