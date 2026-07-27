"""ChromaDB 向量存储 ― 嵌入式向量数据库，语义检索法规条文。"""

import logging
import os

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
COLLECTION_NAME = "regulation_articles"

_chromadb = None

def _ensure_chromadb():
    """延迟导入 chromadb，避免未安装时整个模块崩溃。"""
    global _chromadb
    if _chromadb is None:
        import chromadb
        _chromadb = chromadb
    return _chromadb


class RegulationVectorStore:
    """ChromaDB 包装器，管理法规条文向量。"""

    def __init__(self):
        cb = _ensure_chromadb()
        os.makedirs(CHROMA_DIR, exist_ok=True)
        self._client = cb.PersistentClient(
            path=CHROMA_DIR,
            settings=cb.config.Settings(anonymized_telemetry=False),
        )
        self._collection = None

    def ensure_collection(self) -> None:
        """确保 collection 存在。"""
        if self._collection is not None:
            return
        try:
            self._collection = self._client.get_collection(COLLECTION_NAME)
        except Exception:
            self._collection = self._client.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB collection 已创建: %s", COLLECTION_NAME)

    # ── 写入 ──

    def add_regulation(self, regulation_id: str, articles: list[dict],
                       embedding_fn=None) -> int:
        self.ensure_collection()
        if not articles:
            return 0

        ids = [f"{regulation_id}_{a['number']}" for a in articles]
        texts = [a["text"] for a in articles]
        metadatas = []
        for a in articles:
            meta = dict(a.get("metadata", {}))
            meta["regulation_id"] = regulation_id
            meta["article_number"] = a.get("number", "")
            metadatas.append(meta)

        if embedding_fn:
            embeddings = embedding_fn(texts)
            self._collection.add(ids=ids, embeddings=embeddings,
                                 documents=texts, metadatas=metadatas)
        else:
            self._collection.add(ids=ids, documents=texts, metadatas=metadatas)

        logger.info("向量化完成: %s → %d 条条文", regulation_id, len(articles))
        return len(articles)

    # ── 检索 ──

    def search(self, query: str, top_k: int = 5,
               filter_ids: list[str] = None) -> list[dict]:
        self.ensure_collection()
        if self._collection.count() == 0:
            return []

        where = None
        if filter_ids:
            where = {"regulation_id": {"$in": filter_ids}}

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
            where=where,
        )

        output = []
        if results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                output.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                    "distance": results["distances"][0][i] if results.get("distances") else 0,
                })
        return output

    def search_articles(self, query: str, top_k: int = 20,
                        filter_ids: list[str] = None) -> list[dict]:
        """Article-level semantic search with wider recall."""
        self.ensure_collection()
        if self._collection.count() == 0:
            return []
        where = {"regulation_id": {"$in": filter_ids}} if filter_ids else None
        n = min(top_k * 2, self._collection.count())
        try:
            results = self._collection.query(
                query_texts=[query], n_results=n, where=where)
        except Exception:
            logger.warning("ChromaDB query failed")
            return []
        output = []
        if results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                output.append({"text": doc, "metadata": meta,
                               "distance": results["distances"][0][i] if results.get("distances") else 0})
        return output[:top_k]

    # management

    def delete_regulation(self, regulation_id: str) -> int:
        self.ensure_collection()
        existing = self._collection.get(
            where={"regulation_id": regulation_id})
        if existing and existing["ids"]:
            self._collection.delete(ids=existing["ids"])
        return len(existing["ids"]) if existing else 0

    def collection_count(self) -> int:
        self.ensure_collection()
        return self._collection.count()

    def rebuild_all(self, embedding_fn=None, texts_dir: str = None) -> dict:
        import re

        if texts_dir is None:
            texts_dir = os.path.join(DATA_DIR, "texts")

        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._collection = None
        self.ensure_collection()

        total = 0
        if not os.path.isdir(texts_dir):
            return {"total_articles": 0, "status": "no_texts_dir"}

        for fname in sorted(os.listdir(texts_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(texts_dir, fname)
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
                if text:
                    articles.append({
                        "number": title,
                        "text": text,
                        "metadata": {"source_file": fname},
                    })
            if articles:
                self.add_regulation(
                    regulation_id=fname.replace(".md", ""),
                    articles=articles,
                    embedding_fn=embedding_fn,
                )
                total += len(articles)

        return {"total_articles": total, "status": "done"}
