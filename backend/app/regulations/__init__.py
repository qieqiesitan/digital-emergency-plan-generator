"""
法规知识图谱模块 — 独立 Python package，与核心业务松耦合。
"""

import logging

logger = logging.getLogger(__name__)

_retriever = None


def get_retriever():
    """延迟初始化全局单例 Retriever。向量存储可选。
    
    注意：不使用锁。并发初始化是幂等的——都读同一个 graph.json 文件，
    双重初始化无害但 threading.Lock 会阻塞 asyncio 事件循环。
    """
    global _retriever
    if _retriever is not None:
        return _retriever

    from app.regulations.graph import RegulationGraph
    from app.regulations.retriever import RegulationRetriever

    graph = RegulationGraph()
    graph.load()

    # 向量存储可选
    vector_store = None
    try:
        from app.regulations.vector_store import RegulationVectorStore
        vector_store = RegulationVectorStore()
    except ImportError as e:
        logger.warning("向量存储不可用(chromadb未安装): %s，将仅使用图谱检索", e)

        # BM25 索引可选
    bm25_index = None
    try:
        from app.regulations.bm25_index import BM25ArticleIndex
        bm25_index = BM25ArticleIndex()
        bm25_index.load()
    except ImportError as e:
        logger.warning("BM25 索引不可用: %s", e)

    _retriever = RegulationRetriever(graph, vector_store, bm25_index=bm25_index)
    logger.info("法规检索器已初始化 (向量:%s)", "可用" if vector_store else "不可用")
    return _retriever


def get_graph():
    return get_retriever().graph


_scorer = None

def get_scorer():
    global _scorer
    if _scorer is None:
        from app.regulations.scorer import ArticleRelevanceScorer
        _scorer = ArticleRelevanceScorer()
    return _scorer

def get_vector_store():
    return get_retriever().vector_store