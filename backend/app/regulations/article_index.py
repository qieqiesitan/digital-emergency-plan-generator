"""法规自动归类 - 入库后动态判定预案类型归属，替代纯手动维护 index.yaml。"""

import logging
import os

import yaml

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
INDEX_PATH = os.path.join(DATA_DIR, "index.yaml")

PLAN_TYPE_RULES = {
    "comprehensive": {
        "required_topics": ["应急预案", "应急预案编制"],
        "keyword_rules": ["综合应急预案", "应急预案编制导则"],
        "auto_include": True,
    },
    "risk_assessment": {
        "required_topics": ["风险评估", "危险辨识", "危险化学品", "重大危险源"],
        "keyword_rules": ["风险评估", "安全评价", "风险辨识", "危险化学品"],
        "auto_include": True,
    },
    "resource_investigation": {
        "required_topics": ["应急资源", "应急资源调查", "应急救援物资", "应急物资"],
        "keyword_rules": ["应急资源", "应急物资", "资源调查"],
        "auto_include": True,
    },
    "special": {
        "required_topics": ["危险化学品", "特殊作业", "消防安全"],
        "keyword_rules": ["专项应急预案", "危化品", "消防"],
        "auto_include": True,
    },
    "onsite": {
        "required_topics": ["现场处置", "应急处置"],
        "keyword_rules": ["现场处置方案", "现场处置"],
        "auto_include": True,
    },
}


class ArticleIndexManager:
    """管理 index.yaml 的动态更新。"""

    @staticmethod
    def auto_classify(regulation_id, topics, full_name=""):
        """自动判定法规适用于哪些预案类型。返回 {plan_type: core|optional}。"""
        if not topics:
            return {}
        classification = {}
        topics_lower = [t.lower() for t in topics]
        name_lower = (full_name or "").lower()
        for pt, rules in PLAN_TYPE_RULES.items():
            if not rules.get("auto_include"):
                continue
            score = 0
            for rt in rules.get("required_topics", []):
                if any(rt.lower() in tl for tl in topics_lower):
                    score += 2
            for kw in rules.get("keyword_rules", []):
                if kw.lower() in name_lower:
                    score += 3
                if any(kw.lower() in tl for tl in topics_lower):
                    score += 1
            if score >= 2:
                classification[pt] = "core" if score >= 5 else "optional"
        return classification

    @staticmethod
    def update_index(regulation_id, classification):
        """安全地更新 index.yaml - 只追加，不覆盖手动配置。"""
        if not os.path.exists(INDEX_PATH):
            index = {}
        else:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                index = yaml.safe_load(f) or {}
        changed = False
        for pt, level in classification.items():
            sec = index.setdefault(pt, {"core": [], "optional": []})
            tlist = sec.get(level, [])
            if regulation_id not in tlist:
                tlist.append(regulation_id)
                sec[level] = tlist
                changed = True
                logger.info("index.yaml auto-add: %s -> %s/%s", regulation_id, pt, level)
        if changed:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(INDEX_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(index, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return changed

    @staticmethod
    def rebuild_index():
        """全量重建 index.yaml。"""
        from app.regulations import get_graph
        graph = get_graph()
        stats = {"total": 0, "classified": {}}
        new_index = {}
        for nid, data in graph._g.nodes(data=True):
            nt = data.get("node_type", "")
            if nt in ("topic", "article"):
                continue
            if data.get("status") == "abolished":
                continue
            stats["total"] += 1
            topics = data.get("topics", [])
            fn = data.get("full_name", data.get("label", ""))
            cl = ArticleIndexManager.auto_classify(nid, topics, fn)
            for pt, lvl in cl.items():
                sec = new_index.setdefault(pt, {"core": [], "optional": []})
                if nid not in sec[lvl]:
                    sec[lvl].append(nid)
                stats["classified"][pt] = stats["classified"].get(pt, 0) + 1
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_index, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        logger.info("index.yaml rebuilt: %d regs -> %s", stats["total"], stats["classified"])
        return stats
