"""
法规知识图谱模块 — 独立 Python package，与核心业务松耦合。
"""

import logging
import threading

logger = logging.getLogger(__name__)

_retriever = None
_lock = threading.Lock()


def get_retriever():
    """延迟初始化全局单例 Retriever。向量存储可选。"""
    global _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:
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

                _retriever = RegulationRetriever(graph, vector_store)
                logger.info("法规检索器已初始化 (向量:%s)", "可用" if vector_store else "不可用")
    return _retriever


def get_graph():
    return get_retriever().graph


def get_vector_store():
    return get_retriever().vector_store
