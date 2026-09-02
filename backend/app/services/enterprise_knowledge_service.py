"""企业画像知识库：风险/评估/资源上下文向量化 + 语义检索。"""
import logging
import os

from sqlalchemy import select

logger = logging.getLogger(__name__)

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "regulations", "data", "chroma_db")
COLLECTION_NAME = "enterprise_knowledge"


def _build_enterprise_text(name: str, risk_context: dict, reports: list, resources: list) -> str:
    parts = [f"企业：{name}"]
    for rs in risk_context.get("risk_sources", []):
        parts.append(
            f"风险源：{rs.get('name')}，等级：{rs.get('risk_level')}，"
            f"事故类型：{rs.get('accident_type')}，管控措施：{rs.get('control_measures')}"
        )
    for r in reports:
        parts.append(f"报告：{r}")
    for res in resources:
        parts.append(f"资源：{res.get('name')}，类别：{res.get('category')}，数量：{res.get('quantity')}{res.get('unit')}")
    return "\n".join(parts)


class EnterpriseKnowledgeStore:
    """独立封装企业画像 collection（metadata 按 enterprise_id 过滤）。"""

    def __init__(self):
        import chromadb
        os.makedirs(os.path.abspath(CHROMA_DIR), exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=os.path.abspath(CHROMA_DIR),
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

    def index_enterprise(self, enterprise_id: str, texts: list[str]) -> int:
        """先删旧向量再写入（幂等重建）。"""
        self._collection.delete(where={"enterprise_id": enterprise_id})
        ids = [f"{enterprise_id}_{i}" for i in range(len(texts))]
        metas = [{"enterprise_id": enterprise_id} for _ in texts]
        self._collection.add(ids=ids, documents=texts, metadatas=metas)
        return len(texts)

    def delete_enterprise(self, enterprise_id: str) -> None:
        """删除某企业全部向量（文本不足等场景清旧索引，防止与 DB 漂移）。"""
        self._collection.delete(where={"enterprise_id": enterprise_id})

    def search(self, enterprise_id: str, question: str, top_k: int = 6) -> list[dict]:
        if self._collection.count() == 0:
            return []
        results = self._collection.query(
            query_texts=[question], n_results=min(top_k, self._collection.count()),
            where={"enterprise_id": enterprise_id})
        out = []
        if results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                out.append({"text": doc, "distance": results["distances"][0][i]})
        return out


def _report_text(report) -> str:
    """评估报告转可索引文本（summary 为 JSONB dict，安全转字符串并截断）。"""
    title = report.title or "评估报告"
    summary = report.summary or {}
    if isinstance(summary, dict):
        chunks = []
        for key in ("overall_assessment", "conclusion"):
            value = summary.get(key)
            if value:
                chunks.append(str(value))
        if not chunks and summary.get("chapters"):
            chunks.append(str(summary["chapters"]))
        body = "；".join(chunks)
    else:
        body = str(summary)
    return f"{title}：{body[:300]}"


async def build_enterprise_index(enterprise_id: str, db) -> int:
    """从风险上下文/评估报告/资源调查组装文本并写入向量库。"""
    from app.models.enterprise import Enterprise, EmergencyResource
    from app.models.risk_assessment import RiskAssessmentReport
    from app.services.risk_context_builder import build_risk_management_context
    ent = (await db.execute(select(Enterprise).where(Enterprise.id == enterprise_id))).scalar_one_or_none()
    if not ent:
        return 0
    ctx = await build_risk_management_context(enterprise_id, db)
    resources = (await db.execute(select(EmergencyResource).where(
        EmergencyResource.enterprise_id == enterprise_id))).scalars().all()
    reports = (await db.execute(select(RiskAssessmentReport).where(
        RiskAssessmentReport.enterprise_id == enterprise_id))).scalars().all()
    texts = [_build_enterprise_text(
        ent.name, ctx,
        [_report_text(r) for r in reports],
        [{"name": r.name, "category": r.category, "quantity": r.quantity, "unit": r.unit}
         for r in resources])]
    if not texts[0].strip() or len(texts[0]) < 20:
        # 文本不足时删除旧向量，避免向量库残留过期画像
        EnterpriseKnowledgeStore().delete_enterprise(enterprise_id)
        return 0
    return EnterpriseKnowledgeStore().index_enterprise(enterprise_id, texts)
