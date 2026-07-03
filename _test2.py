import asyncio, sys, logging
sys.path.insert(0, "/app")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("test")

from app.database import async_session
from sqlalchemy import select
from app.models.enterprise import PlanProject, PlanSection, Enterprise, AIConfig, RiskSource, EmergencyResource
from app.routers.generation import _build_section_prompt, _collect_enterprise_data, _enrich_with_reports, _stream_llm
from app.services.prompt_cache import ensure_loaded

async def test():
    await ensure_loaded()
    async with async_session() as db:
        plan = (await db.execute(select(PlanProject).where(PlanProject.id == "7d99bdb4-a276-4fa8-90a4-8bc3a157c6c1"))).scalar_one_or_none()
        if not plan: logger.error("Plan not found"); return
        ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == plan.user_id))).scalar_one_or_none()
        if not ai_config: logger.error("No AI config"); return
        ent = (await db.execute(select(Enterprise).where(Enterprise.id == plan.enterprise_id))).scalar_one_or_none()
        risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == plan.enterprise_id))).scalars().all()
        resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == plan.enterprise_id))).scalars().all()
        ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}
        if ent: ent_data = await _enrich_with_reports(ent_data, plan.enterprise_id, db)
        sections = (await db.execute(select(PlanSection).where(PlanSection.plan_project_id == plan.id).order_by(PlanSection.sort_order).limit(1))).scalars().all()
        if not sections: logger.error("No sections"); return
        section = sections[0]
        logger.info(f"TEST: section={section.title}, type={plan.plan_type}, key={section.section_key}")
        prompt = _build_section_prompt(section.title, ent_data, section_key=section.section_key, plan_type=plan.plan_type)
        logger.info(f"TEST: prompt_len={len(prompt)}")
        logger.info(f"TEST: calling LLM...")
        try:
            result = await _stream_llm(prompt, ai_config, plan.plan_type)
            logger.info(f"TEST: LLM response len={len(result)}")
        except Exception as e:
            logger.error(f"TEST: LLM FAILED: {e}")

asyncio.run(test())
