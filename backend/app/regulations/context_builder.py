"""统一法规上下文构建器——所有生成模块的唯一法规入口。

一次 build_for_plan() 获取全量条文并缓存，
后续 get_chapter_context() 纯本地过滤+token裁剪，零网络开销。
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

TOKEN_BUDGET = 3000
CHARS_PER_TOKEN = 1.5
MAX_CONTEXT_CHARS = int(TOKEN_BUDGET * CHARS_PER_TOKEN)
BASIS_SECTION_KEYS = {"basis", "purpose", "编制依据", "调查依据", "1.1", "1.2", "1.3"}
BASIS_MAX_CHARS = int(TOKEN_BUDGET * 2 * CHARS_PER_TOKEN)


@dataclass
class RegulationRef:
    id: str
    full_name: str
    label: str
    status: str
    code: str = ""
    mandatory: bool = False
    articles: list = field(default_factory=list)


@dataclass
class ChapterContext:
    instruction: str
    regulation_count: int
    article_count: int
    truncated: bool = False


class RegulationContextBuilder:
    _instance: Optional["RegulationContextBuilder"] = None
    _cache: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def build_for_plan(self, plan_type: str, enterprise_data: dict) -> list:
        cache_key = (plan_type, enterprise_data.get("id", ""))
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            from app.regulations import get_retriever
            retriever = get_retriever()
        except Exception as e:
            logger.warning("Retriever unavailable: %s, fallback to empty", e)
            self._cache[cache_key] = []
            return []

        effective = []
        seen = set()

        try:
            plan_result = retriever.graph.query_by_plan_type(plan_type)
            core_ids = set(plan_result.get("core_ids", []))
            for reg in plan_result.get("effective", []):
                rid = reg.get("id", "")
                if rid and rid not in seen:
                    seen.add(rid)
                    articles = retriever._load_articles(reg)
                    effective.append(RegulationRef(
                        id=rid,
                        full_name=reg.get("full_name", reg.get("title", "")),
                        label=reg.get("label", ""),
                        status=reg.get("status", "current"),
                        code=reg.get("code", ""),
                        mandatory=rid in core_ids,
                        articles=articles,
                    ))
        except Exception as e:
            logger.warning("Graph query failed: %s", e)

        try:
            if retriever.vector_store and retriever.vector_store.collection_count() > 0:
                query = " ".join([
                    plan_type,
                    enterprise_data.get("industry", ""),
                    enterprise_data.get("name", ""),
                ]).strip()
                if query:
                    semantic = retriever.vector_store.search(query, top_k=8)
                    for item in semantic:
                        meta = item.get("metadata", {})
                        reg_id = meta.get("regulation_id", "")
                        if reg_id and reg_id not in seen:
                            seen.add(reg_id)
                            node = retriever.graph.get_node(reg_id)
                            if node:
                                articles = retriever._load_articles(node)
                                effective.append(RegulationRef(
                                    id=reg_id,
                                    full_name=node.get("full_name", node.get("title", "")),
                                    label=node.get("label", ""),
                                    status=node.get("status", "current"),
                                    code=node.get("code", ""),
                                    articles=articles,
                                ))
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)

        self._cache[cache_key] = {"data": effective, "_ts": time.time()}
        logger.info("Context built: plan=%s, %d regs, %d articles",
                     plan_type, len(effective), sum(len(r.articles) for r in effective))
        return effective

    def get_chapter_context(self, section_key="", section_title="",
                            plan_type="", enterprise_data=None):
        if enterprise_data is None:
            enterprise_data = {}
        try:
            from app.regulations import get_retriever
            retriever = get_retriever()
            result = retriever.retrieve_articles(
                plan_type=plan_type,
                section_key=section_key,
                section_title=section_title,
                enterprise_data=enterprise_data,
            )
        except Exception as e:
            logger.warning("Article-level retrieval failed: %s", e)
            return ""

        if not result or not result.get("articles"):
            return ""

        # V2.0: LLM reranker integration (silent fallback on failure)
        try:
            from app.regulations.llm_reranker import LLMReranker
            ai_config = enterprise_data.get("ai_config") if enterprise_data else None
            if ai_config:
                reranker = LLMReranker(ai_config)
                import asyncio
                reranked_ids = asyncio.get_event_loop().run_until_complete(
                    reranker.rerank(result["articles"], section_title or "", section_key or "", plan_type)
                )
                if reranked_ids:
                    id_map = {sa.candidate.id: sa for sa in result["articles"]}
                    result["articles"] = [id_map[rid] for rid in reranked_ids if rid in id_map]
                    result["by_regulation"] = {}
                    for sa in result["articles"]:
                        rid = sa.candidate.regulation_id
                        result["by_regulation"].setdefault(rid, []).append(sa)
        except Exception:
            pass

        is_basis = self._is_basis_section(section_key, section_title)
        max_chars = BASIS_MAX_CHARS if is_basis else MAX_CONTEXT_CHARS
        return self._format_article_context(result["by_regulation"], max_chars, is_basis)

    def _is_basis_section(self, section_key, section_title):
        combined = f"{section_key or ''} {section_title or ''}"
        return any(kw in combined for kw in BASIS_SECTION_KEYS)

    def _format_article_context(self, by_regulation: dict, max_chars: int, is_basis: bool) -> str:
            lines = []
            header_text = "【编制依据——本章必须包含以下法律法规的完整名称和文号】" if is_basis else "【法规写作纲要——本节必须覆盖以下法规要求的核心条款】"
            lines.append(header_text)
            lines.append("")
            total = 0
            truncated = False
            for reg_id, scored_articles in by_regulation.items():
                if not scored_articles:
                    continue
                sa0 = scored_articles[0]
                c0 = sa0.candidate
                header = f"### {c0.regulation_name}"
                if c0.regulation_code:
                    header += f"（{c0.regulation_code}）"
                if c0.is_abolished:
                    header += " [已废止]"
                if total + len(header) > max_chars:
                    truncated = True; break
                lines.append(header)
                total += len(header)
                for sa in scored_articles[:8]:
                    art = sa.candidate
                    art_line = f"- **{art.article_number}** {art.article_text[:200]}"
                    if total + len(art_line) > max_chars:
                        truncated = True; break
                    lines.append(art_line)
                    total += len(art_line)
                lines.append("")
                total += 1
                if truncated:
                    break
            if truncated:
                lines.append("(以下条文因篇幅限制省略)")
            lines.append("")
            lines.append("【写作要求】")
            lines.append("- 正文须体现上述法规条款的具体要求")
            lines.append("- 在行文中自然提及法规名称和具体条款号")
            lines.append("- 如某条文与本节不直接相关，可以不使用")
            return "\n".join(lines)

    def _format_context(self, regs, max_chars, is_basis):
        lines = []
        lines.append("【编制依据——本章必须包含以下法律法规的完整名称和文号】" if is_basis
                     else "【法规写作纲要——本节必须覆盖以下法规要求的要点】")
        lines.append("")
        total = 0
        truncated = False

        for reg in regs:
            header = f"### {reg.full_name}"
            if reg.code:
                header += f"（{reg.code}）"
            if reg.status == "abolished":
                header += " [已废止]"
            if total + len(header) > max_chars:
                truncated = True; break
            lines.append(header)
            total += len(header)
            for art in reg.articles:
                art_line = f"- **{art.get('number', '')}** {art.get('text', '')}"
                if total + len(art_line) > max_chars:
                    truncated = True; break
                lines.append(art_line)
                total += len(art_line)
            lines.append("")
            total += 1

        if truncated:
            lines.append("(以下条文因篇幅限制省略，请以完整法规原文为准)")
        lines.append("")
        lines.append("【写作要求】")
        lines.append("- 正文须体现上述法规条款的具体要求，不得偏离或曲解")
        lines.append("- 在行文中自然提及法规名称，但不得在章节末尾附加引用清单")
        lines.append("- 正文应读起来像完整的专业文档，不是引注论文")
        lines.append("- 如某条文与本节不直接相关，可以不使用")
        return "\n".join(lines)
