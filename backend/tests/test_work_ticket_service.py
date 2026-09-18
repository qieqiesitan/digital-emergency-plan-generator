"""作业票服务：编号生成、提交校验、审批推进、有效期。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.work_ticket_service import (
    SubmitValidationError,
    build_ticket_code,
    next_code_seq,
    validate_before_submit,
)


def test_build_ticket_code_format():
    code = build_ticket_code("DHZY", "TYKJ", datetime(2026, 9, 17), 1)
    assert code == "DHZY-TYKJ-20260917-0001"


def test_build_ticket_code_pads_to_four_digits():
    assert build_ticket_code("YXKJ", "A", datetime(2026, 1, 2), 42).endswith("-0042")


def test_next_code_seq_starts_at_one():
    assert next_code_seq([]) == 1


def test_next_code_seq_increments_from_max():
    """取当天已有序号的最大值 +1，避免删除中间记录后重号。"""
    existing = ["DHZY-A-20260917-0001", "DHZY-A-20260917-0003"]
    assert next_code_seq(existing) == 4


def test_next_code_seq_ignores_malformed_codes():
    assert next_code_seq(["DHZY-A-20260917-0002", "垃圾数据"]) == 3


def _tpl(required=("work_content",), allow_ai=True):
    fields = []
    for key in required:
        f = MagicMock()
        f.field_key = key
        f.label = key
        f.is_required = True
        fields.append(f)
    tpl = MagicMock()
    tpl.fields = fields
    tpl.code = "DHZY"
    return tpl


def _measures(count=2):
    out = []
    for i in range(count):
        m = MagicMock()
        m.is_mandatory = True
        m.measure_text = f"措施{i}"
        m.sort_order = i + 1
        out.append(m)
    return out


def _now():
    return datetime.now(timezone.utc)


def test_validate_flags_missing_required_field():
    errs = validate_before_submit(
        template=_tpl(required=("work_content",)),
        values={},
        measures=_measures(),
        confirmed_measure_orders=[1, 2],
        gas_tests=[{"sampled_at": _now()}],
        requires_gas_test=True,
    )
    assert any("work_content" in e for e in errs)


def test_validate_flags_unconfirmed_measure():
    errs = validate_before_submit(
        template=_tpl(),
        values={"work_content": "焊接"},
        measures=_measures(2),
        confirmed_measure_orders=[1],
        gas_tests=[{"sampled_at": _now()}],
        requires_gas_test=True,
    )
    assert any("措施" in e for e in errs)


def test_validate_requires_gas_test_for_hot_work():
    """动火/受限空间类没有气体检测记录一律不能提交。"""
    errs = validate_before_submit(
        template=_tpl(),
        values={"work_content": "焊接"},
        measures=_measures(),
        confirmed_measure_orders=[1, 2],
        gas_tests=[],
        requires_gas_test=True,
    )
    assert any("气体检测" in e for e in errs)


def test_validate_rejects_stale_gas_test():
    """取样时间必须覆盖开工前 30 分钟内。"""
    old = _now() - timedelta(hours=3)
    errs = validate_before_submit(
        template=_tpl(),
        values={"work_content": "焊接"},
        measures=_measures(),
        confirmed_measure_orders=[1, 2],
        gas_tests=[{"sampled_at": old}],
        requires_gas_test=True,
    )
    assert any("30 分钟" in e for e in errs)


def test_validate_passes_when_everything_ok():
    errs = validate_before_submit(
        template=_tpl(),
        values={"work_content": "焊接"},
        measures=_measures(),
        confirmed_measure_orders=[1, 2],
        gas_tests=[{"sampled_at": _now()}],
        requires_gas_test=True,
    )
    assert errs == []


def test_validate_has_no_skip_switch():
    """校验函数不接受任何"跳过"参数——法定必填项不得被开关绕过。"""
    import inspect

    params = set(inspect.signature(validate_before_submit).parameters)
    for banned in ("skip", "force", "bypass", "ignore_required", "ai_check_mode"):
        assert banned not in params, f"校验函数不应接受 {banned} 参数"


def test_gas_test_required_types_is_exactly_two():
    """只有动火与受限空间强制气体检测；扩到 8 类后这个集合不能变。"""
    from app.services.work_ticket_service import GAS_TEST_REQUIRED_TYPES

    assert set(GAS_TEST_REQUIRED_TYPES) == {"DHZY", "YXKJ"}


def test_other_six_types_do_not_require_gas_test():
    from app.services.work_ticket_service import requires_gas_test

    for code in ("MBCD", "GCZY", "QZDZ", "LSYD", "PTZY", "DLZY"):
        assert requires_gas_test(code) is False, code
    for code in ("DHZY", "YXKJ"):
        assert requires_gas_test(code) is True, code
