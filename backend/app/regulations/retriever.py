"""混合检索编排 ― 图谱精确匹配 + 按主题检索 + 向量语义补充。"""

import logging
import os
import re

import yaml

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TEXTS_DIR = os.path.join(DATA_DIR, "texts")
SECTION_TOPICS_PATH = os.path.join(DATA_DIR, "section_topics.yaml")

# 缓存 section_topics 配置
_section_topics_cache = None


def _load_section_topics():
    global _section_topics_cache
    if _section_topics_cache is not None:
        return _section_topics_cache
    if not os.path.exists(SECTION_TOPICS_PATH):
        _section_topics_cache = {"patterns": []}
        return _section_topics_cache
    with open(SECTION_TOPICS_PATH, "r", encoding="utf-8") as f:
        _section_topics_cache = yaml.safe_load(f) or {"patterns": []}
    return _section_topics_cache


def _match_section_topics(section_key: str, section_title: str) -> list[str]:
    """根据 section_key/title 匹配对应的 topic 列表。返回空列表表示不注入。"""
    config = _load_section_topics()
    combined = f"{section_key or ''} {section_title or ''}"
    for pattern in config.get("patterns", []):
        key_re = pattern.get("key", "")
        if key_re and re.search(key_re, combined):
            if pattern.get("inject") is False:
                return []  # 编制依据类走原逻辑
            return pattern.get("topics", [])
    return []


class RegulationRetriever:
    """编排图谱 + 向量的两级混合检索。"""

    def __init__(self, graph, vector_store):
        self.graph = graph
        self.vector_store = vector_store

    def retrieve(self, plan_type: str, section_key: str = "",
                 enterprise_data: dict = None,
                 max_articles: int = 30) -> dict:
        """
        两级混合检索。

        第1级：图谱精确匹配 plan_type → 获取法规列表 → 读条文原文
        第2级：向量语义补充（法规量 >= 30 时启用）
        """
        plan_result = self.graph.query_by_plan_type(plan_type)

        effective = []
        for reg in plan_result.get("effective", []):
            articles = self._load_articles(reg["id"])
            if articles:
                article_count = 0
                trimmed = []
                for art in articles:
                    if article_count >= max_articles:
                        break
                    trimmed.append(art)
                    article_count += 1
                reg_copy = dict(reg)
                reg_copy["articles"] = trimmed
                effective.append(reg_copy)

        abolished = plan_result.get("abolished", [])

        # 第2级：向量语义补充
        if self.vector_store and self.vector_store.collection_count() >= 30 and enterprise_data:
            query_text = self._build_semantic_query(enterprise_data, plan_type)
            existing_ids = {r["id"] for r in effective}
            semantic = self.vector_store.search(query_text, top_k=5)
            for item in semantic:
                reg_id = item["metadata"].get("regulation_id", "")
                if reg_id and reg_id not in existing_ids:
                    reg_node = self.graph.get_node(reg_id)
                    if reg_node:
                        reg_node["articles"] = [{
                            "number": item["metadata"].get("article", ""),
                            "text": item["text"],
                        }]
                        effective.append(reg_node)
                        existing_ids.add(reg_id)

        return {"effective": effective, "abolished": abolished}

    def retrieve_by_topics(self, section_key: str, section_title: str,
                           plan_type: str = "",
                           max_articles: int = 20) -> dict:
        """
        按章节主题检索法规。供非编制依据章节使用。

        流程：section_key → 匹配 section_topics.yaml → 获取 topic 列表
             → 图谱查询 topic 匹配的法规 → 加载条文原文。
        """
        topics = _match_section_topics(section_key, section_title)
        if not topics:
            return {"effective": [], "abolished": []}

        effective = []
        seen = set()

        for topic in topics:
            regs = self.graph.query_by_topic(topic, limit=8)
            for reg in regs:
                rid = reg["id"]
                if rid in seen:
                    continue
                seen.add(rid)
                # 跳过已废止
                if reg.get("status") == "abolished":
                    continue
                articles = self._load_articles(rid)
                if articles:
                    reg_copy = dict(reg)
                    reg_copy["articles"] = articles[:max_articles]
                    effective.append(reg_copy)

        return {"effective": effective, "abolished": [], "matched_topics": topics}

    def _load_articles(self, regulation_id: str) -> list[dict]:
        """从 texts/*.md 读取法规条文。"""
        fname = f"{regulation_id}.md"
        fpath = os.path.join(TEXTS_DIR, fname)
        if not os.path.exists(fpath):
            if not os.path.isdir(TEXTS_DIR):
                return []
            for fn in os.listdir(TEXTS_DIR):
                if fn.startswith(regulation_id) or regulation_id in fn:
                    fpath = os.path.join(TEXTS_DIR, fn)
                    break
            else:
                return []

        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        articles = []
        blocks = re.split(r"\n(?=##\s)", content)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            title = lines[0].lstrip("#").strip() if lines else ""
            text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            if text and len(text) > 10:
                articles.append({"number": title, "text": text})
        return articles

    def _build_semantic_query(self, enterprise_data: dict, plan_type: str) -> str:
        parts = []
        type_labels = {
            "comprehensive": "综合应急预案",
            "special": "专项应急预案",
            "onsite": "现场处置方案",
            "risk_assessment": "风险评估报告",
            "resource_investigation": "应急资源调查报告",
        }
        parts.append(type_labels.get(plan_type, plan_type))
        parts.append("编制依据")

        if enterprise_data:
            industry = enterprise_data.get("industry", "")
            if industry:
                parts.append(industry)
            name = enterprise_data.get("name", "")
            if name:
                parts.append(name)

        return " ".join(parts)