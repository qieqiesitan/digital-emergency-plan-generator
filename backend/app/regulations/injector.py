"""Prompt injector -- delegates to RegulationContextBuilder."""

import logging

logger = logging.getLogger(__name__)


def inject_regulations(plan_type: str, section_key: str,
                       section_title: str, prompt: str,
                       enterprise_data: dict = None) -> str:
    from app.regulations.context_builder import RegulationContextBuilder
    try:
        ctx = RegulationContextBuilder().get_chapter_context(
            section_key=section_key,
            section_title=section_title,
            plan_type=plan_type,
            enterprise_data=enterprise_data,
        )
    except Exception as e:
        logger.warning("Regulation context build failed: %s", e)
        return prompt
    if not ctx or "unavailable" in ctx:
        return prompt
    return prompt + "\n\n---\n\n" + ctx
