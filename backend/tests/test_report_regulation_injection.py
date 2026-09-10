"""回归：风险评估/应急资源调查报告的章节提示词必须注入法规上下文。

根因：risk_assessment_service / resource_investigation_service 调用
RegulationContextBuilder.get_chapter_context 时未 import 该类，NameError 被
build_chapter_prompt 的 except Exception: pass 静默吞掉，法规纲要从未注入。
"""

import pytest

from app.regulations.context_builder import RegulationContextBuilder
from app.services.risk_assessment_service import (
    build_chapter_prompt as ra_build_chapter_prompt,
)
from app.services.resource_investigation_service import (
    build_chapter_prompt as ri_build_chapter_prompt,
)


FAKE_REGULATION_TEXT = "【法规写作纲要】测试注入条文 2026-09-03"


RA_CTX = {
    "enterprise": {"name": "测试企业", "industry": "商贸服务"},
    "risk_sources": [],
}

RI_CTX = {
    "enterprise": {"name": "测试企业", "industry": "商贸服务"},
    "internal_resources": [],
    "external_resources": [],
    "risk_conclusion": None,
    "top_risks": [],
}


@pytest.fixture
def fake_regulation_context(monkeypatch):
    """把法规上下文构建器替换为固定文本，验证调用链真的把它拼进提示词。"""

    def fake_get_chapter_context(self, **kwargs):
        return FAKE_REGULATION_TEXT

    monkeypatch.setattr(
        RegulationContextBuilder, "get_chapter_context", fake_get_chapter_context
    )


def test_risk_assessment_prompt_includes_regulation_context(fake_regulation_context):
    prompt = ra_build_chapter_prompt("ch1_hazard_id", RA_CTX)
    assert FAKE_REGULATION_TEXT in prompt


def test_resource_investigation_prompt_includes_regulation_context(
    fake_regulation_context,
):
    prompt = ri_build_chapter_prompt("ch1_purpose", RI_CTX)
    assert FAKE_REGULATION_TEXT in prompt
