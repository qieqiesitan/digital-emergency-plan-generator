import asyncio, json, logging, sys
logging.basicConfig(level=logging.INFO)
from app.database import async_session
from app.models.enterprise import PlanProject, PlanSection, Enterprise, AIConfig, RiskSource, EmergencyResource
from app.routers.generation import _build_section_prompt, _stream_llm_chunks, _collect_enterprise_data, _enrich_with_reports, _md_to_html, _pre_render_mermaid_svgs, _collect_previous_context
from app.services.prompt_cache import ensure_loaded
from sqlalchemy import select

async def main():
    plan_id = sys.argv[1] if len(sys.argv) > 1 else "57651e07-6e80-4bd5-9692-6ede57d82cec"
    await ensure_loaded()

    async with async_session() as db:
        p = (await db.execute(select(PlanProject).where(PlanProject.id == plan_id))).scalar_one_or_none()
        if not p:
            print(f"Plan {plan_id} not found")
            return
        print(f"Plan: {p.title} [{p.plan_type}]")

        ai_config = (await db.execute(select(AIConfig).where(AIConfig.user_id == p.user_id))).scalar_one_or_none()
        if not ai_config:
            print("No AI config")
            return
        print(f"AI: {ai_config.provider}/{ai_config.model_name}")

        ent = (await db.execute(select(Enterprise).where(Enterprise.id == p.enterprise_id))).scalar_one_or_none()
        risk_sources = (await db.execute(select(RiskSource).where(RiskSource.enterprise_id == p.enterprise_id))).scalars().all()
        resources = (await db.execute(select(EmergencyResource).where(EmergencyResource.enterprise_id == p.enterprise_id))).scalars().all()
        ent_data = _collect_enterprise_data(ent, risk_sources, resources, p.accident_type) if ent else {}
        if ent:
            ent_data = await _enrich_with_reports(ent_data, p.enterprise_id, db)

        sections = list((await db.execute(
            select(PlanSection).where(PlanSection.plan_project_id == plan_id).order_by(PlanSection.sort_order)
        )).scalars().all())

        p.status = "generating"
        await db.commit()

        completed = 0
        failed = 0
        for i, s in enumerate(sections):
            ctx = _collect_previous_context(sections, s.section_key)
            prompt = _build_section_prompt(s.title, ent_data, section_key=s.section_key,
                                           plan_type=p.plan_type, accident_type=p.accident_type,
                                           previous_context=ctx)
            print(f"[{i+1}/{len(sections)}] {s.section_key}: {s.title} | prompt={len(prompt)} chars", flush=True)
            try:
                full = ""
                async for chunk in _stream_llm_chunks(prompt, ai_config, p.plan_type):
                    full += chunk
                s.content = _md_to_html(full)
                s.ai_generated = True
                completed += 1
                await db.commit()
                print(f"  OK: {len(full)} chars", flush=True)
                try:
                    s.mermaid_svgs = await asyncio.wait_for(_pre_render_mermaid_svgs(full), timeout=30)
                except:
                    s.mermaid_svgs = None
            except Exception as e:
                failed += 1
                print(f"  FAIL: {e}", flush=True)

        p.status = "completed" if failed == 0 else "draft"
        await db.commit()
        print(f"Done: {completed}/{len(sections)} ok, {failed} failed, status={p.status}")

asyncio.run(main())
