from app.services.risk_mapping_service import normalize_polygon, validate_polygon_v2, effective_color


def test_normalize_legacy_points():
    result = normalize_polygon({"points": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}, "原料库")
    assert result["version"] == 2
    assert result["polygons"][0]["label"] == "原料库"
    assert result["polygons"][0]["points"][0]["x"] == 1


def test_validate_polygon_rejects_bad_coordinates():
    errors = validate_polygon_v2({
        "version": 2,
        "color_source": "manual",
        "color": "#ff4d4f",
        "polygons": [{"id": "p1", "points": [{"x": 10, "y": 10}, {"x": 20, "y": 20}, {"x": 30, "y": 101}]}],
    })
    assert any("0-100" in e for e in errors)


def test_manual_color_wins():
    color = effective_color({"version": 2, "color_source": "manual", "color": "#123456", "polygons": []}, "重大")
    assert color == "#123456"
