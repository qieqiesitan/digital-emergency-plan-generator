"""一次性构建法规向量索引。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.regulations.vector_store import RegulationVectorStore

if __name__ == "__main__":
    vs = RegulationVectorStore()
    result = vs.rebuild_all(embedding_fn=None)
    print(f"索引构建完成: {result}")
