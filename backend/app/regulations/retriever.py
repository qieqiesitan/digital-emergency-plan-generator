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

    def __init__(self, graph, vector_store, bm25_index=None):
        self.graph = graph
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        from app.regulations.scorer import ArticleRelevanceScorer
        self.scorer = ArticleRelevanceScorer()

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
            articles = self._load_articles(reg)
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
                articles = self._load_articles(reg)
                if articles:
                    reg_copy = dict(reg)
                    reg_copy["articles"] = articles[:max_articles]
                    effective.append(reg_copy)

        return {"effective": effective, "abolished": [], "matched_topics": topics}

    # ── Article-level hybrid retrieval (V1.0 main path) ──

    def retrieve_articles(
        self, plan_type, section_key="", section_title="",
        enterprise_data=None, max_articles=15,
    ):
        section_topics = _match_section_topics(section_key, section_title)
        graph_c = self._graph_article_recall(plan_type, section_topics)
        vector_c = self._vector_article_recall(
            plan_type, section_key, section_title, section_topics, enterprise_data,
        )
        all_c = self._merge_dedup(graph_c, vector_c)
        scored = self.scorer.score_articles(all_c, section_topics)
        scored.sort(key=lambda s: s.score, reverse=True)
        top = scored[:max_articles]
        by_reg = {}
        for sa in top:
            rid = sa.candidate.regulation_id
            by_reg.setdefault(rid, []).append(sa)
        return {"articles": top, "by_regulation": by_reg,
                "debug": {"graph_count": len(graph_c), "vector_count": len(vector_c),
                           "merged_count": len(all_c)}}

    def _graph_article_recall(self, plan_type, section_topics):
        from app.regulations.scorer import ArticleCandidate
        plan_regs = self.graph.query_by_plan_type(plan_type)
        candidates = []
        for reg in plan_regs.get("effective", []):
            rid = reg.get("id", "")
            arts = self.graph.get_articles_by_regulation(rid)
            if not arts:
                for art in self._load_articles(reg):
                    num = art.get("number", "")
                    art_text = art.get("text", "")
                    # V2.0: topic keyword filter in fallback
                    if section_topics:
                        if not any(st in art_text or st in num for st in section_topics):
                            continue
                    safe = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "_", num)
                    candidates.append(ArticleCandidate(
                        id=f"art_{rid}_{safe}", regulation_id=rid,
                        regulation_code=reg.get("code",""),
                        regulation_name=reg.get("full_name", reg.get("label","")),
                        article_number=num, article_text=art_text,
                        topics=reg.get("topics",[]), vector_similarity=0.0,
                        is_core=reg.get("is_core",False),
                        is_abolished=reg.get("status")=="abolished"))
                continue
            for art in arts:
                a_topics = art.get("topics", [])
                if isinstance(a_topics, str):
                    a_topics = [t.strip() for t in a_topics.split(",")]
                if section_topics and a_topics and not any(
                    t.lower() in [tt.lower() for tt in a_topics] for t in section_topics
                ):
                    continue
                candidates.append(ArticleCandidate(
                    id=art.get("id",""), regulation_id=rid,
                    regulation_code=reg.get("code",""),
                    regulation_name=reg.get("full_name", reg.get("label","")),
                    article_number=art.get("article_number", art.get("label","")),
                    article_text=art.get("article_text",""),
                    topics=a_topics, vector_similarity=0.0,
                    is_core=reg.get("is_core",False),
                    is_abolished=reg.get("status")=="abolished"))
        return candidates

    def _vector_article_recall(self, plan_type, section_key, section_title, section_topics, enterprise_data):
        if not self.vector_store or self.vector_store.collection_count() < 3:
            return []
        from app.regulations.scorer import ArticleCandidate
        queries = self._build_semantic_queries(
            enterprise_data or {}, plan_type, section_title or section_key or "")
        all_r = {}
        for q in queries:
            try:
                for item in self.vector_store.search_articles(q, top_k=12):
                    k = item["metadata"].get("regulation_id","") + "_" + item["metadata"].get("article_number","")
                    if k not in all_r or item.get("distance",1) < all_r[k].get("distance",1):
                        all_r[k] = item
            except Exception:
                pass
        candidates = []
        for k, item in all_r.items():
            meta = item.get("metadata",{})
            rid = meta.get("regulation_id","")
            rn = self.graph.get_node(rid) or {}
            if not rn: continue
            d = item.get("distance",1)
            sim = 1.0/(1.0+float(d)) if d is not None else 0.5
            candidates.append(ArticleCandidate(
                id=f"art_{rid}_{meta.get('article_number','?')}", regulation_id=rid,
                regulation_code=rn.get("code",""),
                regulation_name=rn.get("full_name", rn.get("label","")),
                article_number=meta.get("article_number",""),
                article_text=item.get("text",""), topics=rn.get("topics",[]),
                vector_similarity=sim, is_core=rn.get("is_core",False),
                is_abolished=rn.get("status")=="abolished"))
        return candidates

    def _merge_dedup(self, graph_c, vector_c):
        m = {}
        for c in graph_c:
            m[self._normalize_id(c.id)] = c
        for c in vector_c:
            k = self._normalize_id(c.id)
            if k in m:
                m[k].vector_similarity = max(m[k].vector_similarity, c.vector_similarity)
            else:
                m[k] = c
        return list(m.values())

    def _normalize_id(self, aid):
        return re.sub(r'[\s_\-]', '', aid).lower()


    def _build_semantic_queries(self, enterprise_data, plan_type, section_text):
        """构造多条语义查询，每条聚焦不同信号维度。"""
        type_labels = {
            "comprehensive": "综合应急预案", "special": "专项应急预案",
            "onsite": "现场处置方案", "risk_assessment": "风险评估报告",
            "resource_investigation": "应急资源调查报告",
        }
        plan_label = type_labels.get(plan_type, plan_type)
        queries = [f"{plan_label} 编制要求 {section_text}"]
        industry = (enterprise_data or {}).get("industry", "")
        if industry:
            queries.append(f"{industry} {section_text} 规范要求")
        risk_sources = (enterprise_data or {}).get("risk_sources", [])
        if isinstance(risk_sources, list):
            risk_names = [rs.get("name", "") if isinstance(rs, dict) else str(rs) for rs in risk_sources[:3]]
            if risk_names:
                queries.append(f"{' '.join(risk_names)} {section_text} 法规条款")
        chemicals = (enterprise_data or {}).get("hazardous_chemicals", [])
        if isinstance(chemicals, list):
            chem_names = [c.get("name", "") if isinstance(c, dict) else str(c) for c in chemicals[:3]]
            if chem_names:
                queries.append(f"{' '.join(chem_names)} 安全管理 {section_text} 条款")
        name = (enterprise_data or {}).get("name", "")
        if name:
            queries.append(f"{name} {section_text}")
        return list(set(q.strip() for q in queries if q.strip()))


    # 文件索引缓存
    _file_index = None

    def _build_file_index(self) -> dict:
        if self._file_index is not None:
            return self._file_index
        idx = {}
        if not os.path.isdir(TEXTS_DIR):
            self._file_index = idx
            return idx
        for fn in os.listdir(TEXTS_DIR):
            if not fn.endswith(".md"):
                continue
            fpath = os.path.join(TEXTS_DIR, fn)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    first = f.readline().lstrip("#").strip()
                idx[fn] = first
            except Exception:
                idx[fn] = ""
        self._file_index = idx
        return idx

    def _load_articles(self, reg: dict) -> list[dict]:
        """从 texts/*.md 读取法规条文。通过法规元数据智能匹配文件。"""
        rid = reg.get("id", "")
        fname = f"{rid}.md"
        fpath = os.path.join(TEXTS_DIR, fname)

        if not os.path.exists(fpath):
            # 策略1: 用 label/full_name/title 匹配文件标题
            idx = self._build_file_index()
            label = (reg.get("label") or "").lower()
            full_name = (reg.get("full_name") or reg.get("title") or "").lower()
            best = None
            for fn, title in idx.items():
                fn_lower = fn.lower()
                if label and label in fn_lower:
                    best = fn; break
                if label and label in title.lower():
                    best = fn; break
                if full_name and any(kw in fn_lower for kw in full_name.split("《")[0].split() if len(kw) > 2):
                    best = fn; break
                if full_name and full_name[:8] in title.lower():
                    best = fn; break
            if best:
                fpath = os.path.join(TEXTS_DIR, best)
            elif idx:
                # 策略2: 尝试所有文件
                for fn in idx:
                    test_path = os.path.join(TEXTS_DIR, fn)
                    if os.path.exists(test_path):
                        fpath = test_path
                        break

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

    
    def _bm25_article_recall(self, query_text: str, top_k: int = 5) -> list:
        """BM25 精确匹配召回。作为检索第 0 级，高分命中直接进入输出。"""
        if not self.bm25_index:
            return []
        from app.regulations.scorer import ArticleCandidate
        results = self.bm25_index.search(query_text, top_k=top_k)
        candidates = []
        for item in results:
            meta = item["meta"]
            candidates.append(ArticleCandidate(
                id=item["id"],
                regulation_id=meta["regulation_id"],
                regulation_code=meta.get("regulation_code", ""),
                regulation_name=meta.get("regulation_name", ""),
                article_number=meta.get("article_number", ""),
                article_text=item["text"],
                topics=[],
                vector_similarity=0.0,
                is_core=False,
                is_abolished=False,
            ))
        return candidates

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