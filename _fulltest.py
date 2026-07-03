import asyncio, sys, json
sys.path.insert(0, "/app")
from app.database import async_session
from sqlalchemy import select
from app.models.enterprise import PlanProject, PlanSection, Enterprise, AIConfig, RiskSource, EmergencyResource
from app.routers.generation import (
    _build_section_prompt, _collect_enterprise_data, _enrich_with_reports,
    _stream_llm, _md_to_html, _pre_render_mermaid_svgs
)
from app.services.prompt_cache import ensure_loaded

async def test():
    await ensure_loaded()
    async with async_session() as db:
        # Get the plan
        plan = (await db.execute(
            select(PlanProject).where(PlanProject.id == "7d99bdb4-a276-4fa8-90a4-8bc3a157c6c1")
        )).scalar_one_or_none()
        if not plan:
            print("Plan not found")
            return
        
        # Get AI config
        ai_config = (await db.execute(
            select(AIConfig).where(AIConfig.user_id == plan.user_id)
        )).scalar_one_or_none()
        if not ai_config:
            print("No AI config")
            return
        
        # Get enterprise data
        ent = (await db.execute(
            select(Enterprise).where(Enterprise.id == plan.enterprise_id)
        )).scalar_one_or_none()
        risk_sources = (await db.execute(
            select(RiskSource).where(RiskSource.enterprise_id == plan.enterprise_id)
        )).scalars().all()
        resources = (await db.execute(
            select(EmergencyResource).where(EmergencyResource.enterprise_id == plan.enterprise_id)
        )).scalars().all()
        
        ent_data = _collect_enterprise_data(ent, risk_sources, resources) if ent else {}
        if ent:
            ent_data = await _enrich_with_reports(ent_data, plan.enterprise_id, db)
        
        # Get first section
        sections = (await db.execute(
            select(PlanSection).where(PlanSection.plan_project_id == plan.id).order_by(PlanSection.sort_order).limit(1)
        )).scalars().all()
        
        if not sections:
            print("No sections")
            return
        
        section = sections[0]
        print(f"Testing section: {section.title}, plan_type={plan.plan_type}")
        
        # Build prompt
        prompt = _build_section_prompt(
            section.title, ent_data,
            section_key=section.section_key,
            plan_type=plan.plan_type
        )
        print(f"Prompt length: {len(prompt)} chars")
        print(f"Prompt last 200: ...{prompt[-200:]}")
        
        # Call LLM
        print("Calling LLM...")
        try:
            result = await _stream_llm(prompt, ai_config, plan.plan_type)
            print(f"LLM response length: {len(result)} chars")
            print(f"First 100: {result[:100]}")
        except Exception as e:
            print(f"LLM call FAILED: {e}")

asyncio.run(test())
