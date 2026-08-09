from unittest.mock import MagicMock, AsyncMock
import pytest


@pytest.mark.asyncio
async def test_regenerate_missing_diagrams_counts():
    from app.routers.diagrams import regenerate_missing_diagrams
    db = AsyncMock()
    sec = MagicMock()
    sec.section_key = "sec_2"
    sec.diagram_svgs = {"risk_matrix": {"placeholder": True}}
    plan = MagicMock()
    plan.plan_type = "comprehensive"
    result = await regenerate_missing_diagrams(db, plan, [sec], {"risk_events": [
        {"name": "火灾", "likelihood": 3, "severity": 4, "risk_level": "较大"}
    ]})
    assert result["regenerated"] == 1
    assert result["placeholders_remaining"] == 0


def test_preview_build_section_html_includes_placeholder_and_svg():
    from app.routers.export import _build_preview_section_html, _build_section_numbers

    sec = MagicMock()
    sec.title = "风险辨识与评估"
    sec.level = 1
    sec.content = "<p>风险内容</p>"
    sec.mermaid_svgs = {}
    sec.diagram_svgs = {
        "risk_matrix": {"placeholder": True, "reason": "缺少风险事件数据"},
        "evacuation": {
            "svg": '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
                   '<rect width="100" height="50" fill="#ccc"/></svg>'
        },
    }
    numbers = _build_section_numbers([sec])
    html = _build_preview_section_html(sec, numbers)

    assert "待补充数据后生成" in html
    assert "缺少风险事件数据" in html
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in html
    assert 'class="mermaid-diagram"' in html


def test_preview_build_section_html_escapes_placeholder_text():
    from app.routers.export import _build_preview_section_html, _build_section_numbers

    sec = MagicMock()
    sec.title = "风险辨识"
    sec.level = 1
    sec.content = "<p>内容</p>"
    sec.mermaid_svgs = {}
    sec.diagram_svgs = {
        "risk_matrix<script>": {"placeholder": True, "reason": "<b>缺失</b>"},
    }
    numbers = _build_section_numbers([sec])
    html = _build_preview_section_html(sec, numbers)

    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;" in html
    assert "<script>" not in html


def test_generate_plan_docx_includes_diagram_placeholder():
    from app.services.docx_template import generate_plan_docx

    doc = generate_plan_docx(
        company_name="测试企业",
        plan_title="综合应急预案",
        plan_type="comprehensive",
        sections=[{
            "title": "风险辨识与评估",
            "level": 1,
            "content": "<p>风险内容</p>",
            "mermaid_svgs": {},
            "diagram_svgs": {"risk_matrix": {"placeholder": True, "reason": "缺少风险事件数据"}},
        }],
    )
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "【risk_matrix】待补充企业数据后生成" in text
