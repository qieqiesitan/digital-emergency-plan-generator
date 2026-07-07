"""
法规知识图谱模块 — 独立 Python package，与核心业务松耦合。

模块职责：
- graph.py: 法规知识图谱管理 (NetworkX)
- vector_store.py: ChromaDB 向量存储与语义检索
- retriever.py: 图谱 + 向量两级混合检索编排
- injector.py: Prompt 法规条文注入器
- sync.py: AI解析 + 源文件存档 + 变更日志
"""

import logging
import threading

logger = logging.getLogger(__name__)

_retriever = None
_lock = threading.Lock()


def get_retriever():
    """延迟初始化全局单例 Retriever"""
    global _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:
                from app.regulations.graph import RegulationGraph
                from app.regulations.vector_store import RegulationVectorStore
                from app.regulations.retriever import RegulationRetriever

                graph = RegulationGraph()
                graph.load()
                vector_store = RegulationVectorStore()
                _retriever = RegulationRetriever(graph, vector_store)
                logger.info("法规检索器已初始化")
    return _retriever


def get_graph():
    return get_retriever().graph


def get_vector_store():
    return get_retriever().vector_store
