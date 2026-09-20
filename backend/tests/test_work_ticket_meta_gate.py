"""作业票 values_meta / measures_meta / 成员证照 的模型与提交门禁。"""

from types import SimpleNamespace

from app.services.work_ticket_service import validate_before_submit


def test_instance_has_meta_columns():
    from app.models.work_ticket import WorkTicketInstance

    cols = WorkTicketInstance.__table__.columns
    assert "values_meta" in cols, "缺少 values_meta 列"
    assert "measures_meta" in cols, "缺少 measures_meta 列"
    assert cols["values_meta"].nullable is False
    assert cols["measures_meta"].nullable is False


def test_member_has_certificates_column():
    from app.models.enterprise_org import EnterpriseMember

    cols = EnterpriseMember.__table__.columns
    assert "certificates" in cols, "缺少 certificates 列"
    assert cols["certificates"].nullable is False


def _template():
    return SimpleNamespace(
        fields=[
            SimpleNamespace(
                field_key="risk_identification", label="风险辨识结果", is_required=True
            ),
            SimpleNamespace(field_key="work_content", label="作业内容", is_required=True),
        ]
    )


def _measures():
    return [
        SimpleNamespace(sort_order=1, measure_text="措施一", is_mandatory=True),
        SimpleNamespace(sort_order=2, measure_text="措施二", is_mandatory=True),
    ]


def _validate(**overrides):
    base = dict(
        template=_template(),
        values={"risk_identification": "内容", "work_content": "内容"},
        measures=_measures(),
        confirmed_measure_orders=[],
        gas_tests=[],
        requires_gas_test=False,
    )
    base.update(overrides)
    return validate_before_submit(**base)


def test_ai_field_without_confirmation_blocks():
    errors = _validate(values_meta={"risk_identification": {"source": "ai"}})
    assert any("AI 生成内容，尚未经人工确认" in e for e in errors)


def test_ai_field_with_confirmation_passes():
    errors = _validate(
        values_meta={
            "risk_identification": {
                "source": "ai",
                "confirmed_at": "2026-09-20T10:00:00+08:00",
            }
        }
    )
    assert not any("AI 生成内容" in e for e in errors)


def test_missing_values_meta_never_blocks():
    """老票（无 meta）必须完全不受影响。"""
    assert not any("AI 生成内容" in e for e in _validate(values_meta=None))


def test_non_ai_source_without_confirmation_passes():
    errors = _validate(values_meta={"risk_identification": {"source": "history"}})
    assert not any("AI 生成内容" in e for e in errors)


def test_measures_stated_via_meta_are_handled():
    errors = _validate(
        measures_meta={
            "1": {"state": "confirmed"},
            "2": {"state": "not_applicable", "reason_text": "本票不涉及"},
        }
    )
    assert not any("未确认" in e or "未表态" in e for e in errors)


def test_not_applicable_without_reason_blocks():
    errors = _validate(
        measures_meta={
            "1": {"state": "not_applicable"},
            "2": {"state": "confirmed"},
        }
    )
    assert any("未填写理由" in e for e in errors)


def test_confirmed_orders_still_work_without_meta():
    """老路径（只传 confirmed_measures）必须继续通过。"""
    errors = _validate(confirmed_measure_orders=[1, 2])
    assert not any("未确认" in e or "未表态" in e for e in errors)
