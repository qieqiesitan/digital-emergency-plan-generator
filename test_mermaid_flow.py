import asyncio, re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models.enterprise import PlanSection, PlanProject
from app.services.mermaid_renderer import _extract_mermaid_code, render_mermaid_png, replace_mermaid_with_placeholders
from app.routers.export import _strip_section_heading

async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with AsyncSession(engine) as db:
        plans = (await db.execute(
            select(PlanProject).where(PlanProject.title.contains('œ÷≥°¥¶÷√'))
        )).scalars().all()
        plan = plans[0]
        
        sections = (await db.execute(
            select(PlanSection).where(PlanSection.plan_project_id == plan.id).order_by(PlanSection.sort_order)
        )).scalars().all()
        
        for s in sections:
            if not s.content or 'language-mermaid' not in s.content:
                continue
            
            print(f'\n=== Testing: {s.title} ===')
            
            content = s.content
            print(f'Original starts with: {content[:50]}...')
            
            content = _strip_section_heading(content)
            print(f'After strip starts with: {content[:50]}...')
            
            codes = _extract_mermaid_code(content)
            print(f'Extracted {len(codes)} mermaid codes')
            
            for i, code in enumerate(codes):
                print(f'  Code {i} (first 150 chars): {code[:150]}')
                
                # Check for HTML entities
                has_gt = '--&gt;' in code
                print(f'  Has --&gt; (HTML entity): {has_gt}')
                
                try:
                    png = await render_mermaid_png(code)
                    print(f'  Render: SUCCESS ({len(png)} bytes)')
                except Exception as e:
                    print(f'  Render: FAILED - {type(e).__name__}: {str(e)[:200]}')

asyncio.run(main())
