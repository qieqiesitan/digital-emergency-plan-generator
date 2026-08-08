from app.routers.sections import _render_org_structure_html


def test_render_org_structure_html_creates_tables():
    org = [{
        "group_name": "应急救援指挥部",
        "members": [
            {"name": "张三", "position": "总指挥", "phone": "13800000000", "responsibilities": "全面指挥"},
            {"name": "李四", "position": "副总指挥", "phone": "13900000000", "responsibilities": "协助指挥"},
        ],
    }]
    html = _render_org_structure_html(org)
    assert "应急救援指挥部" in html
    assert "张三" in html and "13800000000" in html
    assert "总指挥" in html
    assert "<table" in html


def test_render_org_structure_html_empty_members_skipped():
    org = [{"group_name": "空组", "members": []}]
    assert _render_org_structure_html(org) == ""
