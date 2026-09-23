"""企业创建/更新的入参宽容度。

背景（2026-09-23 用户实测）：前端表单把未填字段传成空字符串，
而数字字段收到 "" 会被 pydantic 判为类型错误 → 整个创建请求 422，
用户只看到「422」不知道哪个字段错了。
"""


def test_create_tolerates_empty_numeric_strings():
    from app.schemas.enterprise import EnterpriseCreate

    payload = EnterpriseCreate(
        name="西安宝岳空间科技",
        employee_count="",
        land_area="",
        building_area="",
        registered_capital="",
        safety_staff_count="",
    )
    assert payload.employee_count is None
    assert payload.land_area is None
    assert payload.building_area is None
    assert payload.registered_capital is None
    assert payload.safety_staff_count is None


def test_create_keeps_empty_text_fields_as_is():
    """文本字段的空串在 Create 里本就合法（列可空），不归一化。

    刻意不碰文本字段：Update 沿用它时，「传空串」是清空该字段的语义，
    归一化成 None 会变成「不改」（2026-09-23 实测踩到过这个回归）。
    """
    from app.schemas.enterprise import EnterpriseCreate

    payload = EnterpriseCreate(name="某企业", address="", phone="   ", credit_code="")
    assert payload.address == ""
    assert payload.phone == "   "
    assert payload.credit_code == ""


def test_name_is_still_required_and_keeps_its_message():
    """name 不做空串归一化，否则「企业名称必填」的提示会被冲掉。"""
    import pytest
    from pydantic import ValidationError

    from app.schemas.enterprise import EnterpriseCreate

    with pytest.raises(ValidationError):
        EnterpriseCreate(name="")


def test_valid_numbers_are_preserved():
    from app.schemas.enterprise import EnterpriseCreate

    payload = EnterpriseCreate(name="某企业", employee_count=120, land_area="3500.5")
    assert payload.employee_count == 120
    assert payload.land_area == 3500.5
