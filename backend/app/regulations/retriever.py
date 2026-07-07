"""混合检索编排 — 图谱精确匹配 + 向量语义补充。"""

import logging
import os

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TEXTS_DIR = os.path.join(DATA_DIR, "texts")


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
        # 第1级：图谱匹配
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
        if self.vector_store.collection_count() >= 30 and enterprise_data:
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

    def _load_articles(self, regulation_id: str) -> list[dict]:
        """从 texts/*.md 读取法规条文。"""
        import re
        fname = f"{regulation_id}.md"
        fpath = os.path.join(TEXTS_DIR, fname)
        if not os.path.exists(fpath):
            # 尝试模糊匹配
            for fn in os.listdir(TEXTS_DIR) if os.path.isdir(TEXTS_DIR) else []:
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
            if text and len(text) > 10:  # 跳过过短的无意义块
                articles.append({"number": title, "text": text})
        return articles

    def _build_semantic_query(self, enterprise_data: dict, plan_type: str) -> str:
        """从企业数据构建语义检索查询。"""
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
