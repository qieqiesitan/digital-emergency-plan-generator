import pytest
from app.services.risk_conversion_service import parse_score, combine_factor, conversion_reference


def test_parse_score_lec():
    assert parse_score("D=270") == 270


def test_combine_factor_min_default():
    factors = {"engineering": 0.5, "management": 0.7, "ppe": 0.85, "emergency": 0.9}
    assert combine_factor(factors, "min") == 0.5
    assert combine_factor(factors, "product") == pytest.approx(0.5 * 0.7 * 0.85 * 0.9)


def test_conversion_reference_level():
    thresholds = [
        {"min": 20, "max": 25, "level": "重大"},
        {"min": 15, "max": 19, "level": "较大"},
        {"min": 10, "max": 14, "level": "一般"},
        {"min": 1, "max": 9, "level": "低"},
    ]
    ref = conversion_reference("R=20", {"engineering": 0.5}, "min", thresholds)
    assert ref["reference_score"] == 10
    assert ref["reference_level"] == "一般"
