import asyncio, logging, sys
from app.database import async_session
from app.models.enterprise import PlanSection
from app.models.user import User
from app.models.enterprise import PlanProject
from app.services.mermaid_renderer import _extract_mermaid_code, render_mermaid_svg, _mermaid_hash
from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")

async def backfill_all():
    async with async_session() as db:
        result = await db.execute(
            select(PlanSection).where(PlanSection.content.contains("language-mermaid"))
        )
        sections = list(result.scalars().all())
        logger.info(f"Found {len(sections)} sections with mermaid code")

        updated_count = 0
        failed_count = 0
        skipped_count = 0

        for section in sections:
            if not section.content:
                continue

            codes = _extract_mermaid_code(section.content)
            if not codes:
                continue

            new_svgs = dict(section.mermaid_svgs or {})
            needs_update = False

            for code in codes:
                h = _mermaid_hash(code)
                if h not in new_svgs:
                    try:
                        svg = await render_mermaid_svg(code)
                        new_svgs[h] = svg
                        needs_update = True
                        logger.info(f"  OK: {section.title[:30]} hash={h[:8]} size={len(svg)}")
                    except Exception as e:
                        logger.error(f"  FAIL: {section.title[:30]} {e}")
                        failed_count += 1
                        continue

            if needs_update:
                section.mermaid_svgs = new_svgs
                await db.flush()
                updated_count += 1
            else:
                skipped_count += 1

        await db.commit()
        logger.info(f"DONE: updated={updated_count} skipped={skipped_count} failed={failed_count}")

        # Verify
        verify = await db.execute(
            select(PlanSection).where(PlanSection.content.contains("language-mermaid"))
        )
        for s in verify.scalars().all():
            codes = _extract_mermaid_code(s.content or "")
            has_svgs = bool(s.mermaid_svgs)
            if codes and not has_svgs:
                logger.error(f"VERIFY FAIL: {s.title[:30]} still has no svgs despite having {len(codes)} codes!")
        logger.info("Verification complete")

if __name__ == "__main__":
    asyncio.run(backfill_all())
