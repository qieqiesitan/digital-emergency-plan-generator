"""提示词缓存模块 — 从业务中台加载 Prompt 模板，提供同步/异步访问"""

import logging
import time
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# ── 缓存结构 ──
_cache: dict = {}          # {category: [templates]}
_loaded_at: float = 0      # epoch timestamp
_cache_ttl: int = 300      # 5 分钟
_loading: bool = False     # 防止并发重复加载

# ── 硬编码 fallback（中台不可用时使用） ──
FALLBACK_SYSTEM_PROMPT = """你是一位持有国家注册安全工程师资格的应急预案编制专家，具有丰富的生产经营单位应急预案编制经验。你精通 GB/T 29639-2020《生产经营单位生产安全事故应急预案编制导则》，并严格遵循以下法律法规：《中华人民共和国安全生产法》《中华人民共和国突发事件应对法》《生产安全事故应急预案管理办法》《生产安全事故应急条例》。

【写作风格——必须严格遵守】

一、公文语体要求
1. 使用正式的政府公文语体，语言严谨、客观、准确、简洁。
2. 高频动词使用：贯彻执行、组织开展、负责、协调、配合、批准、督促、检查、接受、传达、发布、落实、保障。
3. 避免口语化表达、修辞性语言、主观评论。不使用"应该""大概""也许"等不确定词汇。
4. 句式以短句为主，主语明确，逻辑清晰。
5. 开篇应引用法律法规依据。

二、结构范式
综合应急预案章节顺序：总则 → 事故风险描述 → 应急组织机构及职责 → 预警及信息报告 → 应急响应 → 信息公开 → 后期处置 → 保障措施 → 应急预案管理
专项应急预案章节顺序：事故风险分析 → 应急指挥机构及职责 → 处置程序与措施 → 应急保障
现场处置方案章节顺序：事故风险分析 → 应急工作职责 → 应急处置 → 注意事项

三、术语标准
1. 应急组织统一用："应急救援指挥部""总指挥""副总指挥""应急救援小组""抢险救援组""疏散引导组""医疗救护组""通讯联络组""后勤保障组""警戒疏散组"。
2. 响应级别统一表述为Ⅲ级/Ⅱ级/Ⅰ级响应。
3. 信息报告必须包含七要素。

请直接输出章节正文内容，不要重复章节标题。"""


async def ensure_loaded(force: bool = False) -> None:
    """确保缓存已加载（异步，幂等）。force=True 强制刷新。"""
    global _cache, _loaded_at, _loading

    if not force and _cache and (time.time() - _loaded_at) < _cache_ttl:
        return

    if _loading:
        # 等待已在进行的加载
        for _ in range(50):
            if not _loading:
                return
            await asyncio.sleep(0.1)
        return

    _loading = True
    try:
        from app import ywt_client
        # 加载所有 emergency_ 前缀的提示词
        prompts = await ywt_client.fetch_prompts(category=None)
        _cache = {}
        for p in prompts:
            cat = p.get("category", "")
            if cat:  # 加载所有有 category 的模板
                _cache.setdefault(cat, []).append(p)
        _loaded_at = time.time()
        logger.info(f"提示词缓存已加载: {sum(len(v) for v in _cache.values())} 个模板, {len(_cache)} 个分类")
    except Exception as e:
        logger.warning(f"提示词缓存加载失败（将使用fallback）: {e}")
        _cache = {}
    finally:
        _loading = False



# ── 通用报告提示词查询（非应急预案） ──

def get_report_system_prompt(category: str) -> str:
    """获取报告类系统提示词（同步）。
    
    Args:
        category: 如 'risk_assessment_system' / 'resource_investigation_system'
    
    Returns:
        systemPrompt 字符串，缓存空则返回 "" 
    """
    templates = _cache.get(category, [])
    for t in templates:
        sp = t.get("systemPrompt", "")
        if sp:
            return sp
    return ""


def get_report_section_prompt(category: str, chapter_key: str) -> Optional[dict]:
    """获取报告类章节提示词模板（同步）。
    
    templateCode 格式: {category}_{chapter_key}
    如: risk_assessment_section_ch1_hazard_id
    
    返回 {"system_prompt": str, "user_prompt_template": str} 或 None
    """
    templates = _cache.get(category, [])
    target_code = f"{category}_{chapter_key}"
    for t in templates:
        if t.get("templateCode", "") == target_code:
            return {
                "system_prompt": t.get("systemPrompt", ""),
                "user_prompt_template": t.get("userPromptTemplate", ""),
            }
    return None


def get_system_prompt(plan_type: str = "*") -> str:
    """获取系统提示词（同步，从缓存读取）。
    
    匹配优先级：
    1. emergency_system_{planType}_general -> 预案类型专属
    2. emergency_system_default -> 全局兜底
    3. FALLBACK_SYSTEM_PROMPT -> 硬编码兜底
    """
    category = "emergency_system"
    templates = _cache.get(category, [])
    # 一级：精确匹配预案类型
    target_code = f"emergency_system_{plan_type}_general"
    for t in templates:
        if t.get("templateCode", "") == target_code:
            return t.get("systemPrompt", "") or FALLBACK_SYSTEM_PROMPT
    # 二级：全局默认兜底
    for t in templates:
        if t.get("templateCode", "") == "emergency_system_default":
            return t.get("systemPrompt", "") or FALLBACK_SYSTEM_PROMPT
    # 有任意 system 模板则取第一个
    for t in templates:
        return t.get("systemPrompt", "") or FALLBACK_SYSTEM_PROMPT
    # 三级：硬编码兜底
    return FALLBACK_SYSTEM_PROMPT


def get_section_prompt(plan_type: str, section_key: str) -> Optional[dict]:
    """获取章节提示词模板（同步，从缓存读取）。
    
    匹配优先级：
    1. emergency_section_{planType}_{sectionKey}_general -> 精确匹配
    2. emergency_section_{planType}_{sectionKey}_* -> 行业变体兜底
    3. None -> 调用方使用代码 fallback
    
    返回 {"system_prompt": str, "user_prompt_template": str} 或 None。
    """
    category = "emergency_section"
    templates = _cache.get(category, [])
    # 一级：精确匹配 templateCode
    target_code = f"emergency_section_{plan_type}_{section_key}_general"
    for t in templates:
        if t.get("templateCode", "") == target_code:
            return {
                "system_prompt": t.get("systemPrompt", ""),
                "user_prompt_template": t.get("userPromptTemplate", ""),
            }
    # 二级：行业变体兜底
    prefix = f"emergency_section_{plan_type}_{section_key}_"
    for t in templates:
        if t.get("templateCode", "").startswith(prefix):
            return {
                "system_prompt": t.get("systemPrompt", ""),
                "user_prompt_template": t.get("userPromptTemplate", ""),
            }
    return None


def get_mermaid_prompt() -> Optional[str]:
    """获取 Mermaid 流程图提示词模板（同步）。"""
    templates = _cache.get("emergency_mermaid", [])
    if templates:
        return templates[0].get("user_prompt_template", "")
    return None


def render_template(template: str, variables: dict) -> str:
    """替换模板中的 {{变量名}} 为实际值。"""
    import re
    def replacer(match):
        key = match.group(1).strip()
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", replacer, template)
