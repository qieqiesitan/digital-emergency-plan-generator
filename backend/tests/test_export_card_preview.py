"""导出预览：现场处置方案「应急处置卡」系列章节卡片化渲染测试。"""

from unittest.mock import MagicMock


def _onsite_card_section(key="sec_3_2", content="<h3>处置步骤</h3><ol><li>第一步</li></ol><h3>注意事项</h3><p>注意</p>"):
    sec = MagicMock()
    sec.section_key = key
    sec.title = "紧急处置步骤"
    sec.level = 1
    sec.content = content
    sec.mermaid_svgs = {}
    sec.diagram_svgs = {}
    return sec


def test_preview_onsite_card_section_wraps_h3_blocks():
    """onsite sec_3 章节预览应按 h3 分区包成卡片。"""
    from app.routers.export import _build_preview_section_html, _build_section_numbers

    sec = _onsite_card_section()
    numbers = _build_section_numbers([sec])
    html = _build_preview_section_html(sec, numbers, plan_type="onsite")

    assert 'class="emergency-card-section"' in html
    assert html.count('class="emergency-card"') == 2
    assert "处置步骤" in html
    assert "注意事项" in html


def test_preview_onsite_card_section_plain_content_wraps_single_card():
    """内容没有 h3 分区时，整段包一个卡片。"""
    from app.routers.export import _build_preview_section_html, _build_section_numbers

    sec = _onsite_card_section(content="<p>发现事故后立即报警。</p>")
    numbers = _build_section_numbers([sec])
    html = _build_preview_section_html(sec, numbers, plan_type="onsite")

    assert 'class="emergency-card-section"' in html
    assert html.count('class="emergency-card"') == 1


def test_preview_non_card_section_not_wrapped():
    """非 sec_3 章节（如事故风险提示）不套卡片容器。"""
    from app.routers.export import _build_preview_section_html, _build_section_numbers

    sec = _onsite_card_section(key="sec_1", content="<p>风险内容</p>")
    numbers = _build_section_numbers([sec])
    html = _build_preview_section_html(sec, numbers, plan_type="onsite")

    assert 'class="emergency-card-section"' not in html


def test_preview_css_has_emergency_card_styles():
    """预览 CSS 必须包含卡片容器与主题配色样式。"""
    from app.routers.export import PREVIEW_CSS

    assert ".emergency-card-section" in PREVIEW_CSS
    assert ".emergency-card" in PREVIEW_CSS
    assert "data-theme" in PREVIEW_CSS
