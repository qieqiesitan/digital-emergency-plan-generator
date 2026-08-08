from app.routers.generation import (
    SECTION_ADDITIONAL_DIAGRAM_MAP,
)


def test_additional_diagram_map_covers_sections():
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_3"] == "org_chart"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_4_2"] == "report_sequence"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_5"] == "response_timeline"
    assert SECTION_ADDITIONAL_DIAGRAM_MAP["sec_9_1"] == "drill_gantt"
