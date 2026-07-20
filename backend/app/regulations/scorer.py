"""条文相关性评分引擎 — 多维特征加权打分 + Topic 标签校验。"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ArticleCandidate:
    """一条候选条文 — 来自图谱召回或向量语义召回。"""

    id: str  # art_{reg_id}_{article_number}
    regulation_id: str
    regulation_code: str
    regulation_name: str
    article_number: str  # "第四条"
    article_text: str
    topics: list[str] = field(default_factory=list)
    vector_similarity: float = 0.0  # 余弦距离 → 相似度 (0-1)
    is_core: bool = False  # 是否该预案类型的核心法规
    is_abolished: bool = False
    reference_chain: list[str] = field(default_factory=list)  # 引用此条文的其他条文 ID


@dataclass
class ScoredArticle:
    """带评分和明细的候选条文。"""

    candidate: ArticleCandidate
    score: float
    score_breakdown: dict  # {topic_score, vector_score, mandatory_bonus, abolished_penalty, cross_ref_bonus}


class ArticleRelevanceScorer:
    """条文相关性多维评分引擎。

    评分公式:
      score = topic_score * W_TOPIC + vector_score * W_VECTOR
              + mandatory_bonus * W_MANDATORY - abolished_penalty * W_ABOLISHED
              + cross_ref_bonus * W_CROSSREF
    """

    W_TOPIC = 0.35
    W_VECTOR = 0.40
    W_MANDATORY = 0.15
    W_ABOLISHED = 0.30
    W_CROSSREF = 0.10

    def score_articles(
        self,
        candidates: list[ArticleCandidate],
        section_topics: list[str],
    ) -> list[ScoredArticle]:
        """批量打分，返回按分数降序排列的结果。"""
        scored = []
        for c in candidates:
            topic_s = self._topic_match_score(c.topics, section_topics)
            vector_s = c.vector_similarity
            mandatory_b = 1.0 if c.is_core else 0.0
            abolished_p = 1.0 if c.is_abolished else 0.0
            crossref_b = 0.2 if len(c.reference_chain) >= 2 else 0.0
            if len(c.reference_chain) >= 5:
                crossref_b = 0.5

            score = (
                topic_s * self.W_TOPIC
                + vector_s * self.W_VECTOR
                + mandatory_b * self.W_MANDATORY
                - abolished_p * self.W_ABOLISHED
                + crossref_b * self.W_CROSSREF
            )
            score = max(0.0, min(1.0, score))  # clamp

            scored.append(ScoredArticle(
                candidate=c,
                score=round(score, 4),
                score_breakdown={
                    "topic_score": round(topic_s, 4),
                    "vector_score": round(vector_s, 4),
                    "mandatory_bonus": mandatory_b,
                    "abolished_penalty": abolished_p,
                    "cross_ref_bonus": crossref_b,
                },
            ))

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored

    def _topic_match_score(
        self, article_topics: list[str], section_topics: list[str]
    ) -> float:
        """Jaccard 相似度，带同义词扩展。"""
        if not section_topics:
            return 0.3  # 无主题要求时给基准分
        if not article_topics:
            return 0.05  # 条文无 topic 时给基准分，避免全被过滤

        # 扩展同义词
        a_topics_expanded = set()
        for t in article_topics:
            a_topics_expanded.add(t)
            a_topics_expanded.update(TopicValidator.ALIASES.get(t, []))

        s_topics_expanded = set()
        for t in section_topics:
            s_topics_expanded.add(t)
            s_topics_expanded.update(TopicValidator.ALIASES.get(t, []))

        intersection = a_topics_expanded & s_topics_expanded
        union = a_topics_expanded | s_topics_expanded
        if not union:
            return 0.0
        return len(intersection) / len(union)


class TopicValidator:
    """校验 AI 解析出的 topic 标签是否在已知合法集合内。"""

    VALID_TOPICS = {
        "风险评估", "危险辨识", "危险化学品", "重大危险源", "事故分类",
        "应急管理", "应急预案", "应急预案编制", "应急演练", "应急响应",
        "应急救援", "应急救援物资", "应急资源", "应急资源调查",
        "消防安全", "灭火器", "特殊作业", "安全培训", "安全评价",
        "职业健康", "特种设备", "备案", "演练", "评估",
    }

    ALIASES = {
        "风险评估": ["安全风险评估", "安全评估", "评价"],
        "危险辨识": ["危害辨识", "危险源辨识", "危险有害因素辨识"],
        "危险化学品": ["危化品", "危险货物"],
        "应急预案编制": ["编制导则", "预案编制"],
        "应急响应": ["响应程序", "应急处置"],
        "应急救援": ["救援", "抢险"],
        "应急资源": ["应急物资", "应急装备", "物资储备"],
        "消防安全": ["消防", "防火"],
        "安全培训": ["教育培训", "安全教育"],
        "应急演练": ["疏散演练", "消防演练"],
    }

    @classmethod
    def validate_and_normalize(cls, topics: list[str]) -> dict:
        """校验 topic 列表，返回 valid / unknown / suggestions。"""
        valid = []
        unknown = []
        suggestions = {}

        for t in topics:
            t = t.strip()
            if not t:
                continue
            if t in cls.VALID_TOPICS:
                valid.append(t)
                continue
            # 查别名表
            found = False
            for canonical, aliases in cls.ALIASES.items():
                if t in aliases or t.lower() in [a.lower() for a in aliases]:
                    suggestions[t] = canonical
                    if canonical not in valid:
                        valid.append(canonical)
                    found = True
                    break
            # 模糊匹配
            if not found:
                for vt in cls.VALID_TOPICS:
                    if t in vt or vt in t:
                        suggestions[t] = vt
                        if vt not in valid:
                            valid.append(vt)
                        found = True
                        break
            if not found:
                unknown.append(t)

        return {
            "valid": sorted(set(valid)),
            "unknown": unknown,
            "suggestions": suggestions,
        }

    @classmethod
    def confidence(cls, topics: list[str]) -> float:
        """计算 topic 标签的可信度。"""
        if not topics:
            return 0.0
        result = cls.validate_and_normalize(topics)
        known_count = len(result["valid"])
        return min(1.0, known_count / len(topics))
