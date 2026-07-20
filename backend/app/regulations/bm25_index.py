"""BM25 倒排索引 —— 条文号/法规简称的精确关键词匹配。

作为检索管路的第 0 级（L1），高分命中的结果直接进入最终输出。
与 ChromaDB 向量库互补：
- BM25 处理精确匹配（条文号"第二十一条"、法规编号"GB/T 29639"）
- ChromaDB 处理语义相似（"应急响应程序" ≈ "事故应急处置流程"）
"""

import json
import logging
import os
import re
from collections import defaultdict
from math import log

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BM25_INDEX_PATH = os.path.join(DATA_DIR, "bm25_index.json")


class BM25ArticleIndex:
    """轻量级 BM25 实现，索引持久化为 JSON 文件。"""

    def __init__(self):
        self._docs: dict[str, dict] = {}         # article_id -> {text, meta}
        self._inverted_index: dict[str, dict[str, int]] = defaultdict(dict)
        self._doc_lengths: dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._total_docs: int = 0
        self._k1: float = 1.2
        self._b: float = 0.75

    # ── 索引构建 ──

    def index_articles(
        self,
        articles: list[dict],
        regulation_id: str,
        regulation_name: str = "",
        regulation_code: str = "",
    ):
        """将一批条文加入 BM25 索引。

        articles: [{"number": "第四条", "text": "..."}, ...]
        """
        for art in articles:
            art_num = art.get("number", "?")
            aid = f"art_{regulation_id}_{art_num}"
            text = art.get("text", "")
            self._docs[aid] = {
                "text": text,
                "meta": {
                    "regulation_id": regulation_id,
                    "regulation_name": regulation_name,
                    "regulation_code": regulation_code,
                    "article_number": art_num,
                },
            }
            # 分词：条文全文 + 条文号 + 法规名 + 法规编号
            tokens = self._tokenize(text)
            tokens.extend(self._tokenize(art_num))
            tokens.extend(self._tokenize(regulation_name))
            if regulation_code:
                tokens.extend(self._tokenize(regulation_code))

            for token in tokens:
                self._inverted_index[token][aid] = (
                    self._inverted_index[token].get(aid, 0) + 1
                )
            self._doc_lengths[aid] = len(tokens)

        self._total_docs = len(self._docs)
        self._avg_doc_length = (
            sum(self._doc_lengths.values()) / max(self._total_docs, 1)
        )

    # ── 检索 ──

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 检索。返回 [{id, score, meta, text}]。"""
        if not self._docs or not query:
            return []

        query_tokens = self._tokenize(query)
        scores: dict[str, float] = {}

        for token in query_tokens:
            if token not in self._inverted_index:
                continue
            posting = self._inverted_index[token]
            df = len(posting)
            idf = log((self._total_docs - df + 0.5) / (df + 0.5) + 1.0)

            for aid, tf in posting.items():
                doc_len = self._doc_lengths.get(aid, 1)
                score = idf * (tf * (self._k1 + 1)) / (
                    tf
                    + self._k1
                    * (1 - self._b + self._b * doc_len / max(self._avg_doc_length, 1))
                )
                scores[aid] = scores.get(aid, 0.0) + score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for aid, score in ranked:
            doc = self._docs.get(aid, {})
            results.append({
                "id": aid,
                "score": round(score, 4),
                "meta": doc.get("meta", {}),
                "text": doc.get("text", ""),
            })
        return results

    # ── 分词 ──

    def _tokenize(self, text: str) -> list[str]:
        """中文 2-gram + 条文号模式 + 法规编号模式 + 英文/数字词。"""
        if not text:
            return []
        tokens = []

        # 条文号: "第X条"、"第XX条"
        article_pattern = re.findall(r'第[一二三四五六七八九十百\d]+条', text)
        tokens.extend(article_pattern)

        # 法规编号: "GB/T 29639-2020"
        code_pattern = re.findall(r'[A-Z]{2,}[/T]?\s*\d+[.\d]*-?\d*', text)
        tokens.extend(code_pattern)

        # 中文 2-gram
        cleaned = re.sub(
            r'[\s，。；：、！？《》（）""''「」\\[\\]【】\-,.()\\[\\]{}]',
            '',
            text,
        )
        for i in range(len(cleaned) - 1):
            tokens.append(cleaned[i : i + 2])

        # 英文/数字词（长度 >= 2）
        en_tokens = re.findall(r'[a-zA-Z0-9]+', text)
        tokens.extend(t.lower() for t in en_tokens if len(t) >= 2)

        return tokens

    # ── 持久化 ──

    def persist(self):
        """持久化到 JSON 文件。"""
        os.makedirs(DATA_DIR, exist_ok=True)
        data = {
            "docs": self._docs,
            "inverted_index": {k: dict(v) for k, v in self._inverted_index.items()},
            "doc_lengths": self._doc_lengths,
            "avg_doc_length": self._avg_doc_length,
            "total_docs": self._total_docs,
        }
        with open(BM25_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("BM25 index persisted: %d docs", self._total_docs)

    def load(self):
        """从 JSON 文件恢复索引。"""
        if not os.path.exists(BM25_INDEX_PATH):
            logger.info("BM25 index file not found, starting fresh")
            return
        with open(BM25_INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._docs = data.get("docs", {})
        self._inverted_index = defaultdict(
            dict,
            {k: dict(v) for k, v in data.get("inverted_index", {}).items()},
        )
        self._doc_lengths = data.get("doc_lengths", {})
        self._avg_doc_length = data.get("avg_doc_length", 0.0)
        self._total_docs = data.get("total_docs", 0)
        logger.info("BM25 index loaded: %d docs", self._total_docs)

    def delete_regulation(self, regulation_id: str):
        """删除某法规的所有条目。"""
        prefix = f"art_{regulation_id}_"
        to_delete = [aid for aid in self._docs if aid.startswith(prefix)]
        for aid in to_delete:
            # 从倒排索引中移除
            for token in list(self._inverted_index.keys()):
                if aid in self._inverted_index[token]:
                    del self._inverted_index[token][aid]
                    if not self._inverted_index[token]:
                        del self._inverted_index[token]
            # 从文档和长度中移除
            del self._docs[aid]
            del self._doc_lengths[aid]
        self._total_docs = len(self._docs)
        self._avg_doc_length = (
            sum(self._doc_lengths.values()) / max(self._total_docs, 1)
        )
        if to_delete:
            logger.info("BM25: deleted %d articles for %s", len(to_delete), regulation_id)

    def rebuild_all(self, texts_dir: str = None) -> dict:
        """全量重建 BM25 索引（从 texts/*.md 文件）。"""
        from app.regulations import get_graph

        if texts_dir is None:
            texts_dir = os.path.join(DATA_DIR, "texts")

        # 清空
        self._docs.clear()
        self._inverted_index.clear()
        self._doc_lengths.clear()

        graph = get_graph()
        total = 0

        if not os.path.isdir(texts_dir):
            return {"total_articles": 0, "status": "no_texts_dir"}

        for fname in sorted(os.listdir(texts_dir)):
            if not fname.endswith(".md"):
                continue
            reg_id = fname.replace(".md", "")
            fpath = os.path.join(texts_dir, fname)

            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析条文
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

            if not articles:
                continue

            # 获取法规元数据
            node = graph.get_node(reg_id) or {}
            self.index_articles(
                articles,
                regulation_id=reg_id,
                regulation_name=node.get("full_name", node.get("label", "")),
                regulation_code=node.get("code", ""),
            )
            total += len(articles)

        self.persist()
        logger.info("BM25 rebuild complete: %d regs, %d articles", total, total)
        return {"total_articles": total, "status": "done"}