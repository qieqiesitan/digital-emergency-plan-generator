"""
Seed script: populate PromptTemplate table with risk_assessment and
resource_investigation prompts from the hardcoded fallbacks.
Run once: python backend/seed_report_prompts.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import async_session
from app.models.prompt import PromptTemplate
from app.services.risk_assessment_service import SYSTEM_PROMPT as RA_SYSTEM_PROMPT
from app.services.resource_investigation_service import SYSTEM_PROMPT as RI_SYSTEM_PROMPT
from app.services.risk_assessment_service import CHAPTER_DEFINITIONS as RA_CHAPTERS
from app.services.resource_investigation_service import CHAPTER_DEFINITIONS as RI_CHAPTERS
from sqlalchemy import select

# System prompts
SYSTEM_PROMPTS = [
    {
        "template_code": "risk_assessment_system_default",
        "category": "risk_assessment_system",
        "template_name": "风险评估系统提示词",
        "system_prompt": RA_SYSTEM_PROMPT,
        "user_prompt_template": "",
    },
    {
        "template_code": "resource_investigation_system_default",
        "category": "resource_investigation_system",
        "template_name": "应急资源调查系统提示词",
        "system_prompt": RI_SYSTEM_PROMPT,
        "user_prompt_template": "",
    },
]

# Chapter prompts
CHAPTER_PROMPTS = []
for ch in RA_CHAPTERS:
    CHAPTER_PROMPTS.append({
        "template_code": f"risk_assessment_section_{ch['key']}",
        "category": "risk_assessment_section",
        "template_name": ch["title"],
        "system_prompt": "",
        "user_prompt_template": ch["instruction"],
    })
for ch in RI_CHAPTERS:
    CHAPTER_PROMPTS.append({
        "template_code": f"resource_investigation_section_{ch['key']}",
        "category": "resource_investigation_section",
        "template_name": ch["title"],
        "system_prompt": "",
        "user_prompt_template": ch["instruction"],
    })

ALL_PROMPTS = SYSTEM_PROMPTS + CHAPTER_PROMPTS


async def seed():
    async with async_session() as db:
        count = 0
        for p in ALL_PROMPTS:
            existing = (
                await db.execute(
                    select(PromptTemplate).where(
                        PromptTemplate.template_code == p["template_code"]
                    )
                )
            ).scalar_one_or_none()
            if existing:
                # Update existing
                existing.template_name = p["template_name"]
                existing.system_prompt = p["system_prompt"]
                existing.user_prompt_template = p["user_prompt_template"]
                print(f"  Updated: {p['template_code']}")
            else:
                # Create new
                db.add(PromptTemplate(**p))
                print(f"  Created: {p['template_code']}")
            count += 1
        await db.commit()
        print(f"\nDone: {count} prompt templates seeded/updated")


if __name__ == "__main__":
    asyncio.run(seed())
