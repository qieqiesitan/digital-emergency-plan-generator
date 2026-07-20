"""
法规知识图谱管理器 — 基于 NetworkX 的有向图。

法规节点：law / standard / policy / topic
关系边：替代 / 上位法 / 引用 / 适用
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone

import networkx as nx

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
GRAPH_PATH = os.path.join(DATA_DIR, "graph.json")
INDEX_PATH = os.path.join(DATA_DIR, "index.yaml")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RegulationGraph:
    """法规知识图谱，封装 NetworkX DiGraph。"""

    def __init__(self):
        self._g = nx.DiGraph()
        self._lock = threading.Lock()

    # ── 加载 / 持久化 ──

    def load(self) -> None:
        """从 graph.json 加载图谱。文件不存在则从空图开始。"""
        with self._lock:
            if os.path.exists(GRAPH_PATH):
                with open(GRAPH_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._g = nx.node_link_graph(data, edges="edges")
                logger.info("图谱已加载: %d 节点, %d 边", self._g.number_of_nodes(), self._g.number_of_edges())
            else:
                self._g = nx.DiGraph()
                logger.info("graph.json 不存在，从空图开始")

    def save(self) -> None:
        """持久化到 graph.json。"""
        with self._lock:
            data = nx.node_link_data(self._g, edges="edges")
            data["directed"] = True
            data["multigraph"] = False
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(GRAPH_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    # ── 查询 ──

    def query_by_plan_type(self, plan_type: str) -> dict:
        """
        按预案类型查询法规。
        返回: {"effective": [node_dict], "abolished": [node_dict]}
        """
        import yaml
        if not os.path.exists(INDEX_PATH):
            logger.warning("index.yaml 不存在")
            return {"effective": [], "abolished": []}

        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f) or {}

        plan_config = index.get(plan_type, {})
        core_ids = plan_config.get("core", [])
        optional_ids = plan_config.get("optional", [])
        all_ids = core_ids + optional_ids

        effective, abolished = [], []
        for nid in all_ids:
            if nid not in self._g:
                continue
            node = dict(self._g.nodes[nid])
            node["id"] = nid
            node["is_core"] = nid in core_ids
            if node.get("status") == "abolished":
                abolished.append(node)
            else:
                effective.append(node)

        return {"effective": effective, "abolished": abolished}
        return {"effective": effective, "abolished": abolished, "core_ids": core_ids}

    # ── article sub-node management (V1.0) ──

    def add_article_node(self, regulation_id, article):
        import re as _re
        num = article.get("number", "")
        safe = _re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "_", num)
        aid = "art_%s_%s" % (regulation_id, safe)
        if aid in self._g:
            self._g.nodes[aid].update({
                "article_text": article.get("text",""),
                "updated_at": _now()})
            return aid
        self._g.add_node(aid, label=num,
                        full_name=article.get("title", num),
                        node_type="article", status="effective",
                        article_number=num,
                        article_text=article.get("text",""),
                        parent_regulation=regulation_id,
                        topics=article.get("topics",[]),
                        created_at=_now(), updated_at=_now())
        self._g.add_edge(aid, regulation_id, relation="belongs_to")
        return aid

    def get_articles_by_regulation(self, regulation_id):
        result = []
        for nid, data in list(self._g.nodes(data=True)):
            if data.get("node_type") == "article" and data.get("parent_regulation") == regulation_id:
                node = dict(data)
                node["id"] = nid
                result.append(node)
        return sorted(result, key=lambda a: a.get("article_number", ""))

    def set_article_status(self, article_id, status, superseded_by=""):
        if article_id not in self._g:
            return False
        self._g.nodes[article_id]["status"] = status
        self._g.nodes[article_id]["updated_at"] = _now()
        if superseded_by:
            self._g.nodes[article_id]["superseded_by"] = superseded_by
        return True

    def get_effective_articles(self, regulation_id):
        return [a for a in self.get_articles_by_regulation(regulation_id)
                if a.get("status") != "abolished"]

    def query_articles_by_plan_type(self, plan_type):
        plan_regs = self.query_by_plan_type(plan_type)
        articles = []
        for reg in plan_regs.get("effective", []):
            articles.extend(self.get_articles_by_regulation(reg["id"]))
        return articles

    def infer_article_topics(self, article_text: str, reg_topics: list[str] = None) -> list[str]:
        """从条文文本中推断 topic 标签。"""
        if not article_text:
            return []
        from app.regulations.scorer import TopicValidator
        matched = []
        text_lower = article_text.lower()
        reg_topics = reg_topics or []
        for canonical in TopicValidator.VALID_TOPICS:
            candidates = [canonical] + TopicValidator.ALIASES.get(canonical, [])
            for cand in candidates:
                cnt = text_lower.count(cand.lower())
                if cnt >= 2:
                    matched.append(canonical)
                    break
                if cnt == 1 and canonical in reg_topics:
                    matched.append(canonical)
                    break
        return list(set(matched))


    def query_by_topic(self, topic: str, limit: int = 10) -> list[dict]:
        """按主题标签查询法规。"""
        results = []
        for nid, data in self._g.nodes(data=True):
            topics = data.get("topics") or []
            if topic in topics and data.get("status") != "abolished":
                node = dict(data)
                node["id"] = nid
                results.append(node)
                if len(results) >= limit:
                    break
        return results

    def get_node(self, node_id: str) -> dict | None:
        """获取单个节点数据。"""
        if node_id in self._g:
            node = dict(self._g.nodes[node_id])
            node["id"] = node_id
            return node
        return None

    def get_edges(self) -> list[dict]:
        """获取所有边。"""
        return [{"source": s, "target": t, "relation": d.get("relation", "")}
                for s, t, d in self._g.edges(data=True)]

    def trace_chain(self, node_id: str, relation: str = "上位法") -> list[str]:
        """追溯关系链，返回 id 列表。"""
        chain = []
        current = node_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            chain.append(current)
            successors = [t for _, t, d in self._g.out_edges(current, data=True)
                          if d.get("relation") == relation]
            current = successors[0] if successors else None
        return chain

    # ── 增删改 ──

    def add_node(self, node: dict) -> str:
        """新增节点。node 必须含 id 字段。"""
        nid = node.pop("id")
        node.setdefault("created_at", _now())
        node.setdefault("updated_at", _now())
        node.setdefault("status", "effective")
        with self._lock:
            self._g.add_node(nid, **node)
        self.save()
        logger.info("新增节点: %s (%s)", nid, node.get("label", ""))
        return nid

    def update_node(self, node_id: str, updates: dict) -> bool:
        """更新节点字段。"""
        if node_id not in self._g:
            return False
        updates["updated_at"] = _now()
        with self._lock:
            for k, v in updates.items():
                self._g.nodes[node_id][k] = v
        self.save()
        return True

    def add_edge(self, source: str, target: str, relation: str) -> None:
        """新增关系边。"""
        with self._lock:
            self._g.add_edge(source, target, relation=relation)
        self.save()

    def abolish(self, node_id: str, replaced_by: str = "") -> bool:
        """标记法规废止。"""
        if node_id not in self._g:
            return False
        with self._lock:
            self._g.nodes[node_id]["status"] = "abolished"
            self._g.nodes[node_id]["updated_at"] = _now()
            if replaced_by:
                self._g.nodes[node_id]["abolished_by"] = replaced_by
                if replaced_by in self._g:
                    self._g.add_edge(node_id, replaced_by, relation="替代")
        self.save()
        logger.info("法规废止: %s → %s", node_id, replaced_by)
        return True

    def delete_node(self, node_id: str) -> bool:
        """删除节点及关联边。"""
        if node_id not in self._g:
            return False
        with self._lock:
            self._g.remove_node(node_id)
        self.save()
        return True

    def list_nodes(self, node_type: str = None, status: str = None,
                   keyword: str = "", page: int = 1, page_size: int = 20) -> dict:
        """分页列出节点。"""
        results = []
        for nid, data in self._g.nodes(data=True):
            node = dict(data)
            node["id"] = nid
            # 默认隐藏 topic（除非明确筛选"主题"类型）
            # Always hide article sub-nodes
            if node.get("node_type") == "article":
                continue
            # Hide topics by default (show only if explicitly requested)
            if node.get("node_type") == "topic" and (not node_type or node_type == "all"):
                continue
                continue
            if node_type and node_type != "all" and node.get("node_type") != node_type:
                continue
            if status and status != "all" and node.get("status") != status:
                continue
            if keyword:
                kw = keyword.lower()
                label = (node.get("label") or "").lower()
                full = (node.get("full_name") or "").lower()
                code = (node.get("code") or "").lower()
                if kw not in label and kw not in full and kw not in code:
                    continue
            # Fallback identifiers
            if not node.get("code") and not node.get("label") and not node.get("full_name"):
                node["code"] = node.get("id", nid)
            results.append(node)

        results.sort(key=lambda n: n.get("updated_at", ""), reverse=True)
        total = len(results)
        start = (page - 1) * page_size
        return {"items": results[start:start + page_size], "total": total,
                "page": page, "page_size": page_size}

    def stats(self) -> dict:
        """统计信息。"""
        nodes = [(nid, d) for nid, d in self._g.nodes(data=True) if d.get("node_type") not in ("topic", "article")]
        total = len(nodes)
        effective = sum(1 for _, d in nodes if d.get("status") != "abolished")
        abolished = total - effective
        return {"total": total, "effective": effective, "abolished": abolished}

    def all_nodes(self) -> list[dict]:
        """返回所有节点（用于前端图谱渲染）。仅 article 子节点不返回。"""
        results = []
        for nid, data in self._g.nodes(data=True):
            node = dict(data)
            if node.get("node_type") == "article":
                continue
            node["id"] = nid
            # Fallback identifiers for nodes without code/label
            if not node.get("code") and not node.get("label") and not node.get("full_name"):
                node["code"] = nid
            results.append(node)
        return results

    def validate(self) -> list[str]:
        """图谱完整性校验，返回问题列表。"""
        issues = []
        for s, t, d in self._g.edges(data=True):
            rel = d.get("relation", "")
            if rel not in ("替代", "上位法", "引用", "适用"):
                issues.append(f"边 {s}→{t} 关系类型无效: {rel}")
        for nid, data in self._g.nodes(data=True):
            if data.get("status") == "abolished":
                if data.get("abolished_by"):
                    ab = data["abolished_by"]
                    if ab not in self._g:
                        issues.append(f"节点 {nid} 引用的替代法规 {ab} 不存在")
        return issues
