"""提示词缓存模块 — YWT优先，本地DB兜底，双模运行"""

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
    """确保缓存已加载。YWT优先→本地DB兜底。force=True强制刷新。"""
    global _cache, _loaded_at

    if not force and _cache and (time.time() - _loaded_at) < _cache_ttl:
        return

    if not _load_event.is_set():
        await _load_event.wait()
        if not force and _cache:
            return

    _load_event.clear()
    try:
        ywt_success = False
        try:
            from app import ywt_client
            prompts = await ywt_client.fetch_prompts(category=None)
            if prompts:
                _cache = {}
                for p in prompts:
                    cat = p.get("category", "")
                    if cat:
                        _cache.setdefault(cat, []).append(p)
                _loaded_at = time.time()
                logger.info(f"提示词缓存已加载(YWT): {sum(len(v) for v in _cache.values())} 个模板, {len(_cache)} 个分类")
                ywt_success = True
                await _sync_ywt_to_local(prompts)
        except Exception as e:
            logger.warning(f"YWT提示词加载失败，回退本地DB: {e}")

        if not ywt_success:
            await _load_from_local_db()
            logger.info(f"提示词缓存已加载(本地DB): {sum(len(v) for v in _cache.values())} 个模板, {len(_cache)} 个分类")
        else:
            # YWT成功但本地修改优先：合并本地DB数据覆盖YWT缓存
            await _merge_local_overrides()
    finally:
        _load_event.set()


async def _sync_ywt_to_local(prompts: list[dict]) -> None:
    """将YWT提示词同步到本地DB（upsert by template_code）"""
    try:
        from app.database import async_session
        from app.models.prompt import PromptTemplate
        from sqlalchemy import select
        async with async_session() as db:
            for p in prompts:
                code = p.get("templateCode", "") or p.get("template_code", "")
                if not code:
                    continue
                existing = (await db.execute(
                    select(PromptTemplate).where(PromptTemplate.template_code == code)
                )).scalar_one_or_none()
                if existing:
                    # 本地已有模板，只更新名称和状态，不覆盖内容（保护本地修改）
                    existing.template_name = p.get("templateName", "") or p.get("template_name", existing.template_name)
                    existing.status = p.get("status", existing.status or "active")
                else:
                    db.add(PromptTemplate(
                        template_code=code,
                        template_name=p.get("templateName", "") or p.get("template_name", code),
                        category=p.get("category", ""),
                        system_prompt=p.get("systemPrompt", "") or p.get("system_prompt", ""),
                        user_prompt_template=p.get("userPromptTemplate", "") or p.get("user_prompt_template", ""),
                    ))
            await db.commit()
            logger.info(f"YWT→本地DB同步: {len(prompts)} 条")
    except Exception as e:
        logger.warning(f"YWT→本地DB同步失败: {e}")


async def _merge_local_overrides() -> None:
    """YWT加载后，用本地DB中已存在的模板覆盖缓存（保护本地修改）。"""
    try:
        from app.database import async_session
        from app.models.prompt import PromptTemplate
        from sqlalchemy import select
        async with async_session() as db:
            rows = (await db.execute(
                select(PromptTemplate).where(PromptTemplate.status.in_(["active", "0"]))
            )).scalars().all()
            for row in rows:
                cat = row.category or ""
                if not cat:
                    continue
                local_item = {
                    "id": row.id,
                    "templateCode": row.template_code,
                    "template_code": row.template_code,
                    "templateName": row.template_name,
                    "template_name": row.template_name,
                    "category": row.category,
                    "systemPrompt": row.system_prompt or "",
                    "system_prompt": row.system_prompt or "",
                    "userPromptTemplate": row.user_prompt_template or "",
                    "user_prompt_template": row.user_prompt_template or "",
                }
                # Override YWT cache entry with local version
                cat_templates = _cache.setdefault(cat, [])
                replaced = False
                for i, t in enumerate(cat_templates):
                    if t.get("templateCode", "") == row.template_code:
                        cat_templates[i] = local_item
                        replaced = True
                        break
                if not replaced:
                    cat_templates.append(local_item)
    except Exception as e:
        logger.warning(f"本地修改合并失败: {e}")

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
                        "templateCode": row.template_code,
                        "template_code": row.template_code,
                        "templateName": row.template_name,
                        "template_name": row.template_name,
                        "category": row.category,
                        "systemPrompt": row.system_prompt or "",
                        "system_prompt": row.system_prompt or "",
                        "userPromptTemplate": row.user_prompt_template or "",
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
        sp = t.get("systemPrompt", "")
        if sp:
            return sp
    return ""


def get_report_section_prompt(category: str, chapter_key: str) -> Optional[dict]:
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
    category = "emergency_system"
    templates = _cache.get(category, [])
    target_code = f"emergency_system_{plan_type}_general"
    for t in templates:
        if t.get("templateCode", "") == target_code:
            return t.get("systemPrompt", "") or FALLBACK_SYSTEM_PROMPT
    for t in templates:
        if t.get("templateCode", "") == "emergency_system_default":
            return t.get("systemPrompt", "") or FALLBACK_SYSTEM_PROMPT
    for t in templates:
        return t.get("systemPrompt", "") or FALLBACK_SYSTEM_PROMPT
    return FALLBACK_SYSTEM_PROMPT


def get_section_prompt(plan_type: str, section_key: str) -> Optional[dict]:
    category = "emergency_section"
    templates = _cache.get(category, [])
    target_code = f"emergency_section_{plan_type}_{section_key}_general"
    for t in templates:
        if t.get("templateCode", "") == target_code:
            return {
                "system_prompt": t.get("systemPrompt", ""),
                "user_prompt_template": t.get("userPromptTemplate", ""),
            }
    prefix = f"emergency_section_{plan_type}_{section_key}_"
    for t in templates:
        if t.get("templateCode", "").startswith(prefix):
            return {
                "system_prompt": t.get("systemPrompt", ""),
                "user_prompt_template": t.get("userPromptTemplate", ""),
            }
    return None


def get_mermaid_prompt() -> Optional[str]:
    templates = _cache.get("emergency_mermaid", [])
    if templates:
        return templates[0].get("user_prompt_template", "") or templates[0].get("userPromptTemplate", "")
    return None


def render_template(template: str, variables: dict) -> str:
    """替换模板中的 {{变量名}} 为实际值。"""
    import re
    def replacer(match):
        key = match.group(1).strip()
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", replacer, template)
