"""条文间交叉引用检测 - 从条文文本提取引用关系，建立图谱边。"""

import logging
import re

logger = logging.getLogger(__name__)

# 法规引用模式（中文法律文书常见表达）
REFERENCE_PATTERNS = [
    # "依据《安全生产法》第二十一条"
    r"(?:依据|按照|参照|参见|执行|适用|符合)"
    r"[《〈]?(?P<law_name>[^》〉]*?)[》〉]?"
    r"\s*(?:第\s*(?P<article_num>[一二三四五六七八九十百\d]+)\s*条)?",
    # "符合GB/T 29639-2020第4.2条"
    r"(?:符合|满足|执行)"
    r"(?P<law_name2>GB[/T]?\s*\d+[.\d]*-?\d*)"
    r"\s*(?:第\s*(?P<article_num2>[\d.]+)\s*[条节])?",
    # "见《危险化学品安全管理条例》"
    r"[见參](?:照)?[《〈](?P<law_name3>[^》〉]+)[》〉]",
]


class CrossReferenceDetector:
    """检测条文中的交叉引用关系。"""

    def detect_references(self, article_text: str) -> list[dict]:
        """从条文文本中提取引用的其他法规/条文。返回: [{law_name, article_num, confidence}]。"""
        refs = []
        for pattern in REFERENCE_PATTERNS:
            for m in re.finditer(pattern, article_text):
                law_name = (
                    m.group("law_name")
                    or m.group("law_name2")
                    or m.group("law_name3")
                )
                article_num = (
                    m.group("article_num")
                    or m.group("article_num2")
                )
                if not law_name:
                    continue
                law_name = law_name.strip()
                if len(law_name) < 2:
                    continue
                confidence = 0.7
                if article_num:
                    confidence = 0.85

                # 去重
                existing = [r for r in refs if r["law_name"] == law_name]
                if not existing:
                    refs.append({
                        "law_name": law_name,
                        "article_num": article_num.strip() if article_num else None,
                        "confidence": confidence,
                    })
                elif article_num and not existing[0].get("article_num"):
                    existing[0]["article_num"] = article_num.strip()
                    existing[0]["confidence"] = confidence
        return refs

    def resolve_references(
        self, references: list[dict], all_regulations: list[dict]
    ) -> list[dict]:
        """将引用的法规名称解析为具体的 regulation_id 和 article_id。"""
        resolved = []
        for ref in references:
            best_match = None
            best_score = 0
            law_name = ref["law_name"]

            for reg in all_regulations:
                reg_name = reg.get("full_name", reg.get("label", ""))
                reg_code = reg.get("code", "")

                # 精确匹配编号
                if law_name == reg_code:
                    best_match = reg
                    best_score = 1.0
                    break

                # 名称包含匹配
                if law_name in reg_name or reg_name in law_name:
                    score = len(law_name) / max(len(reg_name), 1)
                    if score > best_score:
                        best_score = score
                        best_match = reg

                # 关键词匹配
                if best_score < 0.3:
                    keywords = law_name.replace("《", "").replace("》", "").split()
                    hits = sum(1 for kw in keywords if kw in reg_name)
                    score = hits / max(len(keywords), 1)
                    if score > best_score:
                        best_score = score
                        best_match = reg

            if best_match and best_score >= 0.4:
                article_id = None
                if ref.get("article_num") and best_match.get("id"):
                    article_id = f"art_{best_match['id']}_{ref['article_num']}"

                resolved.append({
                    "law_name": law_name,
                    "article_num": ref.get("article_num"),
                    "regulation_id": best_match.get("id"),
                    "regulation_name": best_match.get("full_name", best_match.get("label", "")),
                    "article_id": article_id,
                    "confidence": min(1.0, ref["confidence"] * best_score),
                })

        return resolved

    def build_reference_graph(
        self, article_id: str, resolved_refs: list[dict]
    ) -> int:
        """在图中建立 article->article 的引用边。返回添加的边数。"""
        from app.regulations import get_graph
        graph = get_graph()
        count = 0

        for ref in resolved_refs:
            target_id = ref.get("article_id")
            if not target_id:
                # 只有 regulation 级匹配，连到 regulation 节点
                target_id = ref.get("regulation_id")
            if not target_id or target_id not in graph._g:
                continue

            # 避免自引用
            if target_id == article_id:
                continue

            # 检查是否已存在
            existing = False
            for _, t, d in graph._g.out_edges(article_id, data=True):
                if t == target_id and d.get("relation") == "引用":
                    existing = True
                    break
            if not existing:
                graph.add_edge(article_id, target_id, relation="引用")
                count += 1

        return count
